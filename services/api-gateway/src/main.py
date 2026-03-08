import json
import os
import re
import urllib.error
import urllib.request
from html import unescape

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlalchemy.orm import Session

from autohaggle_shared.communication_client import send_negotiation_email, send_negotiation_sms
from autohaggle_shared.database import SessionLocal, get_db, init_db
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.jobs import run_autonomous_round
from autohaggle_shared.negotiation import run_negotiation_strategy
from autohaggle_shared.playbook import apply_playbook_target, apply_playbook_tone, build_playbook_policy_snapshot, resolve_playbook
from autohaggle_shared.queueing import get_queue
from autohaggle_shared.repository import (
    add_message,
    acknowledge_saved_search_alert,
    acknowledge_saved_search_alerts,
    create_saved_search,
    create_session,
    delete_saved_search,
    get_offer_history,
    get_offer_trend_summary,
    get_session_with_messages,
    list_offer_catalog,
    list_saved_search_alerts,
    list_saved_searches,
    list_sessions,
    update_session_autopilot,
    update_session_job_metadata,
    update_session_playbook,
    update_session_status,
    upsert_offer_observations,
)
from autohaggle_shared.schemas import (
    AutopilotUpdateRequest,
    AssistantChatRequest,
    AssistantChatResponse,
    DealerOffer,
    DealerSiteInput,
    EnqueueRoundRequest,
    EnqueueRoundResponse,
    JobStatusResponse,
    HealthResponse,
    NegotiationDecision,
    NegotiationMessageOut,
    NegotiationSessionOut,
    NegotiationSessionUpdateRequest,
    NegotiationStatusUpdateRequest,
    OfferCatalogResponse,
    OfferHistoryResponse,
    OfferRankRequest,
    OfferRankResponse,
    OfferSearchRequest,
    OfferSearchResponse,
    OfferTrendItem,
    OfferTrendsBulkRequest,
    OfferTrendsBulkResponse,
    RankedOffer,
    SavedSearchAlertAckAllRequest,
    SavedSearchAlertAckAllResponse,
    SavedSearchAlertAckResponse,
    SavedSearchAlertListResponse,
    SavedSearchCreateRequest,
    SavedSearchDeleteResponse,
    SavedSearchListResponse,
    SavedSearchOut,
    StartNegotiationRequest,
    StartNegotiationResponse,
)
from scraper_pipeline.fallback_agent import ingest_dealer_data_to_fallback
from scraper_pipeline.search_service import search_local_offers

app = FastAPI(title="AutoHaggle AI API Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestFallbackRequest(BaseModel):
    user_zip: str = Field(min_length=3, max_length=12)
    radius_miles: int = Field(default=100, ge=1, le=250)
    budget_otd: float = Field(gt=0)
    targets: list[dict] = Field(min_length=1)
    dealer_sites: list[DealerSiteInput] | None = None


class IngestFallbackResponse(BaseModel):
    provider: str
    jobs_collected: int
    normalized_count: int
    inserted: int
    updated: int


class SimulatedInboundRequest(BaseModel):
    channel: str = Field(default="email", min_length=3, max_length=20)
    body: str = Field(min_length=1, max_length=4000)
    sender_identity: str | None = Field(default=None, max_length=255)
    user_name: str | None = Field(default=None, max_length=120)


def _dom_bucket(days: int | None) -> str | None:
    if days is None:
        return None
    if days <= 7:
        return "0-7"
    if days <= 14:
        return "8-14"
    if days <= 30:
        return "15-30"
    if days <= 60:
        return "31-60"
    return "61+"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new": {"active", "closed", "failed"},
    "active": {"queued", "running", "responded", "closed", "failed"},
    "queued": {"running", "responded", "closed", "failed"},
    "running": {"responded", "closed", "failed"},
    "responded": {"queued", "running", "closed", "failed"},
    "closed": {"active"},
    "failed": {"active", "closed"},
}

def _normalize_status(value: str | None) -> str:
    return (value or "").strip().lower()

def _can_transition_status(current_status: str | None, next_status: str | None) -> bool:
    current = _normalize_status(current_status)
    nxt = _normalize_status(next_status)
    if not current or not nxt:
        return False
    if current == nxt:
        return True
    return nxt in ALLOWED_STATUS_TRANSITIONS.get(current, set())

def _is_job_active(status: str | None) -> bool:
    return _normalize_status(status) in {"queued", "started", "scheduled", "deferred", "running"}

def _format_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:,.0f}"


def _assistant_suggestions(message: str) -> list[str]:
    lowered = message.lower()
    if "negot" in lowered or "email" in lowered or "message" in lowered:
        return [
            "Draft a firmer follow-up message",
            "What counter should I send if dealer refuses?",
            "Summarize leverage from competing offers",
        ]
    if "dom" in lowered or "risk" in lowered or "trend" in lowered:
        return [
            "Explain why DOM affects leverage",
            "Which offer has highest urgency?",
            "Compare trend risk for top 3 offers",
        ]
    return [
        "Which offer should I negotiate first and why?",
        "Give me a target anchor for the top deal",
        "What should I ask the dealer next?",
    ]


def _extract_offer_ids(context) -> set[str]:
    if not context:
        return set()

    ids: set[str] = set()
    for offer in context.offers:
        if offer.offer_id:
            ids.add(str(offer.offer_id))
    for ranked in context.ranked_offers:
        if ranked.offer.offer_id:
            ids.add(str(ranked.offer.offer_id))
    return ids


def _serialize_offer_for_prompt(offer: DealerOffer, rank: int | None = None) -> dict:
    return {
        "offer_id": offer.offer_id,
        "rank": rank,
        "dealership_name": offer.dealership_name,
        "vehicle_label": offer.vehicle_label,
        "otd_price": offer.otd_price,
        "msrp": offer.msrp,
        "advertised_price": offer.advertised_price,
        "selling_price": offer.selling_price,
        "listed_price": offer.listed_price,
        "dealer_discount": offer.dealer_discount,
        "fees": offer.fees,
        "distance_miles": offer.distance_miles,
        "days_on_market": offer.days_on_market,
        "days_on_market_bucket": offer.days_on_market_bucket,
        "price_drop_7d": offer.price_drop_7d,
        "price_drop_30d": offer.price_drop_30d,
        "inventory_status": offer.inventory_status,
        "vin": offer.vin,
    }


def _normalize_external_url(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None

    if re.match(r"^https?://", raw, flags=re.IGNORECASE):
        return raw
    if raw.startswith("//"):
        return f"https:{raw}"
    return f"https://{raw}"


def _candidate_live_urls(context) -> list[str]:
    if not context:
        return []

    urls: list[str] = []
    seen: set[str] = set()

    def add_url(value: str | None) -> None:
        normalized = _normalize_external_url(value)
        if not normalized:
            return
        if normalized in seen:
            return
        seen.add(normalized)
        urls.append(normalized)

    for ranked in context.ranked_offers[:8]:
        add_url(ranked.offer.listing_url)
        add_url(ranked.offer.dealer_url)

    for offer in context.offers[:10]:
        add_url(offer.listing_url)
        add_url(offer.dealer_url)

    return urls[:4]


def _extract_text_snippet(html_text: str, max_chars: int = 1600) -> str:
    body = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<style\b[^>]*>.*?</style>", " ", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<[^>]+>", " ", body)
    body = unescape(body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:max_chars]


def _fetch_live_pages_for_prompt(payload: AssistantChatRequest) -> tuple[list[dict[str, str]], list[str]]:
    if not payload.use_live_web:
        return [], []

    pages: list[dict[str, str]] = []
    checked_urls: list[str] = []
    urls = _candidate_live_urls(payload.context)

    for url in urls:
        checked_urls.append(url)
        try:
            req = urllib.request.Request(
                url=url,
                headers={
                    "User-Agent": "AutoHaggleCopilot/0.1 (+local)",
                    "Accept": "text/html,application/xhtml+xml",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                raw = response.read(220_000).decode("utf-8", errors="ignore")
            snippet = _extract_text_snippet(raw)
            if snippet:
                pages.append({"url": url, "snippet": snippet})
        except Exception:
            # Skip individual fetch failures; keep checked URL list for transparency.
            continue

    return pages, checked_urls


def _build_assistant_messages(payload: AssistantChatRequest) -> tuple[list[dict[str, str]], list[str]]:
    context = payload.context
    rank_by_offer_id: dict[str, int] = {}
    if context:
        for ranked in context.ranked_offers[:20]:
            rank_by_offer_id[str(ranked.offer.offer_id)] = int(ranked.rank)

    prompt_offers: list[dict] = []
    if context:
        source = context.ranked_offers[:20] if context.ranked_offers else []
        if source:
            for ranked in source:
                prompt_offers.append(_serialize_offer_for_prompt(ranked.offer, rank=int(ranked.rank)))
        else:
            for offer in context.offers[:20]:
                prompt_offers.append(_serialize_offer_for_prompt(offer, rank=rank_by_offer_id.get(str(offer.offer_id))))

    live_pages, checked_urls = _fetch_live_pages_for_prompt(payload)

    context_blob = {
        "budget_otd": context.budget_otd if context else None,
        "offers": prompt_offers,
        "use_live_web": payload.use_live_web,
        "live_pages": live_pages,
    }

    system_text = (
        "You are AutoHaggle Copilot. Use the provided context and any fetched live pages. "
        "If live pages are empty, say you could not fetch dealer pages for this request. "
        "Always answer in a structured bullet format and avoid long paragraphs. "
        "Use this exact response layout:\n"
        "Summary:\n"
        "- <1-2 concise bullets>\n"
        "Recommended Actions:\n"
        "- <2-4 actionable bullets>\n"
        "Negotiation Script:\n"
        "- <1-2 copy-ready lines the user can send>\n"
        "Keep each bullet short and concrete. "
        "If evidence comes from specific offers, include the final line exactly in this format: "
        "CITED_IDS: offer_id_1,offer_id_2 . "
        "If no citation, use CITED_IDS: none"
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_text}]

    for item in payload.history[-8:]:
        role = "assistant" if item.role.strip().lower() == "assistant" else "user"
        messages.append({"role": role, "content": item.content})

    messages.append(
        {
            "role": "user",
            "content": (
                f"Question: {payload.message}\n\n"
                f"Context JSON:\n{json.dumps(context_blob, ensure_ascii=True)}"
            ),
        }
    )
    return messages, checked_urls

def _openai_headers() -> dict[str, str]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _parse_answer_and_citations(text: str, allowed_offer_ids: set[str]) -> tuple[str, list[str]]:
    raw = text.strip()
    citation_line_match = re.search(r"(?im)^CITED_IDS:\s*(.+)$", raw)

    cited: list[str] = []
    if citation_line_match:
        cited_raw = citation_line_match.group(1).strip()
        raw = re.sub(r"(?im)^CITED_IDS:\s*.+$", "", raw).strip()
        if cited_raw.lower() != "none":
            for token in re.split(r"[\s,]+", cited_raw):
                item = token.strip()
                if item and item in allowed_offer_ids and item not in cited:
                    cited.append(item)

    bracket_ids = re.findall(r"\[\[([^\]]+)\]\]", raw)
    if bracket_ids:
        for item in bracket_ids:
            clean = item.strip()
            if clean in allowed_offer_ids and clean not in cited:
                cited.append(clean)
        raw = re.sub(r"\[\[[^\]]+\]\]", "", raw).strip()

    return raw, cited


def _build_fallback_assistant_answer(payload: AssistantChatRequest) -> AssistantChatResponse:
    message = payload.message.strip()
    context = payload.context
    offers = list(context.offers) if context else []
    ranked = list(context.ranked_offers) if context else []
    budget = context.budget_otd if context else None

    top_offer: DealerOffer | None = None
    if ranked:
        top_offer = ranked[0].offer
    elif offers:
        top_offer = min(offers, key=lambda item: item.otd_price)

    if not top_offer:
        return AssistantChatResponse(
            answer=("Summary:\n- I do not have offer data yet.\n"
                "Recommended Actions:\n- Run Search and Rank first.\n- Ask again after offers are loaded.\n"
                "Negotiation Script:\n- Not available until offers are loaded."),
            suggestions=_assistant_suggestions(message),
            cited_offer_ids=[],
            checked_urls=[],
            model="fallback-rule-engine",
        )

    delta_text = ""
    if budget:
        delta = top_offer.otd_price - budget
        delta_text = (
            f" This is {_format_money(abs(delta))} under your budget."
            if delta <= 0
            else f" This is {_format_money(delta)} above your budget."
        )

    lowered = message.lower()
    if "negot" in lowered or "email" in lowered or "message" in lowered:
        anchor = max(1.0, top_offer.otd_price - max(300.0, top_offer.otd_price * 0.015))
        answer = (
            "Summary:\n"
            f"- Best immediate anchor is {_format_money(anchor)} for {top_offer.vehicle_label}.\n"
            "Recommended Actions:\n"
            f"- Start with {top_offer.dealership_name} and present {_format_money(anchor)} OTD as same-week close.\n"
            "- Ask for itemized OTD and expiration date in writing.\n"
            "Negotiation Script:\n"
            f"- I can buy this week at {_format_money(anchor)} OTD if we finalize today."
        )
    elif "dom" in lowered or "risk" in lowered or "trend" in lowered:
        dom = top_offer.days_on_market or 0
        risk = "LOW" if dom < 20 else "MEDIUM" if dom < 45 else "HIGH"
        answer = (
            "Summary:\n"
            f"- Top-offer DOM risk is {risk} (DOM {dom}d).{delta_text}\n"
            "Recommended Actions:\n"
            "- Prioritize dealers with higher DOM and recent price drops.\n"
            "- Ask for a same-day decision window to capture urgency.\n"
            "Negotiation Script:\n"
            "- Given market time on this unit, I can close today if we agree on a sharper OTD."
        )
    else:
        answer = (
            "Summary:\n"
            f"- Best current candidate is {top_offer.vehicle_label} at {top_offer.dealership_name} for {_format_money(top_offer.otd_price)} OTD.{delta_text}\n"
            "Recommended Actions:\n"
            "- Use this offer as anchor and request written OTD breakdown.\n"
            "- Ask two competing dealers to beat this OTD by a fixed amount.\n"
            "Negotiation Script:\n"
            f"- I have a written {_format_money(top_offer.otd_price)} OTD offer; if you can beat it, I can finalize today."
        )

    return AssistantChatResponse(
        answer=answer.strip(),
        suggestions=_assistant_suggestions(message),
        cited_offer_ids=[str(top_offer.offer_id)],
        checked_urls=[],
        model="fallback-rule-engine",
    )


def _call_openai_completion(payload: AssistantChatRequest) -> tuple[str, str, list[str]]:
    messages, checked_urls = _build_assistant_messages(payload)
    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    req_body = {
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "messages": messages,
    }
    data = json.dumps(req_body).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, headers=_openai_headers(), method="POST")

    with urllib.request.urlopen(request, timeout=90) as response:
        parsed = json.loads(response.read().decode("utf-8"))

    choices = parsed.get("choices") or []
    content = ""
    if choices:
        content = str((choices[0].get("message") or {}).get("content") or "")
    model = str(parsed.get("model") or OPENAI_MODEL)
    return content, model, checked_urls


def _stream_openai_completion(messages: list[dict[str, str]]):
    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    req_body = {
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "stream": True,
        "messages": messages,
    }
    data = json.dumps(req_body).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, headers=_openai_headers(), method="POST")

    model_name = OPENAI_MODEL
    with urllib.request.urlopen(request, timeout=120) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line or not line.startswith("data:"):
                continue

            payload_text = line[5:].strip()
            if payload_text == "[DONE]":
                break

            try:
                event = json.loads(payload_text)
            except json.JSONDecodeError:
                continue

            model_name = str(event.get("model") or model_name)
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = (choices[0].get("delta") or {}).get("content")
            if isinstance(delta, str) and delta:
                yield delta, model_name

def _sse(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"


@app.post("/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(payload: AssistantChatRequest) -> AssistantChatResponse:
    allowed_ids = _extract_offer_ids(payload.context)
    try:
        raw_answer, model_name, checked_urls = _call_openai_completion(payload)
        answer, cited_offer_ids = _parse_answer_and_citations(raw_answer, allowed_ids)
        return AssistantChatResponse(
            answer=answer or "I could not produce an answer for that prompt.",
            suggestions=_assistant_suggestions(payload.message),
            cited_offer_ids=cited_offer_ids,
            checked_urls=checked_urls,
            model=model_name,
        )
    except Exception:
        return _build_fallback_assistant_answer(payload)


@app.post("/assistant/chat/stream")
def assistant_chat_stream(payload: AssistantChatRequest) -> StreamingResponse:
    allowed_ids = _extract_offer_ids(payload.context)
    messages, checked_urls = _build_assistant_messages(payload)

    def stream_events():
        collected: list[str] = []
        model_name = OPENAI_MODEL

        try:
            for delta, model_name in _stream_openai_completion(messages):
                collected.append(delta)
                yield _sse("delta", {"text": delta})

            full_text = "".join(collected)
            answer, cited_offer_ids = _parse_answer_and_citations(full_text, allowed_ids)
            yield _sse(
                "done",
                {
                    "answer": answer or "I could not produce an answer for that prompt.",
                    "suggestions": _assistant_suggestions(payload.message),
                    "cited_offer_ids": cited_offer_ids,
                    "checked_urls": checked_urls,
                    "model": model_name,
                },
            )
        except Exception:
            fallback = _build_fallback_assistant_answer(payload)
            for chunk_start in range(0, len(fallback.answer), 24):
                yield _sse("delta", {"text": fallback.answer[chunk_start : chunk_start + 24]})
            yield _sse(
                "done",
                {
                    "answer": fallback.answer,
                    "suggestions": fallback.suggestions,
                    "cited_offer_ids": fallback.cited_offer_ids,
                    "checked_urls": checked_urls,
                    "model": fallback.model,
                },
            )

    return StreamingResponse(stream_events(), media_type="text/event-stream")

@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/saved-searches", response_model=SavedSearchListResponse)
def get_saved_searches(limit: int = 50, db: Session = Depends(get_db)) -> SavedSearchListResponse:
    return SavedSearchListResponse(searches=list_saved_searches(db, limit=limit))


@app.post("/saved-searches", response_model=SavedSearchOut)
def save_search(payload: SavedSearchCreateRequest, db: Session = Depends(get_db)) -> SavedSearchOut:
    return create_saved_search(db, payload)


@app.delete("/saved-searches/{search_id}", response_model=SavedSearchDeleteResponse)
def remove_saved_search(search_id: str, db: Session = Depends(get_db)) -> SavedSearchDeleteResponse:
    deleted = delete_saved_search(db, search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return SavedSearchDeleteResponse(deleted=True)
@app.get("/alerts", response_model=SavedSearchAlertListResponse)
def get_alerts(
    include_acknowledged: bool = False,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> SavedSearchAlertListResponse:
    alerts, total = list_saved_search_alerts(
        db,
        include_acknowledged=include_acknowledged,
        page=page,
        page_size=page_size,
    )
    safe_page_size = max(1, min(page_size, 100))
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = max(1, min(page, total_pages))
    return SavedSearchAlertListResponse(
        alerts=alerts,
        total=total,
        page=safe_page,
        page_size=safe_page_size,
        total_pages=total_pages,
    )


@app.post("/alerts/{alert_id}/ack", response_model=SavedSearchAlertAckResponse)
def ack_alert(alert_id: str, db: Session = Depends(get_db)) -> SavedSearchAlertAckResponse:
    ok = acknowledge_saved_search_alert(db, alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")
    return SavedSearchAlertAckResponse(acknowledged=True)


@app.post("/alerts/ack-all", response_model=SavedSearchAlertAckAllResponse)
def ack_all_alerts(payload: SavedSearchAlertAckAllRequest, db: Session = Depends(get_db)) -> SavedSearchAlertAckAllResponse:
    count = acknowledge_saved_search_alerts(db, alert_ids=payload.alert_ids)
    return SavedSearchAlertAckAllResponse(acknowledged_count=count)
@app.post("/ingest/fallback", response_model=IngestFallbackResponse)
def ingest_fallback(payload: IngestFallbackRequest) -> IngestFallbackResponse:
    result = ingest_dealer_data_to_fallback(
        user_zip=payload.user_zip,
        radius_miles=payload.radius_miles,
        budget_otd=payload.budget_otd,
        targets=payload.targets,
        dealer_sites=[item.model_dump() for item in payload.dealer_sites] if payload.dealer_sites else None,
    )
    return IngestFallbackResponse(**result)


@app.post("/offers/search", response_model=OfferSearchResponse)
def search_offers(payload: OfferSearchRequest, db: Session = Depends(get_db)) -> OfferSearchResponse:
    targets = [
        {
            "make": target.make,
            "model": target.model,
            "year": target.year,
            "trim": target.trim,
        }
        for target in payload.targets
    ]

    raw_offers = search_local_offers(
        user_zip=payload.user_zip,
        radius_miles=payload.radius_miles,
        budget_otd=payload.budget_otd,
        targets=targets,
        dealer_sites=[item.model_dump() for item in payload.dealer_sites] if payload.dealer_sites else None,
        include_in_transit=payload.include_in_transit,
        include_pre_sold=payload.include_pre_sold,
        include_hidden=payload.include_hidden,
    )

    # Providers can return incomplete records (for example, zero/blank prices).
    # Filter invalid rows before persistence/serialization so the API stays stable.
    sanitized_offers: list[dict] = []
    for item in raw_offers:
        try:
            otd_price = float(item.get("otd_price") or 0.0)
        except (TypeError, ValueError):
            continue
        if otd_price <= 0:
            continue
        if not item.get("offer_id") or not item.get("dealership_id") or not item.get("vehicle_id"):
            continue
        item["otd_price"] = otd_price
        sanitized_offers.append(item)

    raw_offers = sanitized_offers
    if not raw_offers:
        return OfferSearchResponse(offers=[])

    days_by_offer_id = upsert_offer_observations(db, raw_offers)
    for item in raw_offers:
        offer_id = str(item.get("offer_id") or "")
        provider_dom = item.get("provider_days_on_market")
        if isinstance(provider_dom, int) and provider_dom >= 0:
            item["days_on_market"] = provider_dom
            item["days_on_market_source"] = "provider"
        else:
            item["days_on_market"] = days_by_offer_id.get(offer_id)
            item["days_on_market_source"] = "tracked"

        item["days_on_market_bucket"] = _dom_bucket(item.get("days_on_market"))
        trend = get_offer_trend_summary(
            db,
            dealership_id=str(item.get("dealership_id") or ""),
            vehicle_key=str(item.get("vehicle_id") or ""),
        )
        item["price_drop_7d"] = trend.price_drop_7d
        item["price_drop_30d"] = trend.price_drop_30d

    offers = [DealerOffer(**item) for item in raw_offers]
    return OfferSearchResponse(offers=offers)


@app.get("/offers/catalog", response_model=OfferCatalogResponse)
def offer_catalog(
    dealer_id: str | None = None,
    dealer_name: str | None = None,
    city: str | None = None,
    state: str | None = None,
    make: str | None = None,
    model: str | None = None,
    min_otd: float | None = None,
    max_otd: float | None = None,
    min_dom: int | None = None,
    max_dom: int | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
) -> OfferCatalogResponse:
    offers, total, filters = list_offer_catalog(
        db,
        dealer_id=dealer_id,
        dealer_name=dealer_name,
        city=city,
        state=state,
        make=make,
        model=model,
        min_otd=min_otd,
        max_otd=max_otd,
        min_dom=min_dom,
        max_dom=max_dom,
        page=page,
        page_size=page_size,
    )

    safe_page_size = max(1, min(page_size, 200))
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = max(1, min(page, total_pages))

    return OfferCatalogResponse(
        offers=offers,
        total=total,
        page=safe_page,
        page_size=safe_page_size,
        total_pages=total_pages,
        filters=filters,
    )


@app.get("/offers/trends", response_model=OfferTrendItem)
def offer_trends(
    dealership_id: str,
    vehicle_id: str,
    db: Session = Depends(get_db),
) -> OfferTrendItem:
    return get_offer_trend_summary(db, dealership_id=dealership_id, vehicle_key=vehicle_id)


@app.post("/offers/trends/bulk", response_model=OfferTrendsBulkResponse)
def offer_trends_bulk(payload: OfferTrendsBulkRequest, db: Session = Depends(get_db)) -> OfferTrendsBulkResponse:
    trends = [
        get_offer_trend_summary(db, dealership_id=item.dealership_id, vehicle_key=item.vehicle_id)
        for item in payload.offers
    ]
    return OfferTrendsBulkResponse(trends=trends)


@app.get("/offers/history", response_model=OfferHistoryResponse)
def offer_history(
    dealership_id: str,
    vehicle_id: str,
    limit: int = 90,
    db: Session = Depends(get_db),
) -> OfferHistoryResponse:
    points, first_seen_at, last_seen_at, days_on_market = get_offer_history(
        db,
        dealership_id=dealership_id,
        vehicle_key=vehicle_id,
        limit=max(1, min(limit, 365)),
    )
    return OfferHistoryResponse(
        dealership_id=dealership_id,
        vehicle_id=vehicle_id,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        days_on_market=days_on_market,
        points=points,
    )


@app.post("/offers/rank", response_model=OfferRankResponse)
def rank_offers(payload: OfferRankRequest) -> OfferRankResponse:
    ranked: list[RankedOffer] = []

    for offer in payload.offers:
        budget = payload.budget_otd
        over_budget = max(0.0, offer.otd_price - budget)
        over_budget_pct = (over_budget / budget) * 100 if budget else 0.0

        price_distance_pct = abs(offer.otd_price - budget) / budget * 100
        price_score = max(0.0, 100.0 - price_distance_pct)
        fee_score = max(0.0, 100.0 - min(100.0, (offer.fees / 2000.0) * 100.0))
        distance_score = max(0.0, 100.0 - min(100.0, (offer.distance_miles / 100.0) * 100.0))
        adjustment_score = max(0.0, 100.0 - min(100.0, (offer.market_adjustment / 5000.0) * 100.0))

        dom_days = float(offer.days_on_market or 0)
        dom_score = max(0.0, min(100.0, (dom_days / 50.0) * 100.0))

        drop_7d = float(offer.price_drop_7d or 0.0)
        drop_30d = float(offer.price_drop_30d or 0.0)
        trend_score = max(0.0, min(100.0, ((drop_7d / 1000.0) * 55.0) + ((drop_30d / 3000.0) * 45.0)))

        weighted = (
            (price_score * 0.45)
            + (offer.specs_score * 0.22)
            + (fee_score * 0.10)
            + (distance_score * 0.05)
            + (adjustment_score * 0.05)
            + (dom_score * 0.06)
            + (trend_score * 0.07)
        )

        total_score = max(0.0, weighted - (over_budget_pct * 0.30))
        breakdown = {
            "price_score": round(price_score, 2),
            "specs_score": round(offer.specs_score, 2),
            "fee_score": round(fee_score, 2),
            "distance_score": round(distance_score, 2),
            "adjustment_score": round(adjustment_score, 2),
            "dom_score": round(dom_score, 2),
            "trend_score": round(trend_score, 2),
            "over_budget_penalty": round(over_budget_pct * 0.30, 2),
        }

        ranked.append(
            RankedOffer(
                rank=1,
                offer=offer,
                score=round(total_score, 2),
                score_breakdown=breakdown,
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)

    for idx, item in enumerate(ranked, start=1):
        item.rank = idx

    return OfferRankResponse(ranked_offers=ranked)


@app.post("/negotiations/start", response_model=StartNegotiationResponse)
def start_negotiation(payload: StartNegotiationRequest, db: Session = Depends(get_db)) -> StartNegotiationResponse:
    session = create_session(db, payload)

    playbook_key, playbook_policy = resolve_playbook(payload.playbook)
    effective_target_otd = apply_playbook_target(payload.target_otd, playbook_policy)

    strategy = run_negotiation_strategy(
        user_name=payload.user_name,
        target_otd=effective_target_otd,
        dealer_otd=payload.dealer_otd,
        competitor_best_otd=payload.competitor_best_otd,
        offer_rank=payload.offer_rank,
        days_on_market=payload.days_on_market,
        price_drop_30d=payload.price_drop_30d,
    )

    tone = str(playbook_policy.get("tone", "neutral"))
    strategy["response_text"] = apply_playbook_tone(strategy["response_text"], tone)
    policy_snapshot = build_playbook_policy_snapshot(
        playbook_key=playbook_key,
        policy=playbook_policy,
        input_target_otd=float(payload.target_otd),
    )

    session.playbook = playbook_key
    session.playbook_policy = policy_snapshot

    message = add_message(
        db=db,
        session_id=session.id,
        direction="outbound",
        channel="email",
        sender_identity=f"AI Assistant representing {payload.user_name}",
        body=strategy["response_text"],
        metadata={
            "action": strategy["action"],
            "anchor_otd": strategy["anchor_otd"],
            "rationale": strategy["rationale"],
            "saved_search_id": payload.saved_search_id,
            "offer_id": payload.offer_id,
            "offer_rank": payload.offer_rank,
            "days_on_market": payload.days_on_market,
            "price_drop_7d": payload.price_drop_7d,
            "price_drop_30d": payload.price_drop_30d,
            "playbook_policy": policy_snapshot,
        },
    )
    db.commit()
    delivery = {"status": "not_sent", "reason": "missing_dealer_contact"}
    try:
        if payload.dealership_email:
            delivery = send_negotiation_email(payload.dealership_email, strategy["response_text"])
        elif payload.dealership_phone:
            delivery = send_negotiation_sms(payload.dealership_phone, strategy["response_text"])
    except Exception as exc:
        delivery = {"status": "error", "reason": str(exc)}

    publish_session_event(
        session_id=session.id,
        event_type="negotiation.session.started",
        payload={"message_id": message.id, "action": strategy["action"], "delivery": delivery, "playbook": playbook_key},
    )

    decision = NegotiationDecision(
        action=strategy["action"],
        response_text=strategy["response_text"],
        anchor_otd=strategy["anchor_otd"],
        rationale=(
            f"{strategy['rationale']} "
            f"Playbook={playbook_key}; max_rounds={policy_snapshot['max_rounds']}; "
            f"concession_step=${policy_snapshot['concession_step']:,.0f}; "
            f"walk_away_buffer=${policy_snapshot['walk_away_buffer']:,.0f}."
        ),
    )
    return StartNegotiationResponse(session_id=session.id, status="active", decision=decision)


@app.get("/negotiations", response_model=list[NegotiationSessionOut])
def get_negotiations(db: Session = Depends(get_db)) -> list[NegotiationSessionOut]:
    sessions = list_sessions(db)
    return [to_session_out(session) for session in sessions]


@app.get("/negotiations/{session_id}", response_model=NegotiationSessionOut)
def get_negotiation(session_id: str, db: Session = Depends(get_db)) -> NegotiationSessionOut:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")
    return to_session_out(session)


@app.patch("/negotiations/{session_id}/status", response_model=NegotiationSessionOut)
def update_negotiation_status(
    session_id: str,
    payload: NegotiationStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> NegotiationSessionOut:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    previous_status = _normalize_status(session.status)
    next_status = _normalize_status(payload.status)
    if not _can_transition_status(previous_status, next_status):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {previous_status or 'unknown'} -> {next_status or 'unknown'}",
        )

    ok = update_session_status(db, session_id=session_id, status=next_status)
    if not ok:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    updated = get_session_with_messages(db, session_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    publish_session_event(
        session_id=session_id,
        event_type="negotiation.status.updated",
        payload={
            "previous_status": previous_status,
            "status": next_status,
            "source": (payload.source or "api").strip() or "api",
            "actor": (payload.actor or "operator").strip() or "operator",
        },
    )

    return to_session_out(updated)

@app.patch("/negotiations/{session_id}", response_model=NegotiationSessionOut)
def update_negotiation_session(
    session_id: str,
    payload: NegotiationSessionUpdateRequest,
    db: Session = Depends(get_db),
) -> NegotiationSessionOut:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")
    if (session.status or "").strip().lower() in {"closed", "failed"}:
        raise HTTPException(status_code=409, detail="Playbook cannot be updated for closed/failed sessions")

    previous_playbook = getattr(session, "playbook", None)
    previous_playbook_policy = getattr(session, "playbook_policy", None)

    playbook_key, playbook_policy = resolve_playbook(payload.playbook)
    input_target = float(session.best_offer_otd) if session.best_offer_otd is not None else None
    policy_snapshot = build_playbook_policy_snapshot(
        playbook_key=playbook_key,
        policy=playbook_policy,
        input_target_otd=input_target,
    )

    ok = update_session_playbook(
        db,
        session_id=session_id,
        playbook=playbook_key,
        playbook_policy=policy_snapshot,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    updated = get_session_with_messages(db, session_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    publish_session_event(
        session_id=session_id,
        event_type="negotiation.playbook.updated",
        payload={
            "previous_playbook": previous_playbook,
            "previous_playbook_policy": previous_playbook_policy,
            "playbook": playbook_key,
            "playbook_policy": policy_snapshot,
        },
    )

    return to_session_out(updated)

@app.patch("/negotiations/{session_id}/autopilot", response_model=NegotiationSessionOut)
def update_negotiation_autopilot(
    session_id: str,
    payload: AutopilotUpdateRequest,
    db: Session = Depends(get_db),
) -> NegotiationSessionOut:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    requested_mode = (payload.mode or "").strip().lower() or None
    if requested_mode and requested_mode not in {"manual", "autopilot", "assist"}:
        raise HTTPException(status_code=400, detail="Invalid autopilot mode")

    ok = update_session_autopilot(
        db,
        session_id=session_id,
        enabled=payload.enabled,
        mode=requested_mode,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    updated = get_session_with_messages(db, session_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    publish_session_event(
        session_id=session_id,
        event_type="negotiation.autopilot.updated",
        payload={
            "enabled": bool(updated.autopilot_enabled),
            "mode": updated.autopilot_mode,
        },
    )
    return to_session_out(updated)

@app.post("/negotiations/{session_id}/autonomous-round", response_model=EnqueueRoundResponse)
def enqueue_autonomous_round(
    session_id: str,
    payload: EnqueueRoundRequest,
    db: Session = Depends(get_db),
) -> EnqueueRoundResponse:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    session_state = _normalize_status(session.status)
    if session_state in {"closed", "failed"}:
        raise HTTPException(status_code=409, detail="Cannot queue round for closed/failed sessions")
    if _is_job_active(session.last_job_status):
        raise HTTPException(status_code=409, detail="A round is already queued or running for this session")

    queue = get_queue()
    job = queue.enqueue(run_autonomous_round, session_id, payload.user_name)
    publish_session_event(
        session_id=session_id,
        event_type="negotiation.round.queued",
        payload={"job_id": job.id, "queue": queue.name},
    )
    update_session_status(
        db,
        session_id=session_id,
        status="queued",
        last_job_id=job.id,
        last_job_status="queued",
    )
    return EnqueueRoundResponse(
        session_id=session_id,
        job_id=job.id,
        queue=queue.name,
        status="queued",
    )


@app.post("/negotiations/{session_id}/simulate-reply")
def simulate_inbound_reply(
    session_id: str,
    payload: SimulatedInboundRequest,
    db: Session = Depends(get_db),
) -> dict:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    channel = payload.channel.strip().lower()
    if channel not in {"email", "sms", "voice"}:
        channel = "email"

    sender_identity = (payload.sender_identity or "").strip()
    if not sender_identity:
        sender_identity = "dealer@example.com" if channel == "email" else "+10000000000"

    message = add_message(
        db=db,
        session_id=session_id,
        direction="inbound",
        channel=channel,
        sender_identity=sender_identity,
        body=payload.body.strip(),
        metadata={"source": "ui-simulated"},
    )
    db.commit()
    update_session_status(db, session_id=session_id, status="responded")

    publish_session_event(
        session_id=session_id,
        event_type="negotiation.message.received",
        payload={
            "message_id": message.id,
            "channel": channel,
            "sender": sender_identity,
            "body": message.body,
            "source": "ui-simulated",
        },
    )

    job_id: str | None = None
    queue_name: str | None = None
    autopilot_triggered = False
    skip_reason: str | None = None

    if bool(session.autopilot_enabled):
        active_job_state = (session.last_job_status or "").strip().lower()
        if active_job_state in {"queued", "started", "scheduled", "deferred", "running"}:
            skip_reason = "job_in_progress"
        else:
            queue = get_queue()
            ai_user_name = (payload.user_name or "").strip() or "Buyer"
            job = queue.enqueue(run_autonomous_round, session_id, ai_user_name)
            job_id = job.id
            queue_name = queue.name
            autopilot_triggered = True
            update_session_status(
                db,
                session_id=session_id,
                status="queued",
                last_job_id=job.id,
                last_job_status="queued",
            )
            publish_session_event(
                session_id=session_id,
                event_type="negotiation.round.queued",
                payload={"job_id": job.id, "queue": queue.name, "source": "autopilot"},
            )

    return {
        "status": "ok",
        "message_id": message.id,
        "session_id": session_id,
        "autopilot_enabled": bool(session.autopilot_enabled),
        "autopilot_mode": session.autopilot_mode,
        "autopilot_triggered": autopilot_triggered,
        "job_id": job_id,
        "queue": queue_name,
        "skip_reason": skip_reason,
    }

@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    queue = get_queue()
    try:
        job = Job.fetch(job_id, connection=queue.connection)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job not found")

    status = job.get_status(refresh=True) or "unknown"
    kwargs = job.kwargs if isinstance(job.kwargs, dict) else {}

    session_id = str(job.args[0]) if job.args else kwargs.get("session_id")
    mapped = {
        "queued": "queued",
        "scheduled": "queued",
        "deferred": "queued",
        "started": "running",
        "failed": "failed",
        "stopped": "failed",
        "canceled": "closed",
    }
    session_status = mapped.get(status)

    if session_id:
        db = SessionLocal()
        try:
            if session_status is None:
                update_session_job_metadata(
                    db,
                    session_id=session_id,
                    last_job_id=job.id,
                    last_job_status=status,
                )
            else:
                update_session_status(
                    db,
                    session_id=session_id,
                    status=session_status,
                    last_job_id=job.id,
                    last_job_status=status,
                )
        finally:
            db.close()

    return JobStatusResponse(
        job_id=job.id,
        status=status,
        queue=job.origin,
        enqueued_at=job.enqueued_at.isoformat() if job.enqueued_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        ended_at=job.ended_at.isoformat() if job.ended_at else None,
        session_id=session_id,
        error=job.exc_info,
    )


def to_session_out(session) -> NegotiationSessionOut:
    return NegotiationSessionOut(
        id=session.id,
        user_id=session.user_id,
        saved_search_id=session.saved_search_id,
        offer_id=session.offer_id,
        dealership_id=session.dealership_id,
        dealership_name=session.dealer.name if session.dealer else None,
        vehicle_id=session.vehicle_id,
        vehicle_label=session.vehicle_label,
        status=session.status,
        best_offer_otd=float(session.best_offer_otd) if session.best_offer_otd is not None else None,
        autopilot_enabled=bool(session.autopilot_enabled),
        autopilot_mode=session.autopilot_mode,
        playbook=getattr(session, "playbook", "balanced") or "balanced",
        playbook_policy=getattr(session, "playbook_policy", None),
        last_job_id=session.last_job_id,
        last_job_status=session.last_job_status,
        last_job_at=session.last_job_at.isoformat() if session.last_job_at else None,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        messages=[
            NegotiationMessageOut(
                id=message.id,
                direction=message.direction,
                channel=message.channel,
                sender_identity=message.sender_identity,
                body=message.body,
                created_at=message.created_at.isoformat(),
                metadata=message.message_metadata,
            )
            for message in session.messages
        ],
    )







































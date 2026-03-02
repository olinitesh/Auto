from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from autohaggle_shared.communication_client import send_negotiation_email, send_negotiation_sms
from autohaggle_shared.database import get_db, init_db
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.jobs import run_autonomous_round
from autohaggle_shared.negotiation import run_negotiation_strategy
from autohaggle_shared.queueing import get_queue
from autohaggle_shared.repository import (
    add_message,
    create_session,
    get_offer_history,
    get_offer_trend_signals,
    get_session_with_messages,
    list_sessions,
    upsert_offer_observations,
)
from autohaggle_shared.schemas import (
    DealerOffer,
    DealerSiteInput,
    EnqueueRoundRequest,
    EnqueueRoundResponse,
    HealthResponse,
    NegotiationDecision,
    NegotiationMessageOut,
    NegotiationSessionOut,
    OfferHistoryResponse,
    OfferRankRequest,
    OfferRankResponse,
    OfferSearchRequest,
    OfferSearchResponse,
    RankedOffer,
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


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


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
        trend = get_offer_trend_signals(
            db,
            dealership_id=str(item.get("dealership_id") or ""),
            vehicle_key=str(item.get("vehicle_id") or ""),
        )
        item["price_drop_7d"] = trend.get("price_drop_7d")
        item["price_drop_30d"] = trend.get("price_drop_30d")

    offers = [DealerOffer(**item) for item in raw_offers]
    return OfferSearchResponse(offers=offers)


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
    strategy = run_negotiation_strategy(
        user_name=payload.user_name,
        target_otd=payload.target_otd,
        dealer_otd=payload.dealer_otd,
        competitor_best_otd=payload.competitor_best_otd,
    )

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
        payload={"message_id": message.id, "action": strategy["action"], "delivery": delivery},
    )

    decision = NegotiationDecision(
        action=strategy["action"],
        response_text=strategy["response_text"],
        anchor_otd=strategy["anchor_otd"],
        rationale=strategy["rationale"],
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


@app.post("/negotiations/{session_id}/autonomous-round", response_model=EnqueueRoundResponse)
def enqueue_autonomous_round(
    session_id: str,
    payload: EnqueueRoundRequest,
    db: Session = Depends(get_db),
) -> EnqueueRoundResponse:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    queue = get_queue()
    job = queue.enqueue(run_autonomous_round, session_id, payload.user_name)
    publish_session_event(
        session_id=session_id,
        event_type="negotiation.round.queued",
        payload={"job_id": job.id, "queue": queue.name},
    )
    return EnqueueRoundResponse(
        session_id=session_id,
        job_id=job.id,
        queue=queue.name,
        status="queued",
    )


def to_session_out(session) -> NegotiationSessionOut:
    return NegotiationSessionOut(
        id=session.id,
        user_id=session.user_id,
        dealership_id=session.dealership_id,
        vehicle_id=session.vehicle_id,
        status=session.status,
        best_offer_otd=float(session.best_offer_otd) if session.best_offer_otd is not None else None,
        messages=[
            NegotiationMessageOut(
                id=message.id,
                direction=message.direction,
                channel=message.channel,
                sender_identity=message.sender_identity,
                body=message.body,
                created_at=message.created_at.isoformat(),
            )
            for message in session.messages
        ],
    )

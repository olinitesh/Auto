from contextlib import asynccontextmanager
import imaplib
import re
from email import message_from_bytes, policy
from email.utils import parseaddr

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from autohaggle_shared.config import settings
from autohaggle_shared.database import get_db, init_db
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.jobs import run_autonomous_round
from autohaggle_shared.models import Dealer, NegotiationSession
from autohaggle_shared.queueing import get_queue
from autohaggle_shared.repository import add_message, get_session_with_messages, update_session_status
from providers.gmail_provider import send_email_gmail
from providers.sendgrid_provider import EmailResult, send_email
from providers.twilio_provider import SmsResult, VoiceResult, place_call, send_sms

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_SESSION_HINT_RE = re.compile(
    r"(?:session(?:_id)?|negotiation)\s*[:#=\-\s]*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AutoHaggle Communication Service", version="0.1.0", lifespan=lifespan)


class EmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str


class EmailTestRequest(BaseModel):
    to_email: EmailStr
    subject: str = "AutoHaggle Email Provider Test"
    body: str = "This is a diagnostic email from AutoHaggle communication-service."


class SmsRequest(BaseModel):
    to_number: str
    body: str


class VoiceRequest(BaseModel):
    to_number: str
    spoken_message: str


class TwilioInboundRequest(BaseModel):
    session_id: str
    from_number: str
    body: str
    message_sid: str | None = None


class SendGridInboundRequest(BaseModel):
    session_id: str
    from_email: EmailStr
    subject: str | None = None
    text: str
    message_id: str | None = None


class GmailPollRequest(BaseModel):
    mailbox: str = "INBOX"
    max_messages: int = Field(default=10, ge=1, le=100)
    unseen_only: bool = True


def _is_job_active(status: str | None) -> bool:
    return (status or "").strip().lower() in {"queued", "started", "scheduled", "deferred", "running"}


def _verify_webhook_secret(x_webhook_secret: str | None = Header(default=None)) -> None:
    expected = (settings.webhook_shared_secret or "").strip()
    if not expected:
        return
    if (x_webhook_secret or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _send_email_dispatch(to_email: str, subject: str, body: str) -> EmailResult:
    provider = (settings.email_provider or "sendgrid").strip().lower()
    if provider == "gmail":
        return send_email_gmail(to_email=to_email, subject=subject, body=body)
    if provider == "sendgrid":
        return send_email(to_email=to_email, subject=subject, body=body)
    if provider == "auto":
        result = send_email(to_email=to_email, subject=subject, body=body)
        if result.status == "dry_run":
            return send_email_gmail(to_email=to_email, subject=subject, body=body)
        return result
    raise HTTPException(status_code=400, detail=f"Unsupported email provider: {provider}")


def _extract_email_text(message) -> str:
    if message.is_multipart():
        text_parts: list[str] = []
        for part in message.walk():
            disposition = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            if (part.get_content_type() or "").lower() != "text/plain":
                continue

            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            try:
                text_parts.append(payload.decode(charset, errors="replace"))
            except LookupError:
                text_parts.append(payload.decode("utf-8", errors="replace"))

        if text_parts:
            return "\n".join(part.strip() for part in text_parts if part.strip()).strip()

    payload = message.get_payload(decode=True) or b""
    charset = message.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace").strip()
    except LookupError:
        return payload.decode("utf-8", errors="replace").strip()


def _extract_session_id(*values: str | None) -> str | None:
    for value in values:
        text = (value or "").strip()
        if not text:
            continue

        hinted = _SESSION_HINT_RE.search(text)
        if hinted:
            return hinted.group(1).lower()

    for value in values:
        text = (value or "").strip()
        if not text:
            continue

        generic = _UUID_RE.search(text)
        if generic:
            return generic.group(0).lower()

    return None


def _fetch_gmail_inbound_messages(*, mailbox: str, max_messages: int, unseen_only: bool) -> list[dict]:
    username = (settings.gmail_username or "").strip()
    app_password = (settings.gmail_app_password or "").strip()

    if not username or not app_password:
        raise HTTPException(status_code=400, detail="Gmail inbound polling is not configured")

    host = (settings.gmail_imap_host or "imap.gmail.com").strip() or "imap.gmail.com"
    port = int(settings.gmail_imap_port or 993)

    client = imaplib.IMAP4_SSL(host=host, port=port)
    try:
        login_status, _ = client.login(username, app_password)
        if login_status != "OK":
            raise HTTPException(status_code=502, detail="Gmail login failed")

        select_status, _ = client.select(mailbox, readonly=False)
        if select_status != "OK":
            raise HTTPException(status_code=400, detail=f"Gmail mailbox not found: {mailbox}")

        criteria = "UNSEEN" if unseen_only else "ALL"
        search_status, search_data = client.search(None, criteria)
        if search_status != "OK":
            raise HTTPException(status_code=502, detail="Gmail search failed")

        ids = [value for value in (search_data[0] or b"").split() if value]
        if not ids:
            return []

        selected_ids = ids[-max_messages:]
        fetched: list[dict] = []

        for raw_uid in selected_ids:
            fetch_status, parts = client.fetch(raw_uid, "(RFC822)")
            if fetch_status != "OK" or not parts:
                continue

            raw_message: bytes | None = None
            for part in parts:
                if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], (bytes, bytearray)):
                    raw_message = bytes(part[1])
                    break

            if not raw_message:
                continue

            parsed = message_from_bytes(raw_message, policy=policy.default)
            sender = parseaddr(str(parsed.get("From") or ""))[1].strip().lower()
            subject = str(parsed.get("Subject") or "").strip()
            message_id = str(parsed.get("Message-ID") or "").strip() or None
            in_reply_to = str(parsed.get("In-Reply-To") or "").strip() or None
            references = str(parsed.get("References") or "").strip() or None
            body = _extract_email_text(parsed)
            session_id = _extract_session_id(subject, in_reply_to, references, body)

            fetched.append(
                {
                    "uid": raw_uid.decode(errors="ignore"),
                    "from_email": sender,
                    "subject": subject,
                    "message_id": message_id,
                    "body": body,
                    "session_id": session_id,
                }
            )

        return fetched
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.logout()
        except Exception:
            pass


def _resolve_session_for_gmail_reply(*, db: Session, from_email: str | None, hinted_session_id: str | None):
    if hinted_session_id:
        session = get_session_with_messages(db, hinted_session_id)
        if session:
            return session

    sender = (from_email or "").strip().lower()
    if not sender:
        return None

    stmt = (
        select(NegotiationSession)
        .join(Dealer, NegotiationSession.dealership_id == Dealer.id)
        .where(func.lower(Dealer.email) == sender)
        .order_by(NegotiationSession.created_at.desc())
        .limit(1)
    )
    session = db.execute(stmt).scalars().first()
    if session is None:
        return None

    _ = list(session.messages)
    return session


def _post_inbound_session_actions(
    *,
    db: Session,
    session,
    session_id: str,
    message_id: str,
    channel: str,
    sender: str,
    body: str,
    source: str,
) -> dict:
    update_session_status(db, session_id=session_id, status="responded")

    publish_session_event(
        session_id=session_id,
        event_type="negotiation.message.received",
        payload={
            "message_id": message_id,
            "channel": channel,
            "sender": sender,
            "body": body,
            "source": source,
        },
    )

    job_id: str | None = None
    queue_name: str | None = None
    autopilot_triggered = False
    skip_reason: str | None = None

    if bool(getattr(session, "autopilot_enabled", False)):
        if _is_job_active(getattr(session, "last_job_status", None)):
            skip_reason = "job_in_progress"
        else:
            queue = get_queue()
            job = queue.enqueue(run_autonomous_round, session_id, "Buyer")
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
                payload={"job_id": job.id, "queue": queue.name, "source": source},
            )

    return {
        "autopilot_triggered": autopilot_triggered,
        "job_id": job_id,
        "queue": queue_name,
        "skip_reason": skip_reason,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "communication-service"}


@app.post("/send/email", response_model=EmailResult)
def send_email_route(payload: EmailRequest) -> EmailResult:
    return _send_email_dispatch(
        to_email=str(payload.to_email),
        subject=payload.subject,
        body=payload.body,
    )


@app.post("/send/email/test")
def send_email_test_route(payload: EmailTestRequest) -> dict:
    result = _send_email_dispatch(
        to_email=str(payload.to_email),
        subject=payload.subject,
        body=payload.body,
    )
    provider = (settings.email_provider or "sendgrid").strip().lower()
    return {
        "status": "ok",
        "provider": provider,
        "result": result.model_dump(),
        "diagnostics": {
            "sendgrid_configured": bool(settings.sendgrid_api_key and settings.sendgrid_from_email),
            "gmail_configured": bool(settings.gmail_username and settings.gmail_app_password),
            "webhook_secret_configured": bool(settings.webhook_shared_secret),
        },
    }


@app.post("/send/sms", response_model=SmsResult)
def send_sms_route(payload: SmsRequest) -> SmsResult:
    return send_sms(
        to_number=payload.to_number,
        body=payload.body,
    )


@app.post("/send/voice", response_model=VoiceResult)
def place_call_route(payload: VoiceRequest) -> VoiceResult:
    return place_call(
        to_number=payload.to_number,
        spoken_message=payload.spoken_message,
    )


@app.post("/webhooks/twilio/sms")
def inbound_twilio_sms(
    payload: TwilioInboundRequest,
    _: None = Depends(_verify_webhook_secret),
    db: Session = Depends(get_db),
) -> dict:
    session = get_session_with_messages(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    message = add_message(
        db=db,
        session_id=payload.session_id,
        direction="inbound",
        channel="sms",
        sender_identity=payload.from_number,
        body=payload.body,
        metadata={"message_sid": payload.message_sid, "provider": "twilio"},
    )
    db.commit()

    control = _post_inbound_session_actions(
        db=db,
        session=session,
        session_id=payload.session_id,
        message_id=message.id,
        channel="sms",
        sender=payload.from_number,
        body=payload.body,
        source="twilio-webhook",
    )
    return {"status": "ok", "message_id": message.id, **control}


@app.post("/webhooks/sendgrid/email")
def inbound_sendgrid_email(
    payload: SendGridInboundRequest,
    _: None = Depends(_verify_webhook_secret),
    db: Session = Depends(get_db),
) -> dict:
    session = get_session_with_messages(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    subject_line = f"Subject: {payload.subject}\n\n" if payload.subject else ""
    body = f"{subject_line}{payload.text}"
    message = add_message(
        db=db,
        session_id=payload.session_id,
        direction="inbound",
        channel="email",
        sender_identity=str(payload.from_email),
        body=body,
        metadata={"message_id": payload.message_id, "provider": "sendgrid"},
    )
    db.commit()

    control = _post_inbound_session_actions(
        db=db,
        session=session,
        session_id=payload.session_id,
        message_id=message.id,
        channel="email",
        sender=str(payload.from_email),
        body=body,
        source="sendgrid-webhook",
    )
    return {"status": "ok", "message_id": message.id, **control}


@app.post("/webhooks/gmail/poll")
def inbound_gmail_poll(
    payload: GmailPollRequest,
    _: None = Depends(_verify_webhook_secret),
    db: Session = Depends(get_db),
) -> dict:
    messages = _fetch_gmail_inbound_messages(
        mailbox=payload.mailbox,
        max_messages=payload.max_messages,
        unseen_only=payload.unseen_only,
    )

    processed: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    for item in messages:
        sender = str(item.get("from_email") or "").strip().lower()
        hinted_session_id = str(item.get("session_id") or "").strip() or None
        body_text = str(item.get("body") or "").strip()
        subject = str(item.get("subject") or "").strip()

        try:
            session = _resolve_session_for_gmail_reply(
                db=db,
                from_email=sender,
                hinted_session_id=hinted_session_id,
            )
            if session is None:
                skipped.append(
                    {
                        "uid": item.get("uid"),
                        "from_email": sender,
                        "subject": subject,
                        "hinted_session_id": hinted_session_id,
                        "reason": "session_not_found",
                    }
                )
                continue

            body = f"Subject: {subject}\n\n{body_text}" if subject else body_text
            message = add_message(
                db=db,
                session_id=session.id,
                direction="inbound",
                channel="email",
                sender_identity=sender or "gmail-unknown",
                body=body,
                metadata={
                    "message_id": item.get("message_id"),
                    "provider": "gmail-imap",
                    "uid": item.get("uid"),
                    "hinted_session_id": hinted_session_id,
                },
            )
            db.commit()

            control = _post_inbound_session_actions(
                db=db,
                session=session,
                session_id=session.id,
                message_id=message.id,
                channel="email",
                sender=sender or "gmail-unknown",
                body=body,
                source="gmail-imap-poll",
            )
            processed.append(
                {
                    "uid": item.get("uid"),
                    "session_id": session.id,
                    "message_id": message.id,
                    **control,
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "uid": item.get("uid"),
                    "from_email": sender,
                    "subject": subject,
                    "error": str(exc),
                }
            )

    return {
        "status": "ok",
        "provider": "gmail-imap",
        "fetched": len(messages),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }

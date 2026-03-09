from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from autohaggle_shared.config import settings
from autohaggle_shared.database import get_db, init_db
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.jobs import run_autonomous_round
from autohaggle_shared.queueing import get_queue
from autohaggle_shared.repository import add_message, get_session_with_messages, update_session_status
from providers.gmail_provider import send_email_gmail
from providers.sendgrid_provider import EmailResult, send_email
from providers.twilio_provider import SmsResult, VoiceResult, place_call, send_sms


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

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from autohaggle_shared.database import get_db, init_db
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.repository import add_message, get_session_with_messages
from providers.sendgrid_provider import EmailResult, send_email
from providers.twilio_provider import SmsResult, VoiceResult, place_call, send_sms

app = FastAPI(title="AutoHaggle Communication Service", version="0.1.0")


class EmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str


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


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "communication-service"}


@app.post("/send/email", response_model=EmailResult)
def send_email_route(payload: EmailRequest) -> EmailResult:
    return send_email(
        to_email=payload.to_email,
        subject=payload.subject,
        body=payload.body,
    )


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
def inbound_twilio_sms(payload: TwilioInboundRequest, db: Session = Depends(get_db)) -> dict:
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
    publish_session_event(
        session_id=payload.session_id,
        event_type="negotiation.message.received",
        payload={
            "message_id": message.id,
            "channel": "sms",
            "sender": payload.from_number,
            "body": payload.body,
        },
    )
    return {"status": "ok", "message_id": message.id}


@app.post("/webhooks/sendgrid/email")
def inbound_sendgrid_email(payload: SendGridInboundRequest, db: Session = Depends(get_db)) -> dict:
    session = get_session_with_messages(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    subject_line = f"Subject: {payload.subject}\n\n" if payload.subject else ""
    message = add_message(
        db=db,
        session_id=payload.session_id,
        direction="inbound",
        channel="email",
        sender_identity=str(payload.from_email),
        body=f"{subject_line}{payload.text}",
        metadata={"message_id": payload.message_id, "provider": "sendgrid"},
    )
    db.commit()
    publish_session_event(
        session_id=payload.session_id,
        event_type="negotiation.message.received",
        payload={
            "message_id": message.id,
            "channel": "email",
            "sender": str(payload.from_email),
        },
    )
    return {"status": "ok", "message_id": message.id}


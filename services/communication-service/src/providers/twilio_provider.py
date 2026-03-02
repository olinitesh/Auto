from pydantic import BaseModel
from twilio.rest import Client

from autohaggle_shared.config import settings


class SmsResult(BaseModel):
    status: str
    provider_message_id: str | None
    detail: str


class VoiceResult(BaseModel):
    status: str
    provider_call_id: str | None
    detail: str


def send_sms(to_number: str, body: str) -> SmsResult:
    if (
        not settings.twilio_account_sid
        or not settings.twilio_auth_token
        or not settings.twilio_phone_number
    ):
        return SmsResult(
            status="dry_run",
            provider_message_id=None,
            detail="Twilio credentials not configured; no external SMS sent.",
        )

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        from_=settings.twilio_phone_number,
        to=to_number,
        body=body,
    )
    return SmsResult(
        status="sent",
        provider_message_id=message.sid,
        detail=f"Twilio status={message.status}",
    )


def place_call(to_number: str, spoken_message: str) -> VoiceResult:
    if (
        not settings.twilio_account_sid
        or not settings.twilio_auth_token
        or not settings.twilio_phone_number
    ):
        return VoiceResult(
            status="dry_run",
            provider_call_id=None,
            detail="Twilio credentials not configured; no external call placed.",
        )

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    twiml = f"<Response><Say>{spoken_message}</Say></Response>"
    call = client.calls.create(
        from_=settings.twilio_phone_number,
        to=to_number,
        twiml=twiml,
    )
    return VoiceResult(
        status="sent",
        provider_call_id=call.sid,
        detail=f"Twilio call status={call.status}",
    )

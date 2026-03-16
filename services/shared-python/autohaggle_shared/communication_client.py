import httpx

from autohaggle_shared.config import settings


def send_negotiation_email(to_email: str, body: str, session_id: str | None = None) -> dict:
    subject = "OTD Pricing Request - Ready to Buy Today"
    if session_id:
        subject = f"{subject} [Session: {session_id}]"

    payload = {
        "to_email": to_email,
        "subject": subject,
        "body": body,
    }
    response = httpx.post(f"{settings.communication_service_url}/send/email", json=payload, timeout=15)
    if response.status_code >= 400:
        detail = response.text.strip()
        raise RuntimeError(
            f"Communication email send failed ({response.status_code}): {detail or 'no response body'}"
        )
    return response.json()


def send_negotiation_sms(to_number: str, body: str) -> dict:
    payload = {"to_number": to_number, "body": body}
    response = httpx.post(f"{settings.communication_service_url}/send/sms", json=payload, timeout=15)
    response.raise_for_status()
    return response.json()
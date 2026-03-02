import httpx

from autohaggle_shared.config import settings


def send_negotiation_email(to_email: str, body: str) -> dict:
    payload = {
        "to_email": to_email,
        "subject": "OTD Pricing Request - Ready to Buy Today",
        "body": body,
    }
    response = httpx.post(f"{settings.communication_service_url}/send/email", json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def send_negotiation_sms(to_number: str, body: str) -> dict:
    payload = {"to_number": to_number, "body": body}
    response = httpx.post(f"{settings.communication_service_url}/send/sms", json=payload, timeout=15)
    response.raise_for_status()
    return response.json()

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pydantic import BaseModel

from autohaggle_shared.config import settings


class EmailResult(BaseModel):
    status: str
    provider_message_id: str | None
    detail: str


def send_email(to_email: str, subject: str, body: str) -> EmailResult:
    if not settings.sendgrid_api_key or not settings.sendgrid_from_email:
        return EmailResult(
            status="dry_run",
            provider_message_id=None,
            detail="SendGrid credentials not configured; no external email sent.",
        )

    message = Mail(
        from_email=settings.sendgrid_from_email,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    client = SendGridAPIClient(settings.sendgrid_api_key)
    response = client.send(message)
    provider_id = response.headers.get("X-Message-Id")
    return EmailResult(
        status="sent",
        provider_message_id=provider_id,
        detail=f"SendGrid status={response.status_code}",
    )

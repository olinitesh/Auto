import smtplib
from email.message import EmailMessage

from autohaggle_shared.config import settings
from providers.sendgrid_provider import EmailResult


def send_email_gmail(to_email: str, subject: str, body: str) -> EmailResult:
    username = (settings.gmail_username or "").strip()
    app_password = (settings.gmail_app_password or "").strip()
    from_email = (settings.gmail_from_email or username).strip()

    if not username or not app_password or not from_email:
        return EmailResult(
            status="dry_run",
            provider_message_id=None,
            detail="Gmail credentials not configured; no external email sent.",
        )

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.gmail_smtp_host, int(settings.gmail_smtp_port), timeout=20) as client:
            client.ehlo()
            client.starttls()
            client.login(username, app_password)
            client.send_message(message)
        return EmailResult(
            status="sent",
            provider_message_id=message.get("Message-ID"),
            detail=f"Gmail SMTP host={settings.gmail_smtp_host} port={settings.gmail_smtp_port}",
        )
    except Exception as exc:
        return EmailResult(
            status="error",
            provider_message_id=None,
            detail=f"Gmail send failed: {exc}",
        )

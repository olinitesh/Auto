from pathlib import Path
import importlib.util
import sys


def load_communication_module():
    root = Path(__file__).resolve().parents[2]
    communication_src = root / "services" / "communication-service" / "src"
    shared_src = root / "services" / "shared-python"

    for entry in [str(communication_src), str(shared_src)]:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    path = communication_src / "main.py"
    spec = importlib.util.spec_from_file_location("communication_main_for_email_provider_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load communication main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_email_route_uses_gmail_when_provider_is_gmail(monkeypatch) -> None:
    communication_main = load_communication_module()
    monkeypatch.setattr(communication_main.settings, "email_provider", "gmail", raising=False)
    monkeypatch.setattr(
        communication_main,
        "send_email_gmail",
        lambda **kwargs: communication_main.EmailResult(status="sent", provider_message_id="g1", detail="gmail"),
    )
    monkeypatch.setattr(
        communication_main,
        "send_email",
        lambda **kwargs: communication_main.EmailResult(status="error", provider_message_id=None, detail="should-not-be-used"),
    )

    result = communication_main.send_email_route(
        communication_main.EmailRequest(to_email="dealer@example.com", subject="Hello", body="Body")
    )

    assert result.status == "sent"
    assert result.provider_message_id == "g1"


def test_email_route_auto_falls_back_to_gmail_when_sendgrid_dry_run(monkeypatch) -> None:
    communication_main = load_communication_module()
    monkeypatch.setattr(communication_main.settings, "email_provider", "auto", raising=False)
    monkeypatch.setattr(
        communication_main,
        "send_email",
        lambda **kwargs: communication_main.EmailResult(status="dry_run", provider_message_id=None, detail="sendgrid dry"),
    )
    monkeypatch.setattr(
        communication_main,
        "send_email_gmail",
        lambda **kwargs: communication_main.EmailResult(status="sent", provider_message_id="g2", detail="gmail"),
    )

    result = communication_main.send_email_route(
        communication_main.EmailRequest(to_email="dealer@example.com", subject="Hello", body="Body")
    )

    assert result.status == "sent"
    assert result.provider_message_id == "g2"


def test_email_route_sendgrid_default(monkeypatch) -> None:
    communication_main = load_communication_module()
    monkeypatch.setattr(communication_main.settings, "email_provider", "sendgrid", raising=False)
    monkeypatch.setattr(
        communication_main,
        "send_email",
        lambda **kwargs: communication_main.EmailResult(status="sent", provider_message_id="sg1", detail="sendgrid"),
    )

    result = communication_main.send_email_route(
        communication_main.EmailRequest(to_email="dealer@example.com", subject="Hello", body="Body")
    )

    assert result.status == "sent"
    assert result.provider_message_id == "sg1"

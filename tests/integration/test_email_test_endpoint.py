from pathlib import Path
import importlib.util
import sys

from fastapi.testclient import TestClient


def load_communication_module():
    root = Path(__file__).resolve().parents[2]
    communication_src = root / "services" / "communication-service" / "src"
    shared_src = root / "services" / "shared-python"

    for entry in [str(communication_src), str(shared_src)]:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    path = communication_src / "main.py"
    spec = importlib.util.spec_from_file_location("communication_main_for_email_test_endpoint", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load communication main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_send_email_test_endpoint_returns_diagnostics(monkeypatch) -> None:
    communication_main = load_communication_module()
    communication_main.init_db = lambda: None

    monkeypatch.setattr(communication_main.settings, "email_provider", "gmail", raising=False)
    monkeypatch.setattr(communication_main.settings, "sendgrid_api_key", None, raising=False)
    monkeypatch.setattr(communication_main.settings, "sendgrid_from_email", None, raising=False)
    monkeypatch.setattr(communication_main.settings, "gmail_username", "user@gmail.com", raising=False)
    monkeypatch.setattr(communication_main.settings, "gmail_app_password", "app-pass", raising=False)
    monkeypatch.setattr(communication_main.settings, "webhook_shared_secret", "secret", raising=False)
    monkeypatch.setattr(
        communication_main,
        "_send_email_dispatch",
        lambda **kwargs: communication_main.EmailResult(status="sent", provider_message_id="gdiag", detail="ok"),
    )

    with TestClient(communication_main.app) as client:
        response = client.post(
            "/send/email/test",
            json={
                "to_email": "dealer@example.com",
                "subject": "diag",
                "body": "hello",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["provider"] == "gmail"
    assert payload["result"]["status"] == "sent"
    assert payload["diagnostics"]["sendgrid_configured"] is False
    assert payload["diagnostics"]["gmail_configured"] is True
    assert payload["diagnostics"]["webhook_secret_configured"] is True


def test_send_email_test_endpoint_rejects_invalid_provider(monkeypatch) -> None:
    communication_main = load_communication_module()
    communication_main.init_db = lambda: None
    monkeypatch.setattr(communication_main.settings, "email_provider", "invalid", raising=False)

    with TestClient(communication_main.app) as client:
        response = client.post(
            "/send/email/test",
            json={
                "to_email": "dealer@example.com",
            },
        )

    assert response.status_code == 400
    assert "Unsupported email provider" in response.json()["detail"]

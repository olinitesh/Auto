from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

from fastapi.testclient import TestClient


class FakeDb:
    def commit(self) -> None:
        return None


def load_communication_module():
    root = Path(__file__).resolve().parents[2]
    communication_src = root / "services" / "communication-service" / "src"
    shared_src = root / "services" / "shared-python"

    for entry in [str(communication_src), str(shared_src)]:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    path = communication_src / "main.py"
    spec = importlib.util.spec_from_file_location("communication_main_for_gmail_poll_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load communication main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client_for(communication_main):
    communication_main.init_db = lambda: None
    communication_main.settings.webhook_shared_secret = None

    def fake_get_db():
        yield FakeDb()

    communication_main.app.dependency_overrides[communication_main.get_db] = fake_get_db
    return TestClient(communication_main.app)


def test_gmail_poll_requires_configuration(monkeypatch) -> None:
    communication_main = load_communication_module()

    monkeypatch.setattr(communication_main.settings, "gmail_username", None, raising=False)
    monkeypatch.setattr(communication_main.settings, "gmail_app_password", None, raising=False)

    with _client_for(communication_main) as client:
        response = client.post(
            "/webhooks/gmail/poll",
            json={"mailbox": "INBOX", "max_messages": 5, "unseen_only": True},
        )

    communication_main.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "not configured" in response.text.lower()


def test_gmail_poll_processes_and_skips_messages(monkeypatch) -> None:
    communication_main = load_communication_module()

    fake_messages = [
        {
            "uid": "101",
            "from_email": "dealer@example.com",
            "subject": "Re: OTD [Session: a77a539b-38b8-4610-ae0d-59799a21c246]",
            "message_id": "msg-101",
            "body": "We can do 31,200 OTD.",
            "session_id": "a77a539b-38b8-4610-ae0d-59799a21c246",
        },
        {
            "uid": "102",
            "from_email": "unknown@example.com",
            "subject": "Re: quote",
            "message_id": "msg-102",
            "body": "Hello",
            "session_id": None,
        },
    ]

    monkeypatch.setattr(
        communication_main,
        "_fetch_gmail_inbound_messages",
        lambda **kwargs: fake_messages,
    )

    session = SimpleNamespace(id="a77a539b-38b8-4610-ae0d-59799a21c246", autopilot_enabled=False, last_job_status=None)

    def fake_resolve_session_for_gmail_reply(*, db, from_email, hinted_session_id):
        if from_email == "dealer@example.com":
            return session
        return None

    monkeypatch.setattr(
        communication_main,
        "_resolve_session_for_gmail_reply",
        fake_resolve_session_for_gmail_reply,
    )
    monkeypatch.setattr(
        communication_main,
        "add_message",
        lambda **kwargs: SimpleNamespace(id="m-gmail-1"),
    )
    monkeypatch.setattr(
        communication_main,
        "_post_inbound_session_actions",
        lambda **kwargs: {
            "autopilot_triggered": False,
            "job_id": None,
            "queue": None,
            "skip_reason": None,
        },
    )

    with _client_for(communication_main) as client:
        response = client.post(
            "/webhooks/gmail/poll",
            json={"mailbox": "INBOX", "max_messages": 10, "unseen_only": True},
        )

    communication_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["fetched"] == 2
    assert len(payload["processed"]) == 1
    assert payload["processed"][0]["session_id"] == "a77a539b-38b8-4610-ae0d-59799a21c246"
    assert len(payload["skipped"]) == 1
    assert payload["skipped"][0]["reason"] == "session_not_found"
    assert payload["errors"] == []
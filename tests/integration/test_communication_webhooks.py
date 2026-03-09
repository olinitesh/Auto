from pathlib import Path
from types import SimpleNamespace
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
    spec = importlib.util.spec_from_file_location("communication_main_for_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load communication main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeDb:
    def commit(self) -> None:
        return None


def _client_for(communication_main):
    communication_main.init_db = lambda: None

    def fake_get_db():
        yield FakeDb()

    communication_main.app.dependency_overrides[communication_main.get_db] = fake_get_db
    return TestClient(communication_main.app)


def test_twilio_webhook_updates_status_and_queues_autopilot(monkeypatch) -> None:
    communication_main = load_communication_module()
    session = SimpleNamespace(id="s1", autopilot_enabled=True, last_job_status=None)
    status_calls: list[tuple[str, str | None]] = []
    emitted_events: list[str] = []

    monkeypatch.setattr(communication_main, "get_session_with_messages", lambda db, session_id: session)
    monkeypatch.setattr(
        communication_main,
        "add_message",
        lambda **kwargs: SimpleNamespace(id="m1", body=kwargs["body"]),
    )

    def fake_update_session_status(db, *, session_id, status, last_job_id=None, last_job_status=None):
        status_calls.append((status, last_job_status))
        if last_job_status is not None:
            session.last_job_status = last_job_status
        return True

    monkeypatch.setattr(communication_main, "update_session_status", fake_update_session_status)
    monkeypatch.setattr(communication_main, "publish_session_event", lambda **kwargs: emitted_events.append(kwargs["event_type"]))

    class FakeJob:
        id = "job-webhook-1"

    class FakeQueue:
        name = "default"

        def enqueue(self, fn, session_id, user_name):
            assert session_id == "s1"
            assert user_name == "Buyer"
            return FakeJob()

    monkeypatch.setattr(communication_main, "get_queue", lambda: FakeQueue())

    with _client_for(communication_main) as client:
        response = client.post(
            "/webhooks/twilio/sms",
            json={
                "session_id": "s1",
                "from_number": "+15555550100",
                "body": "Can you do better on OTD?",
                "message_sid": "SM123",
            },
        )

    communication_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["autopilot_triggered"] is True
    assert payload["job_id"] == "job-webhook-1"
    assert status_calls[0] == ("responded", None)
    assert status_calls[1] == ("queued", "queued")
    assert "negotiation.message.received" in emitted_events
    assert "negotiation.round.queued" in emitted_events


def test_sendgrid_webhook_skips_queue_when_job_already_active(monkeypatch) -> None:
    communication_main = load_communication_module()
    session = SimpleNamespace(id="s1", autopilot_enabled=True, last_job_status="running")
    status_calls: list[tuple[str, str | None]] = []
    emitted_events: list[str] = []

    monkeypatch.setattr(communication_main, "get_session_with_messages", lambda db, session_id: session)
    monkeypatch.setattr(
        communication_main,
        "add_message",
        lambda **kwargs: SimpleNamespace(id="m2", body=kwargs["body"]),
    )

    def fake_update_session_status(db, *, session_id, status, last_job_id=None, last_job_status=None):
        status_calls.append((status, last_job_status))
        return True

    monkeypatch.setattr(communication_main, "update_session_status", fake_update_session_status)
    monkeypatch.setattr(communication_main, "publish_session_event", lambda **kwargs: emitted_events.append(kwargs["event_type"]))

    def should_not_get_queue():
        raise AssertionError("queue should not be used when a job is already active")

    monkeypatch.setattr(communication_main, "get_queue", should_not_get_queue)

    with _client_for(communication_main) as client:
        response = client.post(
            "/webhooks/sendgrid/email",
            json={
                "session_id": "s1",
                "from_email": "dealer@example.com",
                "subject": "Re: Quote",
                "text": "We can reduce by 00.",
                "message_id": "SG123",
            },
        )

    communication_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["autopilot_triggered"] is False
    assert payload["skip_reason"] == "job_in_progress"
    assert status_calls == [("responded", None)]
    assert emitted_events == ["negotiation.message.received"]


def test_webhook_returns_404_when_session_not_found(monkeypatch) -> None:
    communication_main = load_communication_module()
    monkeypatch.setattr(communication_main, "get_session_with_messages", lambda db, session_id: None)

    with _client_for(communication_main) as client:
        response = client.post(
            "/webhooks/twilio/sms",
            json={
                "session_id": "missing",
                "from_number": "+15555550100",
                "body": "hello",
            },
        )

    communication_main.app.dependency_overrides.clear()
    assert response.status_code == 404


def test_webhook_secret_enforced_when_configured(monkeypatch) -> None:
    communication_main = load_communication_module()
    monkeypatch.setattr(communication_main.settings, "webhook_shared_secret", "top-secret", raising=False)
    monkeypatch.setattr(communication_main, "get_session_with_messages", lambda db, session_id: SimpleNamespace(id="s1", autopilot_enabled=False, last_job_status=None))
    monkeypatch.setattr(communication_main, "add_message", lambda **kwargs: SimpleNamespace(id="m3", body=kwargs["body"]))
    monkeypatch.setattr(communication_main, "update_session_status", lambda *args, **kwargs: True)
    monkeypatch.setattr(communication_main, "publish_session_event", lambda **kwargs: None)

    with _client_for(communication_main) as client:
        unauthorized = client.post(
            "/webhooks/twilio/sms",
            json={
                "session_id": "s1",
                "from_number": "+15555550100",
                "body": "hello",
            },
        )
        authorized = client.post(
            "/webhooks/twilio/sms",
            headers={"x-webhook-secret": "top-secret"},
            json={
                "session_id": "s1",
                "from_number": "+15555550100",
                "body": "hello",
            },
        )

    communication_main.app.dependency_overrides.clear()
    monkeypatch.setattr(communication_main.settings, "webhook_shared_secret", None, raising=False)

    assert unauthorized.status_code == 401
    assert authorized.status_code != 401

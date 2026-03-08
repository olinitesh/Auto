from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

import pytest


def load_api_main_module():
    root = Path(__file__).resolve().parents[2]
    api_src = root / "services" / "api-gateway" / "src"
    shared_src = root / "services" / "shared-python"
    comparison_src = root / "services" / "comparison-engine" / "src"
    for entry in [str(api_src), str(shared_src), str(comparison_src)]:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    path = api_src / "main.py"
    spec = importlib.util.spec_from_file_location("api_main_for_session_controls", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load api main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_status_transition_success_emits_event(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="active")
    updated = SimpleNamespace(id="s1", status="closed")
    captured = {}

    def fake_get(db, session_id):
        return session if session.status == "active" else updated

    monkeypatch.setattr(api_main, "get_session_with_messages", fake_get)

    def fake_update_status(db, *, session_id, status, last_job_id=None, last_job_status=None):
        session.status = status
        return True

    monkeypatch.setattr(api_main, "update_session_status", fake_update_status)
    monkeypatch.setattr(api_main, "publish_session_event", lambda **kwargs: captured.update(kwargs.get("payload", {})))
    monkeypatch.setattr(api_main, "to_session_out", lambda s: {"id": s.id, "status": s.status})

    payload = api_main.NegotiationStatusUpdateRequest(status="closed", source="warroom", actor="operator")
    result = api_main.update_negotiation_status("s1", payload, db=object())

    assert result["status"] == "closed"
    assert captured["previous_status"] == "active"
    assert captured["status"] == "closed"
    assert captured["source"] == "warroom"


def test_status_transition_invalid_rejected(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="active")
    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    payload = api_main.NegotiationStatusUpdateRequest(status="new", source="warroom", actor="operator")
    with pytest.raises(api_main.HTTPException) as exc:
        api_main.update_negotiation_status("s1", payload, db=object())

    assert exc.value.status_code == 400


def test_enqueue_round_blocks_closed_or_failed(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="closed", last_job_status=None)

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    def should_not_call_queue():
        raise AssertionError("queue should not be called")

    monkeypatch.setattr(api_main, "get_queue", should_not_call_queue)

    with pytest.raises(api_main.HTTPException) as exc:
        api_main.enqueue_autonomous_round("s1", api_main.EnqueueRoundRequest(user_name="Buyer"), db=object())

    assert exc.value.status_code == 409


def test_enqueue_round_blocks_duplicate_active_job(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="active", last_job_status="queued")

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    def should_not_call_queue():
        raise AssertionError("queue should not be called")

    monkeypatch.setattr(api_main, "get_queue", should_not_call_queue)

    with pytest.raises(api_main.HTTPException) as exc:
        api_main.enqueue_autonomous_round("s1", api_main.EnqueueRoundRequest(user_name="Buyer"), db=object())

    assert exc.value.status_code == 409


def test_reopen_then_enqueue_round_success(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="closed", last_job_status=None)
    events: list[str] = []

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    def fake_update_status(db, *, session_id, status, last_job_id=None, last_job_status=None):
        session.status = status
        if last_job_status is not None:
            session.last_job_status = last_job_status
        return True

    monkeypatch.setattr(api_main, "update_session_status", fake_update_status)
    monkeypatch.setattr(api_main, "to_session_out", lambda s: {"id": s.id, "status": s.status})
    monkeypatch.setattr(api_main, "publish_session_event", lambda **kwargs: events.append(kwargs.get("event_type", "")))

    class FakeJob:
        id = "job-1"

    class FakeQueue:
        name = "default"

        def enqueue(self, fn, session_id, user_name):
            assert session_id == "s1"
            assert user_name == "Buyer"
            return FakeJob()

    monkeypatch.setattr(api_main, "get_queue", lambda: FakeQueue())

    status_payload = api_main.NegotiationStatusUpdateRequest(status="active", source="warroom", actor="operator")
    updated = api_main.update_negotiation_status("s1", status_payload, db=object())
    assert updated["status"] == "active"

    queued = api_main.enqueue_autonomous_round("s1", api_main.EnqueueRoundRequest(user_name="Buyer"), db=object())
    assert queued.status == "queued"
    assert queued.job_id == "job-1"
    assert session.last_job_status == "queued"
    assert "negotiation.status.updated" in events
    assert "negotiation.round.queued" in events

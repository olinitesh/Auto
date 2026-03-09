from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

from fastapi.testclient import TestClient


def load_api_main_module():
    root = Path(__file__).resolve().parents[2]
    api_src = root / "services" / "api-gateway" / "src"
    shared_src = root / "services" / "shared-python"
    comparison_src = root / "services" / "comparison-engine" / "src"
    for entry in [str(api_src), str(shared_src), str(comparison_src)]:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    path = api_src / "main.py"
    spec = importlib.util.spec_from_file_location("api_main_for_http_session_controls", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load api main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _session_out(*, session_id: str, status: str) -> dict:
    return {
        "id": session_id,
        "user_id": "u1",
        "saved_search_id": None,
        "offer_id": None,
        "dealership_id": "d1",
        "dealership_name": "Metro Honda",
        "vehicle_id": "v1",
        "vehicle_label": "2025 Civic EX",
        "status": status,
        "best_offer_otd": 32000.0,
        "autopilot_enabled": False,
        "autopilot_mode": "manual",
        "playbook": "balanced",
        "playbook_policy": None,
        "last_job_id": None,
        "last_job_status": None,
        "last_job_at": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "messages": [],
    }


def _client_for(api_main):
    api_main.init_db = lambda: None

    def fake_get_db():
        yield object()

    api_main.app.dependency_overrides[api_main.get_db] = fake_get_db
    return TestClient(api_main.app)


def test_status_patch_active_to_closed_http(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="active", last_job_status=None)

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    def fake_update_status(db, *, session_id, status, last_job_id=None, last_job_status=None):
        session.status = status
        return True

    monkeypatch.setattr(api_main, "update_session_status", fake_update_status)
    monkeypatch.setattr(api_main, "to_session_out", lambda s: _session_out(session_id=s.id, status=s.status))
    monkeypatch.setattr(api_main, "publish_session_event", lambda **kwargs: None)

    with _client_for(api_main) as client:
        response = client.patch(
            "/negotiations/s1/status",
            json={"status": "closed", "source": "warroom", "actor": "operator"},
        )

    api_main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_status_patch_closed_to_active_http(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="closed", last_job_status=None)

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    def fake_update_status(db, *, session_id, status, last_job_id=None, last_job_status=None):
        session.status = status
        return True

    monkeypatch.setattr(api_main, "update_session_status", fake_update_status)
    monkeypatch.setattr(api_main, "to_session_out", lambda s: _session_out(session_id=s.id, status=s.status))
    monkeypatch.setattr(api_main, "publish_session_event", lambda **kwargs: None)

    with _client_for(api_main) as client:
        response = client.patch(
            "/negotiations/s1/status",
            json={"status": "active", "source": "warroom", "actor": "operator"},
        )

    api_main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_status_patch_invalid_transition_http(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="active", last_job_status=None)

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    with _client_for(api_main) as client:
        response = client.patch(
            "/negotiations/s1/status",
            json={"status": "new", "source": "warroom", "actor": "operator"},
        )

    api_main.app.dependency_overrides.clear()
    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["detail"]


def test_autonomous_round_blocks_closed_http(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="closed", last_job_status=None)

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    with _client_for(api_main) as client:
        response = client.post(
            "/negotiations/s1/autonomous-round",
            json={"user_name": "Buyer"},
        )

    api_main.app.dependency_overrides.clear()
    assert response.status_code == 409


def test_autonomous_round_blocks_active_duplicate_job_http(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="active", last_job_status="running")

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    with _client_for(api_main) as client:
        response = client.post(
            "/negotiations/s1/autonomous-round",
            json={"user_name": "Buyer"},
        )

    api_main.app.dependency_overrides.clear()
    assert response.status_code == 409


def test_reopen_then_queue_round_http(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(id="s1", status="closed", last_job_status=None)

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    def fake_update_status(db, *, session_id, status, last_job_id=None, last_job_status=None):
        session.status = status
        if last_job_status is not None:
            session.last_job_status = last_job_status
        return True

    monkeypatch.setattr(api_main, "update_session_status", fake_update_status)
    monkeypatch.setattr(api_main, "to_session_out", lambda s: _session_out(session_id=s.id, status=s.status))
    monkeypatch.setattr(api_main, "publish_session_event", lambda **kwargs: None)

    class FakeJob:
        id = "job-http-1"

    class FakeQueue:
        name = "default"

        def enqueue(self, fn, session_id, user_name):
            assert session_id == "s1"
            assert user_name == "Buyer"
            return FakeJob()

    monkeypatch.setattr(api_main, "get_queue", lambda: FakeQueue())

    with _client_for(api_main) as client:
        reopen = client.patch(
            "/negotiations/s1/status",
            json={"status": "active", "source": "warroom", "actor": "operator"},
        )
        queue = client.post(
            "/negotiations/s1/autonomous-round",
            json={"user_name": "Buyer"},
        )

    api_main.app.dependency_overrides.clear()
    assert reopen.status_code == 200
    assert reopen.json()["status"] == "active"
    assert queue.status_code == 200
    assert queue.json()["status"] == "queued"
    assert queue.json()["job_id"] == "job-http-1"

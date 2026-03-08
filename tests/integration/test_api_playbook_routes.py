from datetime import UTC, datetime
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
    spec = importlib.util.spec_from_file_location("api_main_for_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load api main module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_patch_negotiation_playbook_success(monkeypatch) -> None:
    api_main = load_api_main_module()

    session = SimpleNamespace(
        id="s1",
        status="active",
        best_offer_otd=32000.0,
        playbook="balanced",
        playbook_policy={"effective_target_otd": 31750.0},
    )
    event_payload = {}

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)

    def fake_update_session_playbook(db, *, session_id, playbook, playbook_policy):
        session.playbook = playbook
        session.playbook_policy = playbook_policy
        return True

    monkeypatch.setattr(api_main, "update_session_playbook", fake_update_session_playbook)
    monkeypatch.setattr(api_main, "publish_session_event", lambda **kwargs: event_payload.update(kwargs.get("payload", {})))
    monkeypatch.setattr(api_main, "to_session_out", lambda s: {"id": s.id, "playbook": s.playbook, "playbook_policy": s.playbook_policy})

    payload = api_main.NegotiationSessionUpdateRequest(playbook="aggressive")
    result = api_main.update_negotiation_session("s1", payload, db=object())

    assert result["playbook"] == "aggressive"
    assert event_payload["previous_playbook"] == "balanced"
    assert event_payload["playbook"] == "aggressive"


def test_patch_negotiation_playbook_rejects_closed_or_failed(monkeypatch) -> None:
    api_main = load_api_main_module()
    session = SimpleNamespace(
        id="s1",
        status="closed",
        best_offer_otd=32000.0,
        playbook="balanced",
        playbook_policy={"effective_target_otd": 31750.0},
    )

    monkeypatch.setattr(api_main, "get_session_with_messages", lambda db, session_id: session)
    called = {"update": False}

    def fake_update_session_playbook(*args, **kwargs):
        called["update"] = True
        return True

    monkeypatch.setattr(api_main, "update_session_playbook", fake_update_session_playbook)

    payload = api_main.NegotiationSessionUpdateRequest(playbook="aggressive")
    with pytest.raises(api_main.HTTPException) as exc:
        api_main.update_negotiation_session("s1", payload, db=object())

    assert exc.value.status_code == 409
    assert called["update"] is False


def test_to_session_out_includes_message_metadata_snapshot() -> None:
    api_main = load_api_main_module()

    message_metadata = {
        "playbook": "aggressive",
        "playbook_policy": {
            "effective_target_otd": 31550.0,
            "tone": "firm",
        },
    }

    message = SimpleNamespace(
        id="m1",
        direction="outbound",
        channel="email",
        sender_identity="AI Assistant representing Buyer",
        body="Test",
        created_at=datetime.now(UTC),
        message_metadata=message_metadata,
    )
    session = SimpleNamespace(
        id="s1",
        user_id="u1",
        saved_search_id=None,
        offer_id=None,
        dealership_id="d1",
        dealer=SimpleNamespace(name="Metro Honda"),
        vehicle_id="v1",
        vehicle_label="2025 Civic EX",
        status="active",
        best_offer_otd=32000.0,
        autopilot_enabled=False,
        autopilot_mode="manual",
        playbook="aggressive",
        playbook_policy={"effective_target_otd": 31550.0, "tone": "firm"},
        last_job_id=None,
        last_job_status=None,
        last_job_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        messages=[message],
    )

    out = api_main.to_session_out(session)
    assert out.messages[0].metadata == message_metadata

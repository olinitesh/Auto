from types import SimpleNamespace

import autohaggle_shared.jobs as jobs_module


def test_autonomous_round_uses_session_playbook_policy(monkeypatch) -> None:
    class DummyDb:
        def close(self) -> None:
            return None

        def commit(self) -> None:
            return None

    calls: dict[str, object] = {}

    session = SimpleNamespace(
        id="s1",
        best_offer_otd=35000,
        playbook="aggressive",
        playbook_policy={"tone": "firm", "concession_step": 150.0},
        dealer=SimpleNamespace(email=None, phone=None),
    )

    def fake_strategy(**kwargs):
        calls["strategy"] = kwargs
        return {
            "action": "counter_offer",
            "response_text": "Base response",
            "anchor_otd": 34000,
            "rationale": "rationale",
        }

    def fake_add_message(**kwargs):
        calls["message_metadata"] = kwargs.get("metadata")
        calls["message_body"] = kwargs.get("body")
        return SimpleNamespace(id="m1", direction="outbound", channel="email", body=kwargs.get("body", ""))

    monkeypatch.setattr(jobs_module, "SessionLocal", lambda: DummyDb())
    monkeypatch.setattr(jobs_module, "update_session_status", lambda *args, **kwargs: True)
    monkeypatch.setattr(jobs_module, "get_session_with_messages", lambda *args, **kwargs: session)
    monkeypatch.setattr(jobs_module, "run_negotiation_strategy", fake_strategy)
    monkeypatch.setattr(jobs_module, "add_message", fake_add_message)
    monkeypatch.setattr(jobs_module, "publish_session_event", lambda *args, **kwargs: None)

    result = jobs_module.run_autonomous_round("s1", "Buyer")

    assert result["ok"] is True
    assert calls["strategy"]["target_otd"] == 34550.0
    assert calls["message_metadata"]["playbook"] == "aggressive"
    assert "move to competing offers" in str(calls["message_body"]).lower()

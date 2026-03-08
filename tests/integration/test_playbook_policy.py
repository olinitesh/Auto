from autohaggle_shared.playbook import build_playbook_policy_snapshot, resolve_playbook


def test_resolve_playbook_falls_back_to_balanced() -> None:
    key, policy = resolve_playbook("unknown")
    assert key == "balanced"
    assert policy["tone"] == "neutral"


def test_build_playbook_policy_snapshot_includes_effective_target() -> None:
    key, policy = resolve_playbook("aggressive")
    snapshot = build_playbook_policy_snapshot(
        playbook_key=key,
        policy=policy,
        input_target_otd=32000,
    )
    assert snapshot["playbook"] == "aggressive"
    assert snapshot["effective_target_otd"] == 31550.0
    assert snapshot["tone"] == "firm"

from __future__ import annotations

from typing import Any

NEGOTIATION_PLAYBOOK_POLICIES: dict[str, dict[str, float | int | str]] = {
    "aggressive": {
        "target_offset": -450.0,
        "concession_step": 150.0,
        "max_rounds": 6,
        "walk_away_buffer": 300.0,
        "tone": "firm",
    },
    "balanced": {
        "target_offset": -250.0,
        "concession_step": 250.0,
        "max_rounds": 5,
        "walk_away_buffer": 200.0,
        "tone": "neutral",
    },
    "conservative": {
        "target_offset": -100.0,
        "concession_step": 350.0,
        "max_rounds": 4,
        "walk_away_buffer": 120.0,
        "tone": "collaborative",
    },
}


def resolve_playbook(playbook: str | None) -> tuple[str, dict[str, float | int | str]]:
    key = (playbook or "balanced").strip().lower()
    if key not in NEGOTIATION_PLAYBOOK_POLICIES:
        key = "balanced"
    return key, NEGOTIATION_PLAYBOOK_POLICIES[key]


def apply_playbook_target(target_otd: float, policy: dict[str, float | int | str]) -> float:
    offset = float(policy.get("target_offset", 0.0))
    return max(1000.0, round(float(target_otd) + offset, 2))


def apply_playbook_tone(message: str, tone: str) -> str:
    if tone == "firm":
        return message + " If this target cannot be met today, we will move to competing offers."
    if tone == "collaborative":
        return message + " We are flexible on structure if we can align quickly on a fair OTD."
    return message


def build_playbook_policy_snapshot(
    *,
    playbook_key: str,
    policy: dict[str, float | int | str],
    input_target_otd: float | None,
) -> dict[str, Any]:
    effective_target_otd = apply_playbook_target(input_target_otd, policy) if input_target_otd is not None else None
    return {
        "playbook": playbook_key,
        "target_offset": float(policy.get("target_offset", 0.0)),
        "concession_step": float(policy.get("concession_step", 0.0)),
        "max_rounds": int(policy.get("max_rounds", 0)),
        "walk_away_buffer": float(policy.get("walk_away_buffer", 0.0)),
        "tone": str(policy.get("tone", "neutral")),
        "input_target_otd": float(input_target_otd) if input_target_otd is not None else None,
        "effective_target_otd": effective_target_otd,
    }

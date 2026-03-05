from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["services/shared-python", "services/comparison-engine/src"])
    return env


def _run_once(env: dict[str, str]) -> None:
    limit = os.getenv("AUTOPILOT_SCHEDULER_LIMIT", "25")
    cooldown_seconds = os.getenv("AUTOPILOT_SCHEDULER_COOLDOWN_SECONDS", "120")
    user_name = os.getenv("AUTOPILOT_DEFAULT_USER_NAME", "Buyer")

    cmd = [
        sys.executable,
        "-m",
        "scraper_pipeline.autopilot_scheduler",
        "--limit",
        str(limit),
        "--cooldown-seconds",
        str(cooldown_seconds),
        "--user-name",
        user_name,
    ]

    subprocess.run(cmd, check=True, env=env)


def main() -> int:
    interval_seconds = int(os.getenv("AUTOPILOT_SCHEDULER_INTERVAL_SECONDS", "30"))
    run_once = os.getenv("AUTOPILOT_SCHEDULER_RUN_ONCE", "false").strip().lower() == "true"

    if interval_seconds < 1:
        raise ValueError("AUTOPILOT_SCHEDULER_INTERVAL_SECONDS must be >= 1")

    env = _build_env()

    while True:
        started = datetime.now(timezone.utc).isoformat()
        print(f"[{started}] autopilot scheduler cycle started")
        try:
            _run_once(env)
            ended = datetime.now(timezone.utc).isoformat()
            print(f"[{ended}] autopilot scheduler cycle completed")
        except Exception as exc:
            ended = datetime.now(timezone.utc).isoformat()
            print(f"[{ended}] autopilot scheduler cycle failed: {exc}")

        if run_once:
            return 0

        print(f"Sleeping {interval_seconds} seconds before next autopilot cycle")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

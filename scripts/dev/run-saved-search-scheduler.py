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
    limit = os.getenv("SAVED_SEARCH_REFRESH_LIMIT", "50")

    cmd = [
        sys.executable,
        "-m",
        "scraper_pipeline.saved_search_refresh",
        "--limit",
        str(limit),
    ]

    subprocess.run(cmd, check=True, env=env)


def main() -> int:
    interval_minutes = int(os.getenv("SAVED_SEARCH_REFRESH_INTERVAL_MINUTES", "60"))
    run_once = os.getenv("SAVED_SEARCH_REFRESH_RUN_ONCE", "false").strip().lower() == "true"

    if interval_minutes < 1:
        raise ValueError("SAVED_SEARCH_REFRESH_INTERVAL_MINUTES must be >= 1")

    env = _build_env()

    while True:
        started = datetime.now(timezone.utc).isoformat()
        print(f"[{started}] saved-search scheduler cycle started")
        try:
            _run_once(env)
            ended = datetime.now(timezone.utc).isoformat()
            print(f"[{ended}] saved-search scheduler cycle completed")
        except Exception as exc:
            ended = datetime.now(timezone.utc).isoformat()
            print(f"[{ended}] saved-search scheduler cycle failed: {exc}")

        if run_once:
            return 0

        print(f"Sleeping {interval_minutes} minutes before next saved-search refresh cycle")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())

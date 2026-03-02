from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["services/shared-python", "services/comparison-engine/src"])
    return env


def _run_once(env: dict[str, str]) -> int:
    user_zip = os.getenv("FALLBACK_INGEST_USER_ZIP", "18706")
    radius = os.getenv("FALLBACK_INGEST_RADIUS_MILES", "100")
    budget = os.getenv("FALLBACK_INGEST_BUDGET_OTD", "45000")
    targets_json = os.getenv(
        "FALLBACK_INGEST_TARGETS_JSON",
        '[{"make":"Toyota","model":"RAV4","year":2025},{"make":"Honda","model":"Civic","year":2025}]',
    )
    dealer_sites_json = os.getenv("FALLBACK_INGEST_DEALER_SITES_JSON", "[]")

    # Fail fast with readable errors for malformed env JSON.
    json.loads(targets_json)
    json.loads(dealer_sites_json)

    cmd = [
        sys.executable,
        "-m",
        "scraper_pipeline.fallback_agent",
        "--zip",
        user_zip,
        "--radius",
        str(radius),
        "--budget",
        str(budget),
        "--targets-json",
        targets_json,
        "--dealer-sites-json",
        dealer_sites_json,
    ]

    subprocess.run(cmd, check=True, env=env)
    return 0


def main() -> int:
    interval_minutes = int(os.getenv("FALLBACK_INGEST_INTERVAL_MINUTES", "360"))
    run_once = os.getenv("FALLBACK_INGEST_RUN_ONCE", "false").strip().lower() == "true"

    if interval_minutes < 1:
        raise ValueError("FALLBACK_INGEST_INTERVAL_MINUTES must be >= 1")

    env = _build_env()

    while True:
        started = datetime.now(timezone.utc).isoformat()
        print(f"[{started}] fallback ingest cycle started")
        try:
            _run_once(env)
            ended = datetime.now(timezone.utc).isoformat()
            print(f"[{ended}] fallback ingest cycle completed")
        except Exception as exc:
            ended = datetime.now(timezone.utc).isoformat()
            print(f"[{ended}] fallback ingest cycle failed: {exc}")

        if run_once:
            return 0

        sleep_seconds = interval_minutes * 60
        print(f"Sleeping {interval_minutes} minutes before next cycle")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

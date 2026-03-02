from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["services/shared-python", "services/comparison-engine/src"])

    cmd = [
        sys.executable,
        "-m",
        "scraper_pipeline.fallback_agent",
        "--zip",
        "18706",
        "--radius",
        "100",
        "--budget",
        "45000",
        "--targets-json",
        '[{"make":"Toyota","model":"RAV4","year":2026},{"make":"Honda","model":"Civic","year":2025}]',
    ]

    subprocess.run(cmd, check=True, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

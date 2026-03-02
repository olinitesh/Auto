from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = "services/shared-python"

    subprocess.run(
        [sys.executable, "services/negotiation-orchestrator/src/worker.py"],
        check=True,
        env=env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

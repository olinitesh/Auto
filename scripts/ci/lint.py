from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = "services/shared-python"

    cmd = [
        sys.executable,
        "-m",
        "compileall",
        "services/shared-python",
        "services/api-gateway/src",
        "services/negotiation-orchestrator/src",
        "services/communication-service/src",
        "services/war-room-realtime/src",
    ]
    subprocess.run(cmd, check=True, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

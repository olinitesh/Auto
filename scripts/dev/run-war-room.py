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
        "uvicorn",
        "main:app",
        "--app-dir",
        "services/war-room-realtime/src",
        "--host",
        "0.0.0.0",
        "--port",
        "8020",
        "--reload",
    ]
    subprocess.run(cmd, check=True, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

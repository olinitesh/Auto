from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = "services/shared-python:services/api-gateway/src:services/comparison-engine/src"

    subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

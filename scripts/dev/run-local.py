from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value

    return values


def main() -> int:
    env = os.environ.copy()

    # Load .env so local services get API keys/secrets without manual export.
    dotenv_values = _load_dotenv(Path(".env"))
    for key, value in dotenv_values.items():
        env.setdefault(key, value)

    env["PYTHONPATH"] = os.pathsep.join(["services/shared-python", "services/comparison-engine/src"])

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--app-dir",
        "services/api-gateway/src",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]
    subprocess.run(cmd, check=True, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

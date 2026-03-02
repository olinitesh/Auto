from __future__ import annotations

import pathlib
import subprocess


def main() -> int:
    sql_path = pathlib.Path("database/schema/schema.sql")
    sql = sql_path.read_text(encoding="utf-8")

    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "autohaggle",
            "-d",
            "autohaggle",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=sql,
        text=True,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

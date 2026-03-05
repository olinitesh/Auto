from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_PYTHON = REPO_ROOT / "services" / "shared-python"
if str(SHARED_PYTHON) not in sys.path:
    sys.path.insert(0, str(SHARED_PYTHON))

from autohaggle_shared.database import engine


MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"


def _load_sql_with_includes(sql_file: Path) -> str:
    lines: list[str] = []
    for raw_line in sql_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            lines.append(raw_line)
            continue

        if line.startswith("\\i "):
            include_target = line[3:].strip()
            include_path = Path(include_target)
            if not include_path.is_absolute():
                include_path = (REPO_ROOT / include_path).resolve()
            if not include_path.exists():
                raise FileNotFoundError(f"Included SQL file not found: {include_path}")
            lines.append(include_path.read_text(encoding="utf-8"))
            continue

        lines.append(raw_line)

    return "\n".join(lines)


def _split_sql_statements(sql: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False

    for ch in sql:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double

        if ch == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                parts.append(statement)
            current = []
        else:
            current.append(ch)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)

    return parts


def main() -> int:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No migrations found under {MIGRATIONS_DIR}")
        return 0

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migration (
                  file_name VARCHAR(255) PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )

    applied = 0
    skipped = 0

    for file in files:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM schema_migration WHERE file_name = :file_name"),
                {"file_name": file.name},
            ).scalar_one_or_none()

            if exists:
                skipped += 1
                print(f"skip {file.name}")
                continue

            sql = _load_sql_with_includes(file)
            statements = _split_sql_statements(sql)
            for statement in statements:
                conn.execute(text(statement))

            conn.execute(
                text("INSERT INTO schema_migration (file_name, applied_at) VALUES (:file_name, :applied_at)"),
                {"file_name": file.name, "applied_at": datetime.now(timezone.utc)},
            )
            applied += 1
            print(f"applied {file.name}")

    print(f"done: applied={applied}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

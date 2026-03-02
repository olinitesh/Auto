from __future__ import annotations

import os
import pathlib
import subprocess
import sys


def run(cmd: list[str], cwd: pathlib.Path) -> None:
    subprocess.run(cmd, check=True, cwd=str(cwd))


def venv_python_path(venv_dir: pathlib.Path) -> pathlib.Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def load_dependencies(pyproject_path: pathlib.Path) -> list[str]:
    import tomllib

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return list(data.get("project", {}).get("dependencies", []))


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    venv_dir = repo_root / ".venv"
    python_in_venv = venv_python_path(venv_dir)

    if not python_in_venv.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)], cwd=repo_root)

    run([str(python_in_venv), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo_root)

    dependencies = load_dependencies(repo_root / "pyproject.toml")
    if dependencies:
        run([str(python_in_venv), "-m", "pip", "install", *dependencies], cwd=repo_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Repository Guidelines

## Project Structure & Module Organization
This repository is a monorepo for AutoHaggle AI services and clients.

- `apps/`: frontend clients (for example, `apps/web`).
- `services/`: backend services (API gateway, workers, realtime services).
- `libs/`: shared contracts, configs, and reusable templates.
- `database/`: SQL schema, migrations, and seed data.
- `infra/`: deployment and infrastructure definitions.
- `scripts/`: local development and CI automation scripts.
- `tests/`: integration and end-to-end tests.
- `docs/`: architecture notes, API docs, and runbooks.

Keep modules focused and place shared logic in `libs/` or `services/shared-python`.

## Build, Test, and Development Commands
Use the `Makefile` as the entry point for common workflows:

- `make bootstrap`: install/setup local dependencies via `scripts/dev/bootstrap.py`.
- `make up`: start supporting containers with Docker Compose.
- `make lint`: run Python compile checks via `scripts/ci/lint.py`.
- `make test`: run automated tests via `scripts/ci/test.py`.
- `make api`, `make worker`, `make communication`, `make warroom`: run backend services locally.
- `make web`: install and start the web app (`apps/web`).

## Coding Style & Naming Conventions
- Indentation: 4 spaces for Python; 2 spaces for Markdown/YAML/JSON.
- File names: lowercase with hyphens where practical (example: `run-war-room.py`).
- Python: target 3.11+, keep functions/classes single-purpose, and use descriptive names.
- Prefer ASCII unless a file already requires Unicode.
- Before opening a PR, run `make lint` and `make test`.

## Testing Guidelines
- Framework: `pytest` (configured in `pyproject.toml`, tests under `tests/`).
- Naming: use clear test names such as `test_<behavior>.py`.
- Minimum expectation: cover one success path and one failure path per feature.
- Run locally with `make test`.

## Commit & Pull Request Guidelines
There is no established commit history yet; adopt Conventional Commits:

- `type(scope): short summary` (example: `feat(api): add session status endpoint`).

PRs should include:

- concise change summary and reason,
- related issue/task reference,
- test evidence (`make test`, `make lint`),
- screenshots or sample payloads for user-facing/API behavior changes.

## Security & Configuration Tips
- Never commit secrets or tokens.
- Use `.env.example` as the template for local `.env` values.
- Keep environment-specific credentials out of version control.

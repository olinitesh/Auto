# Repository Guidelines

## Project Structure & Module Organization
This repository is currently minimal and contains:
- `prompt.md`: primary working document.
- `.git/`: version control metadata.

As the project grows, keep a predictable layout:
- `src/` for implementation code.
- `tests/` for automated tests.
- `assets/` for static files (images, fixtures, sample data).
- `docs/` for design notes and usage guides.

Use small, focused modules and keep related files close together.

## Build, Test, and Development Commands
There is no build system configured yet. Use these baseline commands:
- `git status` — check local changes before and after edits.
- `rg --files` — list tracked project files quickly.
- `rg "pattern"` — search code/text across the repo.

When tooling is added, expose standard commands (for example `npm test`, `pytest`, or `make test`) and document them here.

## Coding Style & Naming Conventions
Until language-specific tooling is added, follow these defaults:
- Indentation: 2 spaces for Markdown/JSON/YAML, 4 spaces for Python.
- File names: use lowercase with hyphens (for example, `task-runner.md`).
- Keep functions/classes single-purpose and names descriptive.
- Prefer ASCII in source files unless Unicode is required.

If formatters/linters are introduced, run them before opening a PR.

## Testing Guidelines
No test framework is configured yet. When adding tests:
- Mirror source structure under `tests/`.
- Name tests clearly (`test_<unit>.py`, `<unit>.spec.ts`, etc.).
- Add at least one happy-path and one failure-path test per feature.
- Document the test command in this file once available.

## Commit & Pull Request Guidelines
This repository has no commit history yet, so adopt a conventional format now:
- Commit messages: `type(scope): short summary` (for example, `docs(readme): add setup notes`).
- Keep commits focused and atomic.

Pull requests should include:
- What changed and why.
- Related issue/task reference (if available).
- Screenshots or sample output for user-facing changes.
- Notes on testing performed and any follow-up work.

## Security & Configuration Tips
- Do not commit secrets, tokens, or machine-specific credentials.
- Use `.env` files locally and commit only a sanitized `.env.example` when needed.

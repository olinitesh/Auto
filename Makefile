PYTHON ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)

ifeq ($(strip $(PYTHON)),)
$(error Python not found. Install Python 3.11+ and ensure python3 or python is in PATH.)
endif

ifeq ($(OS),Windows_NT)
VENV_PYTHON ?= .venv/Scripts/python.exe
else
VENV_PYTHON ?= .venv/bin/python
endif

RUN_PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),$(PYTHON))

.PHONY: bootstrap up test lint migrate api worker communication warroom web web-prod fallback-ingest fallback-scheduler saved-search-scheduler autopilot-scheduler session-controls-smoke step6-smoke

bootstrap:
	$(PYTHON) scripts/dev/bootstrap.py

up:
	docker compose up -d

test:
	$(RUN_PYTHON) scripts/ci/test.py

lint:
	$(RUN_PYTHON) scripts/ci/lint.py

migrate:
	$(RUN_PYTHON) scripts/dev/migrate.py

api:
	$(RUN_PYTHON) scripts/dev/run-local.py

worker:
	$(RUN_PYTHON) scripts/dev/run-worker.py

communication:
	$(RUN_PYTHON) scripts/dev/run-communication.py

warroom:
	$(RUN_PYTHON) scripts/dev/run-war-room.py

fallback-ingest:
	$(RUN_PYTHON) scripts/dev/run-fallback-ingest.py

fallback-scheduler:
	$(RUN_PYTHON) scripts/dev/run-fallback-scheduler.py

saved-search-scheduler:
	$(RUN_PYTHON) scripts/dev/run-saved-search-scheduler.py

autopilot-scheduler:
	$(RUN_PYTHON) scripts/dev/run-autopilot-scheduler.py

web:
	cd apps/web && npm install && npm run dev

web-prod:
	cd apps/web && npm ci && npm run build && npm run preview -- --host 127.0.0.1 --port 5173


session-controls-smoke:
	PYTHONPATH=services/shared-python:services/api-gateway/src:services/comparison-engine/src $(RUN_PYTHON) -m pytest -q tests/integration/test_api_session_controls.py


step6-smoke:
	PYTHONPATH=services/shared-python:services/api-gateway/src:services/comparison-engine/src $(RUN_PYTHON) -m pytest -q tests/integration/test_api_payloads.py tests/integration/test_playbook_policy.py tests/integration/test_jobs_playbook.py tests/integration/test_api_playbook_routes.py tests/integration/test_api_session_controls.py

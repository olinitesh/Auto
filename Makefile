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

.PHONY: bootstrap up test lint api worker communication warroom web fallback-ingest fallback-scheduler

bootstrap:
	$(PYTHON) scripts/dev/bootstrap.py

up:
	docker compose up -d

test:
	$(RUN_PYTHON) scripts/ci/test.py

lint:
	$(RUN_PYTHON) scripts/ci/lint.py

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

web:
	cd apps/web && npm install && npm run dev

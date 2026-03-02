# AutoHaggle AI

Monorepo for an autonomous vehicle comparison and negotiation platform.

## Backend Starter Included
- FastAPI API gateway at `services/api-gateway/src/main.py`
- Shared models/config/workflow in `services/shared-python/autohaggle_shared`
- LangGraph negotiation strategy stub with AI disclosure enforcement
- PostgreSQL schema in `database/schema/schema.sql`

## Layout
- `apps/`: mobile and web clients.
- `services/`: backend microservices.
- `libs/`: shared contracts, configs, and templates.
- `database/`: SQL schema, migrations, seeds.
- `infra/`: Docker, Kubernetes, Terraform.
- `docs/`: architecture, API docs, and runbooks.
- `scripts/`: local dev, CI, and DB automation scripts.
- `tests/`: integration and end-to-end tests.

## Quick Start
```bash
make bootstrap
cp .env.example .env
make up
```

`make bootstrap` creates a local virtual environment at `.venv` and installs project dependencies there.

## Run Processes
Run each process in a separate terminal:

```bash
# 1) API Gateway
make api

# 2) Negotiation worker (RQ + Redis)
make worker

# 3) Communication service (Twilio/SendGrid adapters)
make communication

# 4) War Room realtime websocket service
make warroom

# 5) Web War Room UI
make web

# 6) Scheduled fallback ingest (recommended for price history)
make fallback-scheduler
```

Alternative (direct Python scripts):

```bash
# 1) API Gateway
.venv/bin/python scripts/dev/run-local.py

# 2) Negotiation worker (RQ + Redis)
.venv/bin/python scripts/dev/run-worker.py

# 3) Communication service (Twilio/SendGrid adapters)
.venv/bin/python scripts/dev/run-communication.py

# 4) War Room realtime websocket service
.venv/bin/python scripts/dev/run-war-room.py

# 5) Web War Room UI
cd apps/web
npm install
npm run dev

# 6) Scheduled fallback ingest
.venv/bin/python scripts/dev/run-fallback-scheduler.py
```

Service URLs:
- API Gateway Swagger: `http://localhost:8000/docs`
- Communication Service Swagger: `http://localhost:8010/docs`
- War Room WebSocket: `ws://localhost:8020/ws/negotiations/{session_id}`
- Web War Room: `http://localhost:5173/?sessionId={session_id}`


## Scheduled Ingest Worker
Run this process to keep offer history and days-on-market data fresh without manual searches.

```bash
make fallback-scheduler
```

Key `.env` settings:
- `FALLBACK_INGEST_INTERVAL_MINUTES` (default `360`)
- `FALLBACK_INGEST_USER_ZIP`
- `FALLBACK_INGEST_RADIUS_MILES`
- `FALLBACK_INGEST_BUDGET_OTD`
- `FALLBACK_INGEST_TARGETS_JSON` (JSON list of make/model/year targets)
- `FALLBACK_INGEST_RUN_ONCE=true` to run one cycle and exit

## Troubleshooting
- Docker errors on `make up`: ensure Docker Desktop (or Docker Engine) is running, then retry.
- `python`/`python3` not found during `make bootstrap`: install Python 3.11+ and confirm `python3 --version` works.
- `externally-managed-environment` (PEP 668): use `make bootstrap`; it installs into `.venv` (not system Python).
- `npm` not found for `make web`: install Node.js LTS and verify `npm -v`.
- Port already in use: free ports `8000`, `8010`, `8020`, or update service config.
- Environment issues: confirm `.env` exists (`cp .env.example .env`) and required variables are set.

## Example Negotiation Flow
Start negotiation:
```bash
curl -X POST http://localhost:8000/negotiations/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"u1",
    "user_name":"Nitesh",
    "dealership_id":"d1",
    "dealership_name":"Metro Honda",
    "dealership_email":"sales@metrohonda.example",
    "vehicle_id":"v1",
    "vehicle_label":"2025 Honda Civic EX",
    "target_otd":30000,
    "dealer_otd":32150,
    "competitor_best_otd":30790
  }'
```

Queue autonomous follow-up:
```bash
curl -X POST http://localhost:8000/negotiations/{session_id}/autonomous-round \
  -H "Content-Type: application/json" \
  -d '{"user_name":"Nitesh"}'
```

Simulate dealer inbound SMS webhook:
```bash
curl -X POST http://localhost:8010/webhooks/twilio/sms \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"{session_id}",
    "from_number":"+15555550100",
    "body":"Can you come in today to finalize?",
    "message_sid":"SM123"
  }'
```




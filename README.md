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
```powershell
make up
powershell -ExecutionPolicy Bypass -File scripts/dev/bootstrap.ps1
```

Copy environment template:
```powershell
Copy-Item .env.example .env
```

Run services in separate terminals:
```powershell
# 1) API Gateway
powershell -ExecutionPolicy Bypass -File scripts/dev/run-local.ps1

# 2) Negotiation worker (RQ + Redis)
powershell -ExecutionPolicy Bypass -File scripts/dev/run-worker.ps1

# 3) Communication service (Twilio/SendGrid adapters)
powershell -ExecutionPolicy Bypass -File scripts/dev/run-communication.ps1

# 4) War Room realtime websocket service
powershell -ExecutionPolicy Bypass -File scripts/dev/run-war-room.ps1

# 5) Web War Room UI
cd apps/web
npm install
npm run dev
```

Service URLs:
- API Gateway Swagger: `http://localhost:8000/docs`
- Communication Service Swagger: `http://localhost:8010/docs`
- War Room WebSocket: `ws://localhost:8020/ws/negotiations/{session_id}`
- Web War Room: `http://localhost:5173/?sessionId={session_id}`

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

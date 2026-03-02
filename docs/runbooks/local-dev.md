# Local Development Runbook

## Prerequisites
- Docker Desktop
- Python 3.11+

## Start Dependencies
```powershell
make up
```

## Install Backend Dependencies
```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev/bootstrap.ps1
```

## Run Services (Separate Terminals)
```powershell
# API Gateway
powershell -ExecutionPolicy Bypass -File scripts/dev/run-local.ps1

# Background worker
powershell -ExecutionPolicy Bypass -File scripts/dev/run-worker.ps1

# Communication service (Twilio/SendGrid)
powershell -ExecutionPolicy Bypass -File scripts/dev/run-communication.ps1

# War Room realtime feed
powershell -ExecutionPolicy Bypass -File scripts/dev/run-war-room.ps1

# Web dashboard
cd apps/web
npm install
npm run dev
```

## Seed Schema Manually
```powershell
powershell -ExecutionPolicy Bypass -File scripts/db/migrate.ps1
```

## Smoke Test
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

Then queue a follow-up autonomous negotiation round:
```bash
curl -X POST http://localhost:8000/negotiations/{session_id}/autonomous-round \
  -H "Content-Type: application/json" \
  -d '{"user_name":"Nitesh"}'
```

Connect WebSocket client to:
`ws://localhost:8020/ws/negotiations/{session_id}`

Or open web dashboard:
`http://localhost:5173/?sessionId={session_id}`

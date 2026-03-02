# AutoHaggle AI

AutoHaggle AI is a local-first vehicle offer discovery and negotiation workspace.
It searches dealer inventory, ranks offers, tracks pricing over time, and exposes APIs/UI for shortlist and negotiation workflows.

## What This Project Includes
- **API Gateway (FastAPI):** search, rank, trends, history, negotiation endpoints.
- **Comparison UI (Vite/React):** input search criteria, view search + ranked offers, inspect price history.
- **Shared Python layer:** DB models, schemas, repository logic.
- **Data tracking:** offer observations + price snapshots for days-on-market and trend signals.

## Repository Layout
- `apps/web`: comparison UI.
- `services/api-gateway`: FastAPI application.
- `services/shared-python`: shared config/models/schemas/repository.
- `services/comparison-engine`: offer collection + normalization pipeline.
- `database/schema` and `database/migrations`: SQL schema/migrations.
- `scripts/dev`: local process runners.

## Setup (From Scratch)
```bash
make bootstrap
cp .env.example .env
make up
```

## Run Each Section
Run each in a separate terminal.

### 1) API Gateway
```bash
make api
```
Serves REST endpoints (`/offers/search`, `/offers/rank`, `/offers/trends`, `/offers/history`, negotiation endpoints).

### 2) Negotiation Worker
```bash
make worker
```
Processes queued autonomous negotiation rounds.

### 3) Communication Service
```bash
make communication
```
Handles outbound/inbound communication adapters (Twilio/SendGrid flows).

### 4) War Room Realtime Service
```bash
make warroom
```
Serves websocket updates for live negotiation sessions.

### 5) Web UI
```bash
make web
```
Starts the comparison frontend (search, rank, trends, history panels).

### 6) One-off Fallback Ingest
```bash
make fallback-ingest
```
Runs a single ingest cycle to collect/normalize offers.

### 7) Scheduled Fallback Ingest
```bash
make fallback-scheduler
```
Runs recurring ingest cycles to keep trend/history signals fresh.

## URLs
- API docs: `http://localhost:8000/docs`
- Communication docs: `http://localhost:8010/docs`
- Web UI: `http://localhost:5173`
- War Room WS: `ws://localhost:8020/ws/negotiations/{session_id}`

## Common Offer APIs
```bash
# Search offers
curl -X POST "http://localhost:8000/offers/search" -H "Content-Type: application/json" --data-raw '{"user_zip":"18706","radius_miles":100,"budget_otd":45000,"targets":[{"make":"Toyota","model":"RAV4","year":2025}]}'

# Rank offers
curl -X POST "http://localhost:8000/offers/rank" -H "Content-Type: application/json" --data-raw '{"budget_otd":45000,"offers":[]}'

# Trends (single)
curl "http://localhost:8000/offers/trends?dealership_id=1063452&vehicle_id=2T3F1RFVXSW508067"

# Trends (bulk)
curl -X POST "http://localhost:8000/offers/trends/bulk" -H "Content-Type: application/json" --data-raw '{"offers":[{"dealership_id":"1063452","vehicle_id":"2T3F1RFVXSW508067"}]}'

# Price history
curl "http://localhost:8000/offers/history?dealership_id=1063452&vehicle_id=2T3F1RFVXSW508067&limit=30"
```

## Troubleshooting
- If `make`/`python3` missing: install build tools and Python 3.11+.
- If Docker command missing in WSL: enable Docker Desktop WSL integration.
- If API starts but UI says "Failed to fetch": confirm API is running on `http://localhost:8000`.
- If no trend/DOM values appear: run additional searches or fallback ingest to accumulate snapshots.

## Documentation Maintenance
`README.md` will be updated on future feature/process changes to include:
1. what changed,
2. how to run it,
3. what it does.

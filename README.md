# AutoHaggle AI

AutoHaggle AI is a local-first vehicle offer discovery and negotiation workspace. It searches dealer/API inventory, ranks offers, tracks price history, and surfaces negotiation signals (DOM and price drops).

## What This Project Includes
- API Gateway (FastAPI): `/offers/search`, `/offers/rank`, `/offers/trends`, `/offers/history`, `/saved-searches`, `/alerts`.
- Comparison UI (Vite/React): search form, ranked shortlist, saved searches, alerts (severity + filter + server-side pagination + show-acknowledged + bulk acknowledge), price-history panels, and one-click negotiation start with War Room links, queue-round controls, lifecycle status tracking, and AI autopilot toggles (auto-queue on inbound replies).
- Comparison engine: provider adapters, ingest workers, fallback scheduler, saved-search refresh scheduler.
- Shared Python layer: DB config, models, schemas, repository logic.

## Repository Layout
- `apps/web`: comparison UI.
- `services/api-gateway`: FastAPI app.
- `services/comparison-engine`: offer collection + normalization.
- `services/shared-python`: shared config/models/schemas/repository.
- `database/schema`, `database/migrations`: SQL schema + migrations.
- `scripts/dev`: local run scripts.

## Setup (From Scratch)
```bash
make bootstrap
cp .env.example .env
make up
make migrate
# run again after schema changes
# make migrate
```

## Run Services (separate terminals)
```bash
make api
make worker
make communication
make warroom
make web
```

Other jobs:
```bash
make fallback-ingest
make fallback-scheduler
make saved-search-scheduler
make autopilot-scheduler
```

### Saved-Search Scheduler Environment Knobs
- `SAVED_SEARCH_REFRESH_INTERVAL_MINUTES` (default `60`)
- `SAVED_SEARCH_REFRESH_LIMIT` (default `50`)
- `SAVED_SEARCH_REFRESH_RUN_ONCE=true` (run one cycle then exit)
- `ALERT_DOM_THRESHOLD_DAYS` (default `45`)
- `ALERT_PRICE_DROP_7D` (default `500`)
- `ALERT_PRICE_DROP_30D` (default `1500`)


### Autopilot Scheduler Environment Knobs
- `AUTOPILOT_SCHEDULER_INTERVAL_SECONDS` (default `30`)
- `AUTOPILOT_SCHEDULER_LIMIT` (default `25`)
- `AUTOPILOT_SCHEDULER_COOLDOWN_SECONDS` (default `120`)
- `AUTOPILOT_DEFAULT_USER_NAME` (default `Buyer`)
- `AUTOPILOT_SCHEDULER_RUN_ONCE=true` (run one cycle then exit)

## Local URLs
- API docs: `http://localhost:8000/docs`
- Communication docs: `http://localhost:8010/docs`
- Web UI: `http://localhost:5173`
- War Room WS: `ws://localhost:8020/ws/negotiations/{session_id}`

## Quick API Checks
```bash
curl -X POST "http://localhost:8000/offers/search" -H "Content-Type: application/json" --data-raw '{"user_zip":"18706","radius_miles":100,"budget_otd":45000,"targets":[{"make":"Toyota","model":"RAV4","year":2025}]}'
curl -X POST "http://localhost:8000/offers/rank" -H "Content-Type: application/json" --data-raw '{"budget_otd":45000,"offers":[]}'
curl "http://localhost:8000/offers/history?dealership_id=1063452&vehicle_id=2T3F1RFVXSW508067&limit=30"
curl "http://localhost:8000/alerts?include_acknowledged=false&page=1&page_size=20"
# Acknowledge a set of alerts (ids from GET /alerts)
curl -X POST "http://localhost:8000/alerts/ack-all" -H "Content-Type: application/json" --data-raw '{"alert_ids":["alert-id-1","alert-id-2"]}'
# Start a negotiation from a ranked/search offer
curl -X POST "http://localhost:8000/negotiations/start" -H "Content-Type: application/json" --data-raw '{"user_id":"local-user","user_name":"Buyer","dealership_id":"1063452","dealership_name":"Koch 33 Toyota","vehicle_id":"2T3F1RFVXSW508067","vehicle_label":"2025 Toyota RAV4 LE","target_otd":28500,"dealer_otd":29266,"offer_id":"1063452-2T3F1RFVXSW508067-1","offer_rank":1}'
# List negotiation sessions
curl "http://localhost:8000/negotiations"
# Check a queued negotiation round job
curl "http://localhost:8000/jobs/<job_id>"
# Enable AI autopilot for a session
curl -X PATCH "http://localhost:8000/negotiations/<session_id>/autopilot" -H "Content-Type: application/json" --data-raw '{"enabled":true,"mode":"autopilot"}'
# Simulate inbound dealer reply (autopilot queues next round automatically when enabled)
curl -X POST "http://localhost:8000/negotiations/<session_id>/simulate-reply" -H "Content-Type: application/json" --data-raw '{"channel":"email","sender_identity":"dealer@example.com","user_name":"Buyer","body":"We can do 31250 OTD."}'
```

## Troubleshooting
- `make: python: No such file or directory`: run `make PYTHON=python3 bootstrap`.
- WSL Docker missing: enable Docker Desktop WSL integration.
- UI "Failed to fetch": verify API at `http://localhost:8000/health`.
- `UndefinedColumn` (e.g., `saved_search_id` in `negotiation_session`): run `make migrate`, then restart `make api`.
- MarketCheck `429`: wait 30-90 seconds; adapter retries with backoff and bounded request fan-out.






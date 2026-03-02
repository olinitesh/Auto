# Comparison Engine

Aggregates dealer listings and normalizes pricing/specs.

## Scraper Pipeline Skeleton

This service now includes a concrete pipeline skeleton under `src/scraper_pipeline`:

- `queue_worker.py`: queue consumer and batch worker loop.
- `parser.py`: converts source payloads into a common parsed schema.
- `normalizer.py`: canonicalizes make/model/trim and computes OTD totals.
- `deduper.py`: merges duplicates using VIN/key with best-price selection.
- `dealer_registry.py`: dealer source registry (step 1).
- `dealer_site_adapters.py`: Toyota/Honda parser adapters (step 2).
- `dealer_scrape_agent.py`: registry-driven direct dealer scrape orchestrator.
- `live_agent.py`: AI-style data collection agent (direct scrape -> aggregator -> fallback).
- `marketcheck_adapter.py`: Aggregator API adapter for live dealer listing collection.
- `local_catalog.py`: local fallback catalog for development.
- `search_service.py`: search orchestration used by API gateway.
- `fallback_agent.py`: separate ingestion agent that writes fallback listings into local DB.

## Direct Dealer Scrape Setup (Step 1 + 2)

Enable registry+adapter scrape path:

```bash
DEALER_DIRECT_SCRAPE_ENABLED=true
```

Current adapter coverage:

- `honda`: parses `vehicle-card` HTML data attributes.
- `toyota`: parses `window.__INITIAL_INVENTORY__` JSON blob.

Dealer source definitions live in `dealer_registry.py` and are easy to extend.

## Live Aggregator Setup

1. Add a MarketCheck API key to `.env`:

```bash
MARKETCHECK_API_KEY=your_key_here
```

2. Start API normally:

```bash
make api
```

Agent provider order:

1. direct dealer scrape (if `DEALER_DIRECT_SCRAPE_ENABLED=true`)
2. marketcheck aggregator (if API key configured)
3. local catalog fallback

## Fallback Database Ingestion Agent

Run separate agent to collect listings and upsert into local DB fallback tables (`dealership`, `vehicle_listing`):

```bash
make fallback-ingest
```

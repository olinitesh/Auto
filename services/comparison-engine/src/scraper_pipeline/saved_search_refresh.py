from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from autohaggle_shared.database import SessionLocal, init_db
from autohaggle_shared.repository import (
    create_or_touch_saved_search_alert,
    get_offer_trend_summary,
    list_saved_searches,
    upsert_offer_observations,
)

from .search_service import search_local_offers


def _sanitize_offers(raw_offers: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for item in raw_offers:
        try:
            otd_price = float(item.get("otd_price") or 0.0)
        except (TypeError, ValueError):
            continue

        if otd_price <= 0:
            continue
        if not item.get("offer_id") or not item.get("dealership_id") or not item.get("vehicle_id"):
            continue

        item["otd_price"] = otd_price
        sanitized.append(item)

    return sanitized


def _generate_alerts(db, *, saved_search_id: str, offers: list[dict], dom_threshold: int, drop_7d_threshold: float, drop_30d_threshold: float) -> int:
    created = 0

    for offer in offers:
        dealership_id = str(offer.get("dealership_id") or "").strip()
        vehicle_id = str(offer.get("vehicle_id") or "").strip()
        vehicle_label = str(offer.get("vehicle_label") or vehicle_id).strip()
        dealer_name = str(offer.get("dealership_name") or dealership_id).strip()
        otd_price = float(offer.get("otd_price") or 0.0)

        if not dealership_id or not vehicle_id:
            continue

        trend = get_offer_trend_summary(db, dealership_id=dealership_id, vehicle_key=vehicle_id)

        if trend.days_on_market is not None and trend.days_on_market >= dom_threshold:
            create_or_touch_saved_search_alert(
                db,
                saved_search_id=saved_search_id,
                alert_type="dom_threshold",
                dealership_id=dealership_id,
                vehicle_id=vehicle_id,
                title=f"DOM {trend.days_on_market}d: {vehicle_label}",
                message=f"{dealer_name} listing reached {trend.days_on_market} days on market.",
                metadata={
                    "days_on_market": trend.days_on_market,
                    "days_on_market_bucket": trend.days_on_market_bucket,
                    "otd_price": otd_price,
                },
            )
            created += 1

        if trend.price_drop_7d is not None and trend.price_drop_7d >= drop_7d_threshold:
            create_or_touch_saved_search_alert(
                db,
                saved_search_id=saved_search_id,
                alert_type="price_drop_7d",
                dealership_id=dealership_id,
                vehicle_id=vehicle_id,
                title=f"7d drop ${trend.price_drop_7d:,.0f}: {vehicle_label}",
                message=f"{dealer_name} dropped by ${trend.price_drop_7d:,.0f} in 7 days.",
                metadata={
                    "price_drop_7d": trend.price_drop_7d,
                    "otd_price": otd_price,
                },
            )
            created += 1

        if trend.price_drop_30d is not None and trend.price_drop_30d >= drop_30d_threshold:
            create_or_touch_saved_search_alert(
                db,
                saved_search_id=saved_search_id,
                alert_type="price_drop_30d",
                dealership_id=dealership_id,
                vehicle_id=vehicle_id,
                title=f"30d drop ${trend.price_drop_30d:,.0f}: {vehicle_label}",
                message=f"{dealer_name} dropped by ${trend.price_drop_30d:,.0f} in 30 days.",
                metadata={
                    "price_drop_30d": trend.price_drop_30d,
                    "otd_price": otd_price,
                },
            )
            created += 1

    return created


def run_cycle(limit: int = 50) -> dict[str, int]:
    init_db()

    searched = 0
    snapshots_written = 0
    offers_seen = 0
    alerts_created = 0

    dom_threshold = int(os.getenv("ALERT_DOM_THRESHOLD_DAYS", "45"))
    drop_7d_threshold = float(os.getenv("ALERT_PRICE_DROP_7D", "500"))
    drop_30d_threshold = float(os.getenv("ALERT_PRICE_DROP_30D", "1500"))

    with SessionLocal() as db:
        saved_searches = list_saved_searches(db, limit=limit)

        for search in saved_searches:
            targets = [
                {
                    "make": target.make,
                    "model": target.model,
                    "year": target.year,
                    "trim": target.trim,
                }
                for target in search.targets
            ]
            dealer_sites = [site.model_dump() for site in search.dealer_sites] if search.dealer_sites else None

            raw_offers = search_local_offers(
                user_zip=search.user_zip,
                radius_miles=search.radius_miles,
                budget_otd=search.budget_otd,
                targets=targets,
                dealer_sites=dealer_sites,
                include_in_transit=search.include_in_transit,
                include_pre_sold=search.include_pre_sold,
                include_hidden=search.include_hidden,
            )

            sanitized = _sanitize_offers(raw_offers)
            if sanitized:
                upsert_offer_observations(db, sanitized)
                snapshots_written += len(sanitized)
                alerts_created += _generate_alerts(
                    db,
                    saved_search_id=search.id,
                    offers=sanitized,
                    dom_threshold=dom_threshold,
                    drop_7d_threshold=drop_7d_threshold,
                    drop_30d_threshold=drop_30d_threshold,
                )

            offers_seen += len(raw_offers)
            searched += 1

    return {
        "searches": searched,
        "offers_seen": offers_seen,
        "snapshots_written": snapshots_written,
        "alerts_created": alerts_created,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh saved searches and persist offer observations")
    parser.add_argument("--limit", type=int, default=50, help="Max number of saved searches to process")
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    print(f"[{started}] saved-search refresh cycle started")
    result = run_cycle(limit=max(1, min(args.limit, 500)))
    ended = datetime.now(timezone.utc).isoformat()
    print(
        f"[{ended}] saved-search refresh completed: searches={result['searches']}, offers_seen={result['offers_seen']}, snapshots_written={result['snapshots_written']}, alerts_created={result['alerts_created']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


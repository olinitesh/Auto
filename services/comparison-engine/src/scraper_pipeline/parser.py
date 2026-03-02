from __future__ import annotations

from datetime import datetime, timezone

from .types import ParsedListing, ScrapeJob


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _to_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


class ListingParser:
    """Parses source-specific raw payload into a common ParsedListing shape."""

    def parse(self, job: ScrapeJob) -> ParsedListing:
        p = job.payload
        now = datetime.now(timezone.utc)
        return ParsedListing(
            source=job.source,
            external_id=str(p.get("id") or p.get("external_id") or p.get("vin") or "unknown"),
            dealership_id=str(p.get("dealership_id") or "unknown-dealer"),
            dealership_name=str(p.get("dealership_name") or "Unknown Dealer"),
            distance_miles=_to_float(p.get("distance_miles")),
            vin=(str(p["vin"]).strip().upper() if p.get("vin") else None),
            year=int(p.get("year") or 0),
            make=str(p.get("make") or "").strip(),
            model=str(p.get("model") or "").strip(),
            trim=(str(p.get("trim")).strip() if p.get("trim") else None),
            listed_price=_to_float(p.get("listed_price")),
            fees=_to_float(p.get("fees")),
            market_adjustment=_to_float(p.get("market_adjustment")),
            mileage=_to_int(p.get("mileage")),
            listing_url=(str(p.get("listing_url")).strip() if p.get("listing_url") else None),
            dealer_url=(str(p.get("dealer_url")).strip() if p.get("dealer_url") else None),
            provider_days_on_market=_to_int(p.get("provider_days_on_market") or p.get("days_on_market")),
            inventory_status=(str(p.get("inventory_status")).strip() if p.get("inventory_status") else None),
            is_in_transit=_to_bool(p.get("is_in_transit")),
            is_pre_sold=_to_bool(p.get("is_pre_sold")),
            is_hidden=_to_bool(p.get("is_hidden")),
            scraped_at=now,
        )

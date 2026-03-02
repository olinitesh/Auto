from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .types import ScrapeJob


@dataclass(slots=True)
class MarketCheckClient:
    api_key: str
    base_url: str = "https://api.marketcheck.com/v2/search/car/active"
    timeout_seconds: float = 20.0

    def fetch_jobs(
        self,
        *,
        user_zip: str,
        radius_miles: int,
        budget_otd: float,
        targets: list[dict],
        rows_per_target: int = 25,
    ) -> list[ScrapeJob]:
        jobs: list[ScrapeJob] = []

        with httpx.Client(timeout=self.timeout_seconds, headers={"Accept": "application/json"}) as client:
            for target in targets:
                base_params: dict[str, Any] = {
                    "api_key": self.api_key,
                    "zip": user_zip,
                    "radius": radius_miles,
                    "rows": rows_per_target,
                    "seller_type": "dealer",
                    "make": target.get("make"),
                    "model": target.get("model"),
                }

                trim = target.get("trim")
                if trim:
                    base_params["trim"] = trim

                year = target.get("year")
                if year:
                    params = dict(base_params)
                    params["year"] = year
                    listings = self._request_listings(client, params)
                else:
                    listings = self._request_listings(client, base_params)

                if not listings and year:
                    listings = self._request_listings(client, base_params)

                self._append_jobs_from_listings(jobs, listings, budget_otd)

        return jobs

    def _request_listings(self, client: httpx.Client, params: dict[str, Any]) -> list[dict]:
        response = client.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json()
        listings = data.get("listings") or data.get("data") or []
        if isinstance(listings, list):
            return listings
        return []

    def _append_jobs_from_listings(self, jobs: list[ScrapeJob], listings: list[dict], budget_otd: float) -> None:
        for row in listings:
            payload = self._map_listing(row)
            if payload is None:
                continue

            rough_otd = float(payload.get("listed_price", 0.0)) + float(payload.get("fees", 0.0)) + float(
                payload.get("market_adjustment", 0.0)
            )
            if rough_otd > budget_otd * 1.25:
                continue

            jobs.append(ScrapeJob(source="marketcheck", payload=payload))

    def _parse_bool(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _safe_int(self, value: object) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _extract_provider_days_on_market(self, row: dict) -> int | None:
        for key in ("dom", "dom_active", "days_on_market", "daysonmarket", "daysonmarket_active"):
            value = self._safe_int(row.get(key))
            if value is not None and value >= 0:
                return value
        return None

    def _map_listing(self, row: dict) -> dict | None:
        dealer = row.get("dealer") if isinstance(row.get("dealer"), dict) else {}
        build = row.get("build") if isinstance(row.get("build"), dict) else {}

        vin = row.get("vin")
        year = row.get("year") or build.get("year")
        make = row.get("make") or build.get("make")
        model = row.get("model") or build.get("model")

        if not (year and make and model):
            return None

        dealer_id = str(row.get("dealer_id") or dealer.get("id") or "unknown-dealer")
        dealer_name = str(row.get("dealer_name") or dealer.get("name") or "Unknown Dealer")
        dealer_zip = str(row.get("dealer_zip") or dealer.get("zip") or dealer.get("zipcode") or row.get("zip") or "")

        distance = row.get("dist") or row.get("distance") or 0.0
        listed_price = row.get("price") or row.get("selling_price") or row.get("msrp") or 0.0
        fees = row.get("fees") or 0.0
        market_adjustment = row.get("market_adjustment") or row.get("dealer_markup") or 0.0

        inventory_status = (
            str(row.get("inventory_status") or row.get("status") or row.get("car_status") or "").strip() or None
        )
        lower_status = (inventory_status or "").lower()

        is_in_transit = self._parse_bool(row.get("is_in_transit") or row.get("in_transit"))
        is_pre_sold = self._parse_bool(row.get("is_pre_sold") or row.get("pre_sold") or row.get("is_presold"))
        is_hidden = self._parse_bool(row.get("is_hidden") or row.get("hidden") or row.get("hide"))

        if not is_in_transit and "transit" in lower_status:
            is_in_transit = True
        if not is_pre_sold and ("pre" in lower_status and "sold" in lower_status):
            is_pre_sold = True
        if not is_hidden and "hidden" in lower_status:
            is_hidden = True

        listing_url = str(row.get("vdp_url") or row.get("vdpUrl") or row.get("vdp") or "").strip() or None
        dealer_url = str(row.get("dealer_website") or row.get("dealerWebsite") or dealer.get("website") or "").strip() or None

        return {
            "id": str(row.get("id") or row.get("inventory_id") or vin or row.get("heading") or "unknown"),
            "dealership_id": dealer_id,
            "dealership_name": dealer_name,
            "dealer_zip": dealer_zip,
            "distance_miles": float(distance or 0.0),
            "vin": str(vin).upper() if vin else None,
            "year": int(year),
            "make": str(make),
            "model": str(model),
            "trim": row.get("trim") or build.get("trim"),
            "listed_price": float(listed_price or 0.0),
            "fees": float(fees or 0.0),
            "market_adjustment": float(market_adjustment or 0.0),
            "mileage": row.get("miles") or row.get("mileage"),
            "listing_url": listing_url,
            "dealer_url": dealer_url,
            "provider_days_on_market": self._extract_provider_days_on_market(row),
            "inventory_status": inventory_status,
            "is_in_transit": is_in_transit,
            "is_pre_sold": is_pre_sold,
            "is_hidden": is_hidden,
        }

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from .types import ScrapeJob


class MarketCheckRateLimitedError(RuntimeError):
    pass


@dataclass(slots=True)
class MarketCheckClient:
    api_key: str
    base_url: str = "https://api.marketcheck.com/v2/search/car/active"
    timeout_seconds: float = 20.0
    max_retries: int = 2
    backoff_seconds: float = 1.0

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
                target_make = str(target.get("make") or "").strip()
                target_model = str(target.get("model") or "").strip()
                target_trim = str(target.get("trim") or "").strip() or None

                # Handle model strings like "CR-V Hybrid" by splitting into model + trim when trim is empty.
                if "hybrid" in target_model.lower() and not target_trim:
                    normalized_model = " ".join(
                        part for part in target_model.split() if part.lower() != "hybrid"
                    ).strip()
                    if normalized_model:
                        target_model = normalized_model
                        target_trim = "Hybrid"

                seen_listing_keys: set[str] = set()
                listings: list[dict] = []
                rate_limited = False

                # Keep external call volume bounded: try a small, prioritized query set.
                candidates = self._build_query_candidates(
                    make=target_make,
                    model=target_model,
                    trim=target_trim,
                    year=target.get("year"),
                    user_zip=user_zip,
                    radius_miles=radius_miles,
                    rows_per_target=rows_per_target,
                )

                for params in candidates:
                    try:
                        queried = self._request_listings(client, params)
                    except MarketCheckRateLimitedError:
                        # Stop issuing more requests in this cycle once API throttles us.
                        rate_limited = True
                        break

                    for row in queried:
                        key = str(row.get("id") or row.get("inventory_id") or row.get("vin") or "")
                        if key and key in seen_listing_keys:
                            continue
                        if key:
                            seen_listing_keys.add(key)
                        listings.append(row)

                    if listings:
                        break

                self._append_jobs_from_listings(jobs, listings, budget_otd)

                if rate_limited:
                    break

        return jobs

    def _build_query_candidates(
        self,
        *,
        make: str,
        model: str,
        trim: str | None,
        year: Any,
        user_zip: str,
        radius_miles: int,
        rows_per_target: int,
    ) -> list[dict[str, Any]]:
        model_variants = self._model_variants(model)
        primary_model = model_variants[0] if model_variants else model
        secondary_model = model_variants[1] if len(model_variants) > 1 else None

        base: dict[str, Any] = {
            "api_key": self.api_key,
            "zip": user_zip,
            "radius": min(radius_miles, 100),
            "rows": rows_per_target,
            "seller_type": "dealer",
            "make": make,
        }

        candidates: list[dict[str, Any]] = []

        def add_candidate(*, m: str | None, t: str | None, y: Any | None) -> None:
            if not m:
                return
            params = dict(base)
            params["model"] = m
            if t:
                params["trim"] = t
            if y:
                params["year"] = y
            candidates.append(params)

        trim_variants = self._trim_variants(trim)

        # 1) Most specific request (including trim aliases such as "Woodland Edition").
        if trim_variants:
            for trim_variant in trim_variants:
                add_candidate(m=primary_model, t=trim_variant, y=year)
        else:
            add_candidate(m=primary_model, t=None, y=year)

        # 2) Drop trim if needed
        if trim:
            add_candidate(m=primary_model, t=None, y=year)

        # 3) One alternate model alias (e.g., CR-V -> CRV)
        if secondary_model:
            if trim_variants:
                add_candidate(m=secondary_model, t=trim_variants[0], y=year)
            else:
                add_candidate(m=secondary_model, t=None, y=year)

        # 4) Last resort: broaden by removing year once
        if year:
            add_candidate(m=primary_model, t=None, y=None)

        return candidates

    def _model_variants(self, model: str) -> list[str]:
        base = model.strip()
        if not base:
            return [base]

        variants: list[str] = [base]
        compact = base.replace(" ", "")
        dashed = base.replace(" ", "-")

        for candidate in (compact, dashed, base.replace("-", ""), base.replace("-", " ")):
            candidate = candidate.strip()
            if candidate and candidate.lower() not in {v.lower() for v in variants}:
                variants.append(candidate)

        if base.lower() == "cr-v" and "crv" not in {v.lower() for v in variants}:
            variants.append("CRV")
        if base.lower() == "crv" and "cr-v" not in {v.lower() for v in variants}:
            variants.append("CR-V")

        return variants

    def _trim_variants(self, trim: str | None) -> list[str]:
        if not trim:
            return []

        base = trim.strip()
        if not base:
            return []

        variants: list[str] = [base]
        lower = base.lower()

        if lower == "woodland":
            variants.append("Woodland Edition")
        if lower.endswith(" edition"):
            variants.append(base[: -len(" edition")].strip())

        deduped: list[str] = []
        seen: set[str] = set()
        for value in variants:
            key = value.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(value)
        return deduped

    def _request_listings(self, client: httpx.Client, params: dict[str, Any]) -> list[dict]:
        for attempt in range(self.max_retries + 1):
            response = client.get(self.base_url, params=params)

            if response.status_code == 429:
                if attempt >= self.max_retries:
                    raise MarketCheckRateLimitedError("marketcheck rate limit (429)")
                time.sleep(self._retry_after_seconds(response, attempt))
                continue

            response.raise_for_status()
            data = response.json()
            listings = data.get("listings") or data.get("data") or []
            if isinstance(listings, list):
                return listings
            return []

        raise MarketCheckRateLimitedError("marketcheck rate limit (429)")

    def _retry_after_seconds(self, response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                seconds = int(value)
                if seconds > 0:
                    return min(float(seconds), 20.0)
            except ValueError:
                pass
        return min(self.backoff_seconds * (2**attempt), 10.0)

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
        msrp = row.get("msrp") or build.get("msrp")
        advertised_price = row.get("advertised_price") or row.get("advertized_price") or row.get("price")
        selling_price = row.get("selling_price") or row.get("price")
        dealer_discount = None
        try:
            if msrp is not None and advertised_price is not None:
                discount = float(msrp) - float(advertised_price)
                if discount > 0:
                    dealer_discount = discount
        except (TypeError, ValueError):
            dealer_discount = None
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
            "msrp": float(msrp) if msrp is not None else None,
            "advertised_price": float(advertised_price) if advertised_price is not None else None,
            "selling_price": float(selling_price) if selling_price is not None else None,
            "dealer_discount": float(dealer_discount) if dealer_discount is not None else None,
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




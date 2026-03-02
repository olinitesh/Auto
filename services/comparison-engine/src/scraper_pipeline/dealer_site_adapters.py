from __future__ import annotations

import html as html_lib
import json
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class DealerSiteAdapter(ABC):
    """Base parser adapter for dealer inventory HTML payloads."""

    adapter_key: str

    @abstractmethod
    def parse_inventory_html(self, *, html: str) -> list[dict]:
        raise NotImplementedError


class HondaDealerAdapter(DealerSiteAdapter):
    adapter_key = "honda"

    _card_pattern = re.compile(
        r'<div[^>]*class="[^"]*vehicle-card[^"]*"[^>]*data-vin="(?P<vin>[^"]*)"[^>]*data-year="(?P<year>[^"]*)"[^>]*data-make="(?P<make>[^"]*)"[^>]*data-model="(?P<model>[^"]*)"[^>]*data-trim="(?P<trim>[^"]*)"[^>]*data-price="(?P<price>[^"]*)"[^>]*data-mileage="(?P<mileage>[^"]*)"',
        re.IGNORECASE,
    )

    def parse_inventory_html(self, *, html: str) -> list[dict]:
        listings: list[dict] = []
        for idx, match in enumerate(self._card_pattern.finditer(html), start=1):
            gd = match.groupdict()
            listings.append(
                {
                    "id": f"honda-card-{idx}",
                    "vin": (gd.get("vin") or None),
                    "year": int(gd.get("year") or 0),
                    "make": gd.get("make") or "Honda",
                    "model": gd.get("model") or "",
                    "trim": gd.get("trim") or None,
                    "listed_price": _safe_float(gd.get("price")),
                    "fees": 0.0,
                    "market_adjustment": 0.0,
                    "mileage": int(_safe_float(gd.get("mileage"), 0.0)),
                }
            )
        return listings


class ToyotaDealerAdapter(DealerSiteAdapter):
    adapter_key = "toyota"

    _inventory_json_pattern = re.compile(
        r"window\.__INITIAL_INVENTORY__\s*=\s*(?P<json>\[.*?\])\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    _next_data_pattern = re.compile(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>\s*(?P<json>\{.*?\})\s*</script>',
        re.IGNORECASE | re.DOTALL,
    )
    _embedded_html_json_pattern = re.compile(
        r"txtSit\.innerHTML\s*=\s*`(?P<json>\{.*?\})`;",
        re.IGNORECASE | re.DOTALL,
    )
    _window_json_object_patterns = [
        re.compile(r"window\.__INITIAL_STATE__\s*=\s*(?P<json>\{.*?\})\s*;", re.IGNORECASE | re.DOTALL),
        re.compile(r"window\.__APOLLO_STATE__\s*=\s*(?P<json>\{.*?\})\s*;", re.IGNORECASE | re.DOTALL),
    ]

    def _safe_int(self, value: object, default: int = 0) -> int:
        try:
            return int(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    def _extract_candidates(self, value: object) -> Iterable[dict]:
        if isinstance(value, dict):
            norm_keys = {str(key).lower() for key in value.keys()}
            has_vehicle_shape = (
                ("model" in norm_keys or "modelname" in norm_keys)
                and ("year" in norm_keys or "modelyear" in norm_keys)
                and (
                    "vin" in norm_keys
                    or "id" in norm_keys
                    or "vehicleid" in norm_keys
                    or "price" in norm_keys
                    or "sellingprice" in norm_keys
                    or "dealerprice" in norm_keys
                )
            )
            if has_vehicle_shape:
                yield value

            for nested in value.values():
                yield from self._extract_candidates(nested)
            return

        if isinstance(value, list):
            for nested in value:
                yield from self._extract_candidates(nested)

    def _to_listing(self, item: dict, idx: int) -> dict | None:
        year = self._safe_int(item.get("year") or item.get("modelYear"))
        make = str(item.get("make") or item.get("makeName") or "Toyota").strip()
        model = str(item.get("model") or item.get("modelName") or item.get("modelCode") or "").strip()
        if not model or year <= 0:
            return None

        trim = item.get("trim") or item.get("grade") or item.get("gradeName")
        vin = item.get("vin") or item.get("VIN")
        listed_price = (
            item.get("price")
            or item.get("sellingPrice")
            or item.get("dealerPrice")
            or item.get("advertisedPrice")
            or item.get("msrp")
            or item.get("totalMsrp")
        )
        fees = item.get("fees") or item.get("dealerFees") or 0.0
        market_adjustment = item.get("market_adjustment") or item.get("marketAdjustment") or 0.0
        mileage = item.get("mileage") or item.get("odometer") or item.get("odometerValue") or 0

        listing_id = (
            item.get("id")
            or item.get("vehicleId")
            or item.get("stockNumber")
            or item.get("stockNo")
            or vin
            or f"toyota-item-{idx}"
        )

        return {
            "id": str(listing_id),
            "vin": str(vin).strip().upper() if vin else None,
            "year": year,
            "make": make,
            "model": model,
            "trim": str(trim).strip() if trim else None,
            "listed_price": _safe_float(listed_price),
            "fees": _safe_float(fees),
            "market_adjustment": _safe_float(market_adjustment),
            "mileage": int(_safe_float(mileage, 0.0)),
        }

    def _append_candidates(self, *, source_data: object, listings: list[dict], seen_ids: set[str]) -> None:
        for idx, candidate in enumerate(self._extract_candidates(source_data), start=1):
            listing = self._to_listing(candidate, idx)
            if listing is None or listing["id"] in seen_ids:
                continue
            seen_ids.add(listing["id"])
            listings.append(listing)

    def parse_inventory_html(self, *, html: str) -> list[dict]:
        listings: list[dict] = []
        seen_ids: set[str] = set()

        # Legacy/static format
        legacy_match = self._inventory_json_pattern.search(html)
        if legacy_match:
            try:
                parsed = json.loads(legacy_match.group("json"))
            except json.JSONDecodeError:
                parsed = []
            self._append_candidates(source_data=parsed, listings=listings, seen_ids=seen_ids)

        # Next.js payloads
        next_data_match = self._next_data_pattern.search(html)
        if next_data_match:
            try:
                next_data = json.loads(next_data_match.group("json"))
            except json.JSONDecodeError:
                next_data = {}
            self._append_candidates(source_data=next_data, listings=listings, seen_ids=seen_ids)

        # Embedded JSON assigned via HTML entities in page scripts.
        embedded_match = self._embedded_html_json_pattern.search(html)
        if embedded_match:
            raw = html_lib.unescape(embedded_match.group("json"))
            try:
                embedded_data = json.loads(raw)
            except json.JSONDecodeError:
                embedded_data = {}
            self._append_candidates(source_data=embedded_data, listings=listings, seen_ids=seen_ids)

        # Other common bootstrapped JSON object globals.
        for pattern in self._window_json_object_patterns:
            match = pattern.search(html)
            if not match:
                continue
            try:
                data = json.loads(match.group("json"))
            except json.JSONDecodeError:
                continue
            self._append_candidates(source_data=data, listings=listings, seen_ids=seen_ids)

        return listings


def get_adapter(adapter_key: str) -> DealerSiteAdapter | None:
    key = adapter_key.strip().lower()
    if key == "honda":
        return HondaDealerAdapter()
    if key == "toyota":
        return ToyotaDealerAdapter()
    return None

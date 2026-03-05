from __future__ import annotations

import re

from .live_agent import LiveDealerDataAgent
from .pipeline import process_jobs


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _model_matches(target_model: str, item_model: str) -> bool:
    if not target_model:
        return True
    if item_model == target_model:
        return True
    # Allow common provider variants like "RAV4" vs "RAV4 Hybrid" while still rejecting unrelated models.
    return target_model in item_model or item_model in target_model


def _matches_target_base(item: object, target: dict) -> bool:
    target_make = _norm(target.get("make"))
    target_model = _norm(target.get("model"))
    target_trim = _norm(target.get("trim"))

    item_make = _norm(getattr(item, "make", ""))
    item_model = _norm(getattr(item, "model", ""))
    item_trim = _norm(getattr(item, "trim", ""))

    if target_make and item_make != target_make:
        return False
    if not _model_matches(target_model, item_model):
        return False
    if target_trim and target_trim not in item_trim:
        return False
    return True


def _has_year_for_target(items: list[object], target: dict) -> bool:
    target_year = target.get("year")
    if not target_year:
        return False
    target_year_str = str(target_year)

    for item in items:
        if not _matches_target_base(item, target):
            continue
        item_year = getattr(item, "year", None)
        if item_year is not None and str(item_year) == target_year_str:
            return True
    return False


def _matches_target(item: object, target: dict, enforce_year: bool) -> bool:
    if not _matches_target_base(item, target):
        return False

    target_year = target.get("year")
    if enforce_year and target_year:
        item_year = getattr(item, "year", None)
        if item_year is None or str(item_year) != str(target_year):
            return False

    return True


def _matches_any_target(item: object, targets: list[dict], enforce_year_flags: list[bool]) -> bool:
    for idx, target in enumerate(targets):
        enforce_year = enforce_year_flags[idx] if idx < len(enforce_year_flags) else False
        if _matches_target(item, target, enforce_year=enforce_year):
            return True
    return False


def search_local_offers(
    *,
    user_zip: str,
    radius_miles: int,
    budget_otd: float,
    targets: list[dict],
    dealer_sites: list[dict] | None = None,
    include_in_transit: bool = True,
    include_pre_sold: bool = False,
    include_hidden: bool = False,
) -> list[dict]:
    agent = LiveDealerDataAgent()
    agent_result = agent.collect(
        user_zip=user_zip,
        radius_miles=radius_miles,
        budget_otd=budget_otd,
        targets=targets,
        dealer_sites=dealer_sites,
    )

    normalized = process_jobs(agent_result.jobs)
    enforce_year_flags = [_has_year_for_target(normalized, target) for target in targets]

    offers: list[dict] = []
    for idx, item in enumerate(normalized, start=1):
        if not _matches_any_target(item, targets, enforce_year_flags):
            continue
        if item.is_in_transit and not include_in_transit:
            continue
        if item.is_pre_sold and not include_pre_sold:
            continue
        if item.is_hidden and not include_hidden:
            continue

        vehicle_label = f"{item.year} {item.make} {item.model}" + (f" {item.trim}" if item.trim else "")
        offer = {
            "offer_id": f"{item.dealership_id}-{item.external_id}-{idx}",
            "dealership_id": item.dealership_id,
            "dealership_name": item.dealership_name,
            "distance_miles": item.distance_miles,
            "vehicle_id": item.vin or item.external_id,
            "vehicle_label": vehicle_label,
            "otd_price": item.otd_price,
            "listed_price": item.listed_price,
            "msrp": item.msrp,
            "advertised_price": item.advertised_price,
            "selling_price": item.selling_price,
            "dealer_discount": item.dealer_discount,
            "fees": item.fees,
            "market_adjustment": item.market_adjustment,
            "specs_score": 80.0 if item.trim else 72.0,
            "data_provider": agent_result.provider,
            "provider_days_on_market": item.provider_days_on_market,
            "inventory_status": item.inventory_status,
            "is_in_transit": item.is_in_transit,
            "is_pre_sold": item.is_pre_sold,
            "is_hidden": item.is_hidden,
            "year": item.year,
            "make": item.make,
            "model": item.model,
            "trim": item.trim,
            "vin": item.vin,
            "listing_url": item.listing_url,
            "dealer_url": item.dealer_url,
        }
        offers.append(offer)

    return offers



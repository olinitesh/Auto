from __future__ import annotations

from .live_agent import LiveDealerDataAgent
from .pipeline import process_jobs


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

    offers: list[dict] = []
    for idx, item in enumerate(normalized, start=1):
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

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ScrapeJob:
    source: str
    payload: dict


@dataclass(slots=True)
class ParsedListing:
    source: str
    external_id: str
    dealership_id: str
    dealership_name: str
    distance_miles: float
    vin: str | None
    year: int
    make: str
    model: str
    trim: str | None
    listed_price: float
    fees: float
    market_adjustment: float
    mileage: int | None
    listing_url: str | None
    dealer_url: str | None
    provider_days_on_market: int | None
    inventory_status: str | None
    is_in_transit: bool
    is_pre_sold: bool
    is_hidden: bool
    scraped_at: datetime


@dataclass(slots=True)
class NormalizedListing:
    source: str
    external_id: str
    dedupe_key: str
    dealership_id: str
    dealership_name: str
    distance_miles: float
    vin: str | None
    year: int
    make: str
    model: str
    trim: str | None
    listed_price: float
    fees: float
    market_adjustment: float
    otd_price: float
    mileage: int | None
    listing_url: str | None
    dealer_url: str | None
    provider_days_on_market: int | None
    inventory_status: str | None
    is_in_transit: bool
    is_pre_sold: bool
    is_hidden: bool
    scraped_at: datetime

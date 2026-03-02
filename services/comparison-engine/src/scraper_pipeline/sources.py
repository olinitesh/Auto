from __future__ import annotations

from .types import ScrapeJob


def sample_jobs() -> list[ScrapeJob]:
    """Sample scrape payloads representing multiple dealer/source formats."""

    return [
        ScrapeJob(
            source="dealer-site-a",
            payload={
                "id": "a-1001",
                "dealership_id": "d1",
                "dealership_name": "Metro Honda",
                "vin": "19XFL2H8XRE000111",
                "year": 2025,
                "make": "honda",
                "model": "civic",
                "trim": "ex",
                "listed_price": "28990",
                "fees": "1120",
                "market_adjustment": "0",
                "mileage": "11",
            },
        ),
        ScrapeJob(
            source="dealer-site-b",
            payload={
                "external_id": "b-55",
                "dealership_id": "d5",
                "dealership_name": "Valley Auto Mall",
                "vin": "19XFL2H8XRE000111",
                "year": 2025,
                "make": "Honda",
                "model": "Civic",
                "trim": "EX",
                "listed_price": 29150,
                "fees": 980,
                "market_adjustment": 400,
                "mileage": 9,
            },
        ),
        ScrapeJob(
            source="dealer-site-c",
            payload={
                "id": "c-901",
                "dealership_id": "d2",
                "dealership_name": "Sunrise Toyota",
                "year": 2025,
                "make": "toyota",
                "model": "corolla",
                "trim": "xse",
                "listed_price": 27999,
                "fees": 995,
                "market_adjustment": 250,
                "mileage": 5,
            },
        ),
    ]

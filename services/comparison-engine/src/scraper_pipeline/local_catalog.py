from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from .types import ScrapeJob

# Minimal ZIP centroid map for local development search behavior.
ZIP_COORDS: dict[str, tuple[float, float]] = {
    "18706": (41.2417, -75.8895),
    "18702": (41.2334, -75.8738),
    "18640": (41.3356, -75.7338),
    "18509": (41.4248, -75.6522),
    "19103": (39.9529, -75.1741),
    "10001": (40.7506, -73.9972),
    "07030": (40.7440, -74.0324),
    "15222": (40.4473, -79.9930),
    "60601": (41.8864, -87.6186),
    "78701": (30.2711, -97.7437),
    "78753": (30.3824, -97.6801),
    "78758": (30.3876, -97.7061),
    "78613": (30.5052, -97.8203),
    "30303": (33.7525, -84.3915),
    "90012": (34.0614, -118.2396),
    "94105": (37.7898, -122.3942),
}

LOCAL_LISTINGS: list[dict] = [
    {
        "source": "dealer-site-a",
        "id": "pa-honda-1",
        "dealership_id": "d1",
        "dealership_name": "Metro Honda",
        "dealer_zip": "18702",
        "vin": "19XFL2H8XRE000111",
        "year": 2025,
        "make": "Honda",
        "model": "Civic",
        "trim": "EX",
        "listed_price": 28990,
        "fees": 1120,
        "market_adjustment": 0,
        "mileage": 11,
    },
    {
        "source": "dealer-site-b",
        "id": "pa-honda-2",
        "dealership_id": "d5",
        "dealership_name": "Valley Auto Mall",
        "dealer_zip": "18640",
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
    {
        "source": "dealer-site-c",
        "id": "pa-toyota-1",
        "dealership_id": "d2",
        "dealership_name": "Sunrise Toyota",
        "dealer_zip": "18509",
        "year": 2025,
        "make": "Toyota",
        "model": "Corolla",
        "trim": "XSE",
        "listed_price": 27999,
        "fees": 995,
        "market_adjustment": 250,
        "mileage": 5,
    },
    {
        "source": "tx-toyota-1",
        "id": "tx-rav4-1",
        "dealership_id": "d8",
        "dealership_name": "Austin Toyota North",
        "dealer_zip": "78753",
        "year": 2026,
        "make": "Toyota",
        "model": "RAV4",
        "trim": "XLE",
        "listed_price": 36120,
        "fees": 1295,
        "market_adjustment": 0,
        "mileage": 6,
    },
    {
        "source": "tx-toyota-2",
        "id": "tx-rav4-2",
        "dealership_id": "d9",
        "dealership_name": "Hill Country Toyota",
        "dealer_zip": "78613",
        "year": 2026,
        "make": "Toyota",
        "model": "RAV4",
        "trim": "Limited",
        "listed_price": 39800,
        "fees": 1410,
        "market_adjustment": 1500,
        "mileage": 8,
    },
    {
        "source": "tx-honda-1",
        "id": "tx-civic-1",
        "dealership_id": "d10",
        "dealership_name": "Capital Honda",
        "dealer_zip": "78758",
        "year": 2025,
        "make": "Honda",
        "model": "Civic",
        "trim": "Sport",
        "listed_price": 27650,
        "fees": 1180,
        "market_adjustment": 300,
        "mileage": 7,
    },
]


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_miles = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return earth_radius_miles * c


def _zip_coords(zip_code: str) -> tuple[float, float] | None:
    key = zip_code.strip()[:5]
    return ZIP_COORDS.get(key)


def _target_match(listing: dict, targets: list[dict]) -> bool:
    make = str(listing.get("make", "")).strip().lower()
    model = str(listing.get("model", "")).strip().lower()
    year = int(listing.get("year") or 0)
    trim = str(listing.get("trim") or "").strip().lower()

    for target in targets:
        t_make = str(target.get("make") or "").strip().lower()
        t_model = str(target.get("model") or "").strip().lower()
        t_year = int(target.get("year") or 0)
        t_trim = str(target.get("trim") or "").strip().lower()

        if make != t_make or model != t_model or year != t_year:
            continue
        if t_trim and t_trim not in trim:
            continue
        return True
    return False


def build_jobs_for_search(
    *,
    user_zip: str,
    radius_miles: int,
    budget_otd: float,
    targets: list[dict],
) -> list[ScrapeJob]:
    origin = _zip_coords(user_zip)
    jobs: list[ScrapeJob] = []

    for listing in LOCAL_LISTINGS:
        if not _target_match(listing, targets):
            continue

        dealer_zip = str(listing.get("dealer_zip") or "")
        dealer_coords = _zip_coords(dealer_zip)

        # Unknown ZIP centroid fallback to conservative distance at radius edge.
        if origin and dealer_coords:
            distance = _haversine_miles(origin[0], origin[1], dealer_coords[0], dealer_coords[1])
        else:
            distance = float(radius_miles)

        if distance > radius_miles:
            continue

        rough_otd = float(listing.get("listed_price", 0)) + float(listing.get("fees", 0)) + float(
            listing.get("market_adjustment", 0)
        )
        if rough_otd > budget_otd * 1.25:
            continue

        payload = dict(listing)
        payload["distance_miles"] = round(distance, 1)
        jobs.append(ScrapeJob(source=str(listing.get("source") or "catalog"), payload=payload))

    return jobs

from __future__ import annotations

import argparse
import json

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from autohaggle_shared.database import SessionLocal, init_db
from autohaggle_shared.models import Dealer, VehicleListing

from .live_agent import LiveDealerDataAgent
from .pipeline import process_jobs


def _upsert_dealer(db: Session, dealership_id: str, dealership_name: str, distance_miles: float) -> Dealer:
    dealer = db.get(Dealer, dealership_id)
    if dealer is None:
        dealer = Dealer(id=dealership_id, name=dealership_name, distance_miles=distance_miles)
        db.add(dealer)
        db.flush()
        return dealer

    dealer.name = dealership_name
    dealer.distance_miles = distance_miles
    return dealer


def _find_listing(db: Session, *, dealership_id: str, vin: str | None, year: int, make: str, model: str, trim: str | None) -> VehicleListing | None:
    if vin:
        stmt = select(VehicleListing).where(
            and_(VehicleListing.dealership_id == dealership_id, VehicleListing.vin == vin)
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return existing

    stmt = select(VehicleListing).where(
        and_(
            VehicleListing.dealership_id == dealership_id,
            VehicleListing.year == year,
            VehicleListing.make == make,
            VehicleListing.model == model,
            or_(VehicleListing.trim == trim, and_(VehicleListing.trim.is_(None), trim is None)),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def ingest_dealer_data_to_fallback(
    *,
    user_zip: str,
    radius_miles: int,
    budget_otd: float,
    targets: list[dict],
    dealer_sites: list[dict] | None = None,
) -> dict:
    init_db()

    agent = LiveDealerDataAgent()
    agent_result = agent.collect(
        user_zip=user_zip,
        radius_miles=radius_miles,
        budget_otd=budget_otd,
        targets=targets,
        dealer_sites=dealer_sites,
    )

    normalized = process_jobs(agent_result.jobs)

    inserted = 0
    updated = 0

    db: Session = SessionLocal()
    try:
        for item in normalized:
            _upsert_dealer(
                db,
                dealership_id=item.dealership_id,
                dealership_name=item.dealership_name,
                distance_miles=item.distance_miles,
            )

            listing = _find_listing(
                db,
                dealership_id=item.dealership_id,
                vin=item.vin,
                year=item.year,
                make=item.make,
                model=item.model,
                trim=item.trim,
            )

            specs_payload = {
                "fees": item.fees,
                "market_adjustment": item.market_adjustment,
                "otd_price": item.otd_price,
                "mileage": item.mileage,
                "dedupe_key": item.dedupe_key,
            }

            if listing is None:
                listing = VehicleListing(
                    dealership_id=item.dealership_id,
                    vin=item.vin,
                    year=item.year,
                    make=item.make,
                    model=item.model,
                    trim=item.trim,
                    msrp=None,
                    listed_price=item.listed_price,
                    specs=specs_payload,
                    source=item.source,
                )
                db.add(listing)
                inserted += 1
            else:
                listing.vin = item.vin
                listing.year = item.year
                listing.make = item.make
                listing.model = item.model
                listing.trim = item.trim
                listing.listed_price = item.listed_price
                listing.specs = specs_payload
                listing.source = item.source
                updated += 1

        db.commit()
    finally:
        db.close()

    return {
        "provider": agent_result.provider,
        "jobs_collected": len(agent_result.jobs),
        "normalized_count": len(normalized),
        "inserted": inserted,
        "updated": updated,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest dealer listing data into local fallback database.")
    parser.add_argument("--zip", dest="user_zip", required=True, help="User ZIP code for local search context")
    parser.add_argument("--radius", dest="radius_miles", type=int, default=100, help="Search radius in miles")
    parser.add_argument("--budget", dest="budget_otd", type=float, required=True, help="Budget OTD ceiling")
    parser.add_argument(
        "--targets-json",
        required=True,
        help='JSON array of vehicle targets, e.g. [{"make":"Toyota","model":"RAV4","year":2026}]',
    )
    parser.add_argument(
        "--dealer-sites-json",
        required=False,
        default="[]",
        help='Optional JSON array of dealer site sources for direct scrape.',
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    targets = json.loads(args.targets_json)
    dealer_sites = json.loads(args.dealer_sites_json)

    result = ingest_dealer_data_to_fallback(
        user_zip=args.user_zip,
        radius_miles=args.radius_miles,
        budget_otd=args.budget_otd,
        targets=targets,
        dealer_sites=dealer_sites,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

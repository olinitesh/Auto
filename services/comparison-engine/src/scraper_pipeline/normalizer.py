from __future__ import annotations

from .types import NormalizedListing, ParsedListing


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.strip().split())


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


class ListingNormalizer:
    """Normalizes parsed listing values and computes derived totals."""

    def normalize(self, parsed: ParsedListing) -> NormalizedListing:
        make = _title_case(parsed.make)
        model = _title_case(parsed.model)
        trim = _title_case(parsed.trim) if parsed.trim else None

        otd_price = round(parsed.listed_price + parsed.fees + parsed.market_adjustment, 2)

        if parsed.vin:
            dedupe_key = parsed.vin
        else:
            dedupe_key = "|".join(
                [
                    parsed.dealership_id,
                    str(parsed.year),
                    make.lower(),
                    model.lower(),
                    (trim or "").lower(),
                ]
            )

        return NormalizedListing(
            source=parsed.source,
            external_id=parsed.external_id,
            dedupe_key=dedupe_key,
            dealership_id=parsed.dealership_id,
            dealership_name=parsed.dealership_name.strip(),
            distance_miles=round(parsed.distance_miles, 1),
            vin=parsed.vin,
            year=parsed.year,
            make=make,
            model=model,
            trim=trim,
            listed_price=round(parsed.listed_price, 2),
            msrp=_round_or_none(parsed.msrp),
            advertised_price=_round_or_none(parsed.advertised_price),
            selling_price=_round_or_none(parsed.selling_price),
            dealer_discount=_round_or_none(parsed.dealer_discount),
            fees=round(parsed.fees, 2),
            market_adjustment=round(parsed.market_adjustment, 2),
            otd_price=otd_price,
            mileage=parsed.mileage,
            listing_url=parsed.listing_url,
            dealer_url=parsed.dealer_url,
            provider_days_on_market=parsed.provider_days_on_market,
            inventory_status=parsed.inventory_status,
            is_in_transit=parsed.is_in_transit,
            is_pre_sold=parsed.is_pre_sold,
            is_hidden=parsed.is_hidden,
            scraped_at=parsed.scraped_at,
        )

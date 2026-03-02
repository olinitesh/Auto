from __future__ import annotations

from .types import NormalizedListing


class ListingDeduper:
    """Deduplicates listings by key, keeping the lowest OTD listing for each key."""

    def dedupe(self, listings: list[NormalizedListing]) -> list[NormalizedListing]:
        best_by_key: dict[str, NormalizedListing] = {}

        for listing in listings:
            existing = best_by_key.get(listing.dedupe_key)
            if existing is None or listing.otd_price < existing.otd_price:
                best_by_key[listing.dedupe_key] = listing

        return sorted(best_by_key.values(), key=lambda item: (item.otd_price, item.dealership_name))

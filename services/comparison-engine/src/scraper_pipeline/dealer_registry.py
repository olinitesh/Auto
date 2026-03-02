from __future__ import annotations

from dataclasses import dataclass


ZIP_COORDS: dict[str, tuple[float, float]] = {
    "18706": (41.2417, -75.8895),
    "18702": (41.2334, -75.8738),
    "18640": (41.3356, -75.7338),
    "18509": (41.4248, -75.6522),
    "78701": (30.2711, -97.7437),
    "78753": (30.3824, -97.6801),
    "78758": (30.3876, -97.7061),
    "78613": (30.5052, -97.8203),
}


@dataclass(slots=True)
class DealerSource:
    dealer_id: str
    dealer_name: str
    dealer_zip: str
    brand: str
    site_url: str
    inventory_url: str
    adapter_key: str


DEALER_SOURCE_REGISTRY: list[DealerSource] = [
    DealerSource(
        dealer_id="d1",
        dealer_name="Metro Honda",
        dealer_zip="18702",
        brand="honda",
        site_url="https://www.metrohonda.example",
        inventory_url="https://www.metrohonda.example/new-inventory",
        adapter_key="honda",
    ),
    DealerSource(
        dealer_id="d10",
        dealer_name="Capital Honda",
        dealer_zip="78758",
        brand="honda",
        site_url="https://www.capitalhonda.example",
        inventory_url="https://www.capitalhonda.example/new-cars",
        adapter_key="honda",
    ),
    DealerSource(
        dealer_id="d8",
        dealer_name="Austin Toyota North",
        dealer_zip="78753",
        brand="toyota",
        site_url="https://www.austintoyotanorth.example",
        inventory_url="https://www.austintoyotanorth.example/new-inventory",
        adapter_key="toyota",
    ),
    DealerSource(
        dealer_id="d9",
        dealer_name="Hill Country Toyota",
        dealer_zip="78613",
        brand="toyota",
        site_url="https://www.hillcountrytoyota.example",
        inventory_url="https://www.hillcountrytoyota.example/inventory/new",
        adapter_key="toyota",
    ),
]


def sources_for_brands(brands: set[str]) -> list[DealerSource]:
    return [source for source in DEALER_SOURCE_REGISTRY if source.brand.lower() in brands]

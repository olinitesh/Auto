from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
COMPARISON_ENGINE_SRC = ROOT / "services" / "comparison-engine" / "src"
if str(COMPARISON_ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(COMPARISON_ENGINE_SRC))

from scraper_pipeline import search_service


def _build_item(*, trim: str, model: str = "RAV4", year: int = 2025) -> SimpleNamespace:
    return SimpleNamespace(
        dealership_id="dealer-1",
        external_id=f"ext-{trim.lower().replace(' ', '-')}-{year}",
        dealership_name="Test Toyota",
        distance_miles=12.5,
        vin=None,
        year=year,
        make="Toyota",
        model=model,
        trim=trim,
        listed_price=39000.0,
        msrp=42000.0,
        advertised_price=39500.0,
        selling_price=39000.0,
        dealer_discount=3000.0,
        fees=1500.0,
        market_adjustment=0.0,
        otd_price=40500.0,
        provider_days_on_market=20,
        inventory_status="available",
        is_in_transit=False,
        is_pre_sold=False,
        is_hidden=False,
        listing_url="https://dealer.example/vdp/1",
        dealer_url="https://dealer.example",
    )


def test_search_local_offers_filters_to_requested_trim(monkeypatch) -> None:
    items = [
        _build_item(trim="XLE", model="RAV4", year=2025),
        _build_item(trim="Woodland Edition", model="RAV4 Hybrid", year=2025),
    ]

    class StubAgent:
        def collect(self, **kwargs):
            return SimpleNamespace(jobs=[{"id": "stub"}], provider="marketcheck")

    monkeypatch.setattr(search_service, "LiveDealerDataAgent", lambda: StubAgent())
    monkeypatch.setattr(search_service, "process_jobs", lambda jobs: items)

    offers = search_service.search_local_offers(
        user_zip="78701",
        radius_miles=100,
        budget_otd=50000,
        targets=[{"year": 2025, "make": "Toyota", "model": "RAV4", "trim": "Woodland"}],
    )

    assert len(offers) == 1
    assert offers[0]["trim"] == "Woodland Edition"
    assert offers[0]["model"] == "RAV4 Hybrid"


def test_search_local_offers_without_trim_includes_matching_model(monkeypatch) -> None:
    items = [
        _build_item(trim="XLE", year=2025),
        _build_item(trim="Woodland Edition", model="RAV4 Hybrid", year=2025),
        _build_item(trim="Sport", model="Highlander", year=2025),
    ]

    class StubAgent:
        def collect(self, **kwargs):
            return SimpleNamespace(jobs=[{"id": "stub"}], provider="marketcheck")

    monkeypatch.setattr(search_service, "LiveDealerDataAgent", lambda: StubAgent())
    monkeypatch.setattr(search_service, "process_jobs", lambda jobs: items)

    offers = search_service.search_local_offers(
        user_zip="78701",
        radius_miles=100,
        budget_otd=50000,
        targets=[{"year": 2025, "make": "Toyota", "model": "RAV4"}],
    )

    assert len(offers) == 2
    assert {offer["trim"] for offer in offers} == {"XLE", "Woodland Edition"}


def test_search_local_offers_falls_back_to_other_year_when_exact_year_absent(monkeypatch) -> None:
    items = [
        _build_item(trim="Woodland Edition", model="RAV4", year=2025),
        _build_item(trim="XLE", model="RAV4", year=2025),
    ]

    class StubAgent:
        def collect(self, **kwargs):
            return SimpleNamespace(jobs=[{"id": "stub"}], provider="marketcheck")

    monkeypatch.setattr(search_service, "LiveDealerDataAgent", lambda: StubAgent())
    monkeypatch.setattr(search_service, "process_jobs", lambda jobs: items)

    offers = search_service.search_local_offers(
        user_zip="78701",
        radius_miles=100,
        budget_otd=50000,
        targets=[{"year": 2026, "make": "Toyota", "model": "RAV4", "trim": "Woodland"}],
    )

    assert len(offers) == 1
    assert offers[0]["year"] == 2025
    assert offers[0]["trim"] == "Woodland Edition"

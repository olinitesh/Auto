from scraper_pipeline.dealer_scrape_agent import DealerSiteScrapeAgent


def test_toyota_series_codes_include_rav4hybrid_for_rav4_target() -> None:
    agent = DealerSiteScrapeAgent()
    series = agent._toyota_series_codes_from_targets(
        [
            {
                "make": "Toyota",
                "model": "RAV4",
                "year": 2026,
                "trim": "Woodland",
            }
        ]
    )

    codes = {item.strip() for item in series.split(",") if item.strip()}
    assert "rav4" in codes
    assert "rav4hybrid" in codes


def test_toyota_series_codes_include_rav4_for_rav4hybrid_target() -> None:
    agent = DealerSiteScrapeAgent()
    series = agent._toyota_series_codes_from_targets(
        [
            {
                "make": "Toyota",
                "model": "RAV4 Hybrid",
                "year": 2026,
            }
        ]
    )

    codes = {item.strip() for item in series.split(",") if item.strip()}
    assert "rav4hybrid" in codes
    assert "rav4" in codes

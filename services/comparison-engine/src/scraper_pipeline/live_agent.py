from __future__ import annotations

import os
from dataclasses import dataclass

from autohaggle_shared.config import settings

from .dealer_scrape_agent import DealerSiteScrapeAgent
from .local_catalog import build_jobs_for_search
from .marketcheck_adapter import MarketCheckClient
from .types import ScrapeJob


@dataclass(slots=True)
class AgentResult:
    jobs: list[ScrapeJob]
    provider: str


class LiveDealerDataAgent:
    """Collects dealer listing jobs using API-first, fallback-safe strategy."""

    def __init__(self) -> None:
        self.marketcheck_api_key = (settings.marketcheck_api_key or os.getenv("MARKETCHECK_API_KEY", "")).strip()
        self.marketcheck_base_url = (
            settings.marketcheck_base_url
            or os.getenv("MARKETCHECK_BASE_URL", "https://api.marketcheck.com/v2/search/car/active")
        ).strip()
        self.dealer_direct_scrape_enabled = bool(settings.dealer_direct_scrape_enabled)

    def collect(
        self,
        *,
        user_zip: str,
        radius_miles: int,
        budget_otd: float,
        targets: list[dict],
        dealer_sites: list[dict] | None = None,
    ) -> AgentResult:
        # API-first: if aggregator key is configured, always try it before any scraping.
        if self.marketcheck_api_key:
            try:
                client = MarketCheckClient(
                    api_key=self.marketcheck_api_key,
                    base_url=self.marketcheck_base_url,
                )
                jobs = client.fetch_jobs(
                    user_zip=user_zip,
                    radius_miles=radius_miles,
                    budget_otd=budget_otd,
                    targets=targets,
                )
                if jobs:
                    return AgentResult(jobs=jobs, provider="marketcheck")
            except Exception as exc:
                print(f"[live-agent] marketcheck failed: {exc}")
                # Fallback for local dev continuity.
                pass

        # Direct scrape is opt-in only.
        if self.dealer_direct_scrape_enabled:
            try:
                scrape_agent = DealerSiteScrapeAgent()
                scrape_result = scrape_agent.collect_jobs(
                    user_zip=user_zip,
                    radius_miles=radius_miles,
                    budget_otd=budget_otd,
                    targets=targets,
                    dealer_sites=dealer_sites,
                )
                if scrape_result.jobs:
                    return AgentResult(jobs=scrape_result.jobs, provider="dealer-direct-scrape")
            except Exception as exc:
                print(f"[live-agent] dealer direct scrape failed: {exc}")
                pass

        fallback_jobs = build_jobs_for_search(
            user_zip=user_zip,
            radius_miles=radius_miles,
            budget_otd=budget_otd,
            targets=targets,
        )
        return AgentResult(jobs=fallback_jobs, provider="local-catalog")
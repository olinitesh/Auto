from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from uuid import uuid4

import httpx

from .dealer_registry import DealerSource, ZIP_COORDS, sources_for_brands
from .dealer_site_adapters import get_adapter
from .types import ScrapeJob


TOYOTA_GET_MODELS_QUERY = """
query getModels(
  $zipCd: String!
  $brand: String!
  $imageProps: ImageProps!
  $modelCode: [String!]
) {
  models(
    zipCd: $zipCd
    brand: $brand
    imageProps: $imageProps
    modelCode: $modelCode
  ) {
    asShownDisclaimer
    asShown
    families {
      seqNo
      familyType
    }
    image
    modelCode
    msrp
    series
    title
    year
    mpgDisclaimerCode
    mpgeDisclaimerCode
    msrpDisclaimerCode
    topLabel {
      textField
    }
  }
}
""".strip()

TOYOTA_LOCATE_VEHICLES_QUERY = """
query locateVehiclesByZipQuery(
  $zipCode: String!
  $distance: Int!
  $pageNo: Int!
  $pageSize: Int!
  $seriesCodes: String!
  $leadid: String!
) {
  locateVehiclesByZip(
    zipCode: $zipCode
    brand: "TOYOTA"
    pageNo: $pageNo
    pageSize: $pageSize
    seriesCodes: $seriesCodes
    distance: $distance
    leadid: $leadid
    interiorMedia: true
  ) {
    pagination {
      pageNo
      pageSize
      totalPages
      totalRecords
    }
    vehicleSummary {
      vin
      stockNum
      brand
      marketingSeries
      year
      dealerCd
      dealerMarketingName
      dealerWebsite
      vdpUrl
      distance
      inventoryMileage
      model {
        modelCd
        marketingName
        marketingTitle
      }
      price {
        advertizedPrice
        nonSpAdvertizedPrice
        totalMsrp
        sellingPrice
        dph
        dioTotalMsrp
        dioTotalDealerSellingPrice
        dealerCashApplied
        baseMsrp
      }
    }
  }
}
""".strip()


TOYOTA_DEALER_INFO_QUERY = """
query dealerInfoByZip($zipCode: String!) {
  getDealerInfoSystem(brandId: 1, zipCode: $zipCode, useDd365: true) {
    preferredDealers {
      localDealerCode
      localDealerName
      localPostalAddress {
        postcode {
          value
        }
      }
      localProximityMeasureGroup {
        proximityMeasure {
          value
        }
      }
    }
  }
}
""".strip()


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    earth_radius_miles = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return earth_radius_miles * c


def _zip_coords(zip_code: str) -> tuple[float, float] | None:
    return ZIP_COORDS.get(zip_code.strip()[:5])


def _dealer_source_from_input(item: dict) -> DealerSource | None:
    required = ["dealer_id", "dealer_name", "dealer_zip", "brand", "site_url", "inventory_url", "adapter_key"]
    if any(not item.get(key) for key in required):
        return None
    return DealerSource(
        dealer_id=str(item["dealer_id"]),
        dealer_name=str(item["dealer_name"]),
        dealer_zip=str(item["dealer_zip"]),
        brand=str(item["brand"]),
        site_url=str(item["site_url"]),
        inventory_url=str(item["inventory_url"]),
        adapter_key=str(item["adapter_key"]),
    )


@dataclass(slots=True)
class DealerScrapeResult:
    jobs: list[ScrapeJob]
    attempted_sources: int


class DealerSiteScrapeAgent:
    """Registry-driven scraper agent for direct dealer-site ingestion."""

    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.toyota_graphql_endpoint = os.getenv(
            "TOYOTA_GRAPHQL_ENDPOINT", "https://api.search-inventory.toyota.com/graphql"
        ).strip()
        self.toyota_graphql_origin = os.getenv("TOYOTA_GRAPHQL_ORIGIN", "https://www.toyota.com").strip()
        self.toyota_graphql_referer = os.getenv("TOYOTA_GRAPHQL_REFERER", "https://www.toyota.com/").strip()
        self.toyota_graphql_user_agent = os.getenv(
            "TOYOTA_GRAPHQL_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        ).strip()
        self.toyota_debug = os.getenv("TOYOTA_GRAPHQL_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}

    def collect_jobs(
        self,
        *,
        user_zip: str,
        radius_miles: int,
        budget_otd: float,
        targets: list[dict],
        dealer_sites: list[dict] | None = None,
    ) -> DealerScrapeResult:
        sources: list[DealerSource]
        if dealer_sites:
            parsed_sources = [_dealer_source_from_input(item) for item in dealer_sites]
            sources = [item for item in parsed_sources if item is not None]
        else:
            brands = {str(t.get("make") or "").strip().lower() for t in targets if t.get("make")}
            sources = sources_for_brands(brands)

        jobs: list[ScrapeJob] = []
        origin = _zip_coords(user_zip)

        for source in sources:
            if not self._within_radius(origin=origin, dealer=source, radius_miles=radius_miles):
                continue

            adapter = get_adapter(source.adapter_key)
            if adapter is None:
                continue

            raw_listings: list[dict] = []

            html = self._fetch_inventory_html(source.inventory_url)
            if html:
                raw_listings = adapter.parse_inventory_html(html=html)

            # Toyota search pages are JS-heavy; fallback to GraphQL inventory/model feeds.
            if not raw_listings and self._is_toyota_source(source):
                raw_listings = self._fetch_toyota_vehicle_summaries(
                    user_zip=user_zip,
                    radius_miles=radius_miles,
                    targets=targets,
                )
            if not raw_listings and self._is_toyota_source(source):
                raw_listings = self._fetch_toyota_models(user_zip=user_zip)

            if not raw_listings:
                continue

            for item in raw_listings:
                if not self._target_match(item, targets):
                    continue

                listed_price = float(item.get("listed_price") or 0.0)
                fees = float(item.get("fees") or 0.0)
                market_adjustment = float(item.get("market_adjustment") or 0.0)
                rough_otd = listed_price + fees + market_adjustment
                if rough_otd > budget_otd * 1.25:
                    continue

                payload = {
                    **item,
                    "dealership_id": str(item.get("dealership_id") or source.dealer_id),
                    "dealership_name": str(item.get("dealership_name") or source.dealer_name),
                    "dealer_zip": str(item.get("dealer_zip") or source.dealer_zip),
                    "distance_miles": float(
                        item.get("distance_miles")
                        if item.get("distance_miles") is not None
                        else self._distance(origin, source)
                    ),
                }
                jobs.append(ScrapeJob(source=f"dealer-site:{source.adapter_key}", payload=payload))

        return DealerScrapeResult(jobs=jobs, attempted_sources=len(sources))

    def _fetch_inventory_html(self, url: str) -> str | None:
        try:
            with httpx.Client(timeout=self.timeout_seconds, headers={"User-Agent": "AutoHaggleBot/0.1"}) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except Exception:
            return None

    def _is_toyota_source(self, source: DealerSource) -> bool:
        if source.adapter_key.strip().lower() != "toyota":
            return False
        url = source.inventory_url.strip().lower()
        return "toyota.com/search-inventory" in url or "api.search-inventory.toyota.com/graphql" in url

    def _toyota_log(self, message: str) -> None:
        if self.toyota_debug:
            print(f"[toyota-graphql] {message}")

    def _toyota_post(self, *, client: httpx.Client, endpoint: str, payload: dict) -> httpx.Response | None:
        try:
            response = client.post(endpoint, json=payload)
        except Exception as exc:
            self._toyota_log(f"request exception: {exc}")
            return None

        if response.status_code >= 400:
            snippet = response.text[:240].replace("\n", " ")
            self._toyota_log(f"http {response.status_code}; body={snippet}")
            return None

        return response

    def _toyota_graphql_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": self.toyota_graphql_origin,
            "Referer": self.toyota_graphql_referer,
            "User-Agent": self.toyota_graphql_user_agent,
        }

        api_key = os.getenv("TOYOTA_X_API_KEY", "").strip()
        waf_token = os.getenv("TOYOTA_X_AWS_WAF_TOKEN", "").strip()
        cookie = os.getenv("TOYOTA_GRAPHQL_COOKIE", "").strip()
        if api_key and api_key.lower() != "undefined":
            headers["x-api-key"] = api_key
        if waf_token:
            headers["x-aws-waf-token"] = waf_token
        if cookie:
            headers["Cookie"] = cookie

        raw_extra = os.getenv("TOYOTA_GRAPHQL_EXTRA_HEADERS_JSON", "").strip()
        if raw_extra:
            try:
                parsed = json.loads(raw_extra)
                if isinstance(parsed, dict):
                    for key, value in parsed.items():
                        if key and value is not None:
                            headers[str(key)] = str(value)
            except Exception:
                pass

        return headers

    def _toyota_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds, headers=self._toyota_graphql_headers())

    def _toyota_series_codes_from_targets(self, targets: list[dict]) -> str:
        def add_code(codes: list[str], value: str) -> None:
            if value and value not in codes:
                codes.append(value)

        codes: list[str] = []
        for target in targets:
            make = str(target.get("make") or "").strip().lower()
            if make != "toyota":
                continue

            raw_model = str(target.get("model") or "").strip().lower()
            code = re.sub(r"[^a-z0-9]", "", raw_model)
            if not code:
                continue

            add_code(codes, code)

            # Toyota woodland inventory commonly appears under hybrid series.
            # Query both so model-level requests (e.g., "RAV4" + "Woodland") do not miss it.
            if code == "rav4":
                add_code(codes, "rav4hybrid")
            elif code == "rav4hybrid":
                add_code(codes, "rav4")

        return ",".join(codes)

    def _fetch_toyota_vehicle_summaries(
        self,
        *,
        user_zip: str,
        radius_miles: int,
        targets: list[dict],
    ) -> list[dict]:
        endpoint = self.toyota_graphql_endpoint
        series_codes = self._toyota_series_codes_from_targets(targets)
        if not series_codes:
            return []

        listings: list[dict] = []
        dealer_lookup = self._fetch_toyota_dealer_lookup(user_zip=user_zip)
        leadid = str(uuid4())
        total_pages = 1
        page_no = 1
        page_size = 100

        try:
            with self._toyota_client() as client:
                while page_no <= total_pages and page_no <= 5:
                    payload = {
                        "operationName": "locateVehiclesByZipQuery",
                        "query": TOYOTA_LOCATE_VEHICLES_QUERY,
                        "variables": {
                            "zipCode": user_zip,
                            "distance": int(radius_miles),
                            "pageNo": page_no,
                            "pageSize": page_size,
                            "seriesCodes": series_codes,
                            "leadid": leadid,
                        },
                    }
                    response = self._toyota_post(client=client, endpoint=endpoint, payload=payload)
                    if response is None:
                        return []
                    body = response.json()
                    locate_data = ((body or {}).get("data") or {}).get("locateVehiclesByZip") or {}
                    pagination = locate_data.get("pagination") or {}
                    total_pages = int(pagination.get("totalPages") or total_pages)
                    items = locate_data.get("vehicleSummary") or []

                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        model_obj = item.get("model") or {}
                        price_obj = item.get("price") or {}
                        vin = item.get("vin")
                        stock_num = item.get("stockNum")
                        listing_id = str(vin or stock_num or f"toyota-vehicle-{page_no}-{len(listings)+1}")
                        model_name = str(
                            item.get("marketingSeries")
                            or model_obj.get("marketingName")
                            or model_obj.get("marketingTitle")
                            or ""
                        ).strip()
                        if not model_name:
                            continue

                        msrp = float(price_obj.get("totalMsrp") or price_obj.get("baseMsrp") or 0.0)
                        advertised_price = float(price_obj.get("advertizedPrice") or price_obj.get("nonSpAdvertizedPrice") or 0.0)
                        selling_price = float(price_obj.get("sellingPrice") or 0.0)
                        listed_price = float(selling_price or advertised_price or msrp or 0.0)
                        dealer_discount = max(0.0, (msrp - advertised_price)) if msrp > 0 and advertised_price > 0 else None
                        fees = float(price_obj.get("dph") or 0.0)
                        dio_msrp = float(price_obj.get("dioTotalMsrp") or 0.0)
                        dio_dealer = float(price_obj.get("dioTotalDealerSellingPrice") or 0.0)
                        market_adjustment = max(0.0, dio_dealer - dio_msrp)

                        dealer_code = str(item.get("dealerCd") or "").strip()
                        dealer_info = dealer_lookup.get(dealer_code, {})
                        dealer_name = str(
                            item.get("dealerMarketingName")
                            or dealer_info.get("dealer_name")
                            or ""
                        ).strip()
                        dealer_zip = str(dealer_info.get("dealer_zip") or "").strip()

                        listings.append(
                            {
                                "id": listing_id,
                                "vin": str(vin).strip().upper() if vin else None,
                                "year": self._safe_int(item.get("year")),
                                "make": str(item.get("brand") or "Toyota").strip().title(),
                                "model": model_name,
                                "trim": str(model_obj.get("marketingTitle") or "").strip() or None,
                                "listed_price": listed_price,
                                "msrp": (msrp or None),
                                "advertised_price": (advertised_price or None),
                                "selling_price": (selling_price or None),
                                "dealer_discount": dealer_discount,
                                "fees": fees,
                                "market_adjustment": market_adjustment,
                                "mileage": self._safe_int(item.get("inventoryMileage")),
                                "dealership_id": dealer_code or None,
                                "dealership_name": dealer_name or None,
                                "dealer_zip": dealer_zip or None,
                                "distance_miles": float(item.get("distance") or dealer_info.get("distance_miles") or 0.0),
                            }
                        )
                    page_no += 1
        except Exception:
            return []

        return listings

    def _fetch_toyota_dealer_lookup(self, *, user_zip: str) -> dict[str, dict]:
        endpoint = self.toyota_graphql_endpoint
        payload = {
            "operationName": "dealerInfoByZip",
            "query": TOYOTA_DEALER_INFO_QUERY,
            "variables": {"zipCode": user_zip},
        }

        try:
            with self._toyota_client() as client:
                response = self._toyota_post(client=client, endpoint=endpoint, payload=payload)
                if response is None:
                    return {}
                body = response.json()
        except Exception:
            return {}

        preferred = (((body or {}).get("data") or {}).get("getDealerInfoSystem") or {}).get("preferredDealers") or []
        lookup: dict[str, dict] = {}
        for item in preferred:
            if not isinstance(item, dict):
                continue
            code = str(item.get("localDealerCode") or "").strip()
            if not code:
                continue

            postal = item.get("localPostalAddress") or {}
            postcode = postal.get("postcode") or {}
            proximity_group = item.get("localProximityMeasureGroup") or {}
            proximity = proximity_group.get("proximityMeasure") or {}

            lookup[code] = {
                "dealer_name": str(item.get("localDealerName") or "").strip(),
                "dealer_zip": str(postcode.get("value") or "").strip(),
                "distance_miles": float(proximity.get("value") or 0.0),
            }

        return lookup

    def _fetch_toyota_models(self, *, user_zip: str) -> list[dict]:
        endpoint = self.toyota_graphql_endpoint
        payload = {
            "operationName": "getModels",
            "query": TOYOTA_GET_MODELS_QUERY,
            "variables": {
                "zipCd": user_zip,
                "brand": "T",
                "imageProps": {"wid": "690", "hei": "290"},
                "modelCode": [],
            },
        }

        try:
            with self._toyota_client() as client:
                response = self._toyota_post(client=client, endpoint=endpoint, payload=payload)
                if response is None:
                    return []
                body = response.json()
        except Exception:
            return []

        models = ((body or {}).get("data") or {}).get("models") or []
        listings: list[dict] = []
        for idx, item in enumerate(models, start=1):
            if not isinstance(item, dict):
                continue

            year = self._safe_int(item.get("year"))
            series = str(item.get("series") or "").strip()
            title = str(item.get("title") or "").strip()
            model = series or title
            if not model:
                continue

            top_label = item.get("topLabel") or {}
            trim = str(top_label.get("textField") or "").strip() or None
            listing_id = str(item.get("modelCode") or f"toyota-model-{idx}")
            msrp = float(item.get("msrp") or item.get("asShown") or 0.0)

            listings.append(
                {
                    "id": listing_id,
                    "vin": None,
                    "year": year,
                    "make": "Toyota",
                    "model": model,
                    "trim": trim,
                    "listed_price": msrp,
                    "fees": 0.0,
                    "market_adjustment": 0.0,
                    "mileage": 0,
                }
            )

        return listings

    def _safe_int(self, value: object) -> int:
        try:
            return int(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    def _normalize_model(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())

    def _target_match(self, listing: dict, targets: list[dict]) -> bool:
        make = str(listing.get("make") or "").strip().lower()
        model = str(listing.get("model") or "").strip().lower()
        model_norm = self._normalize_model(model)
        year = int(listing.get("year") or 0)
        trim = str(listing.get("trim") or "").strip().lower()

        for target in targets:
            t_make = str(target.get("make") or "").strip().lower()
            t_model = str(target.get("model") or "").strip().lower()
            t_model_norm = self._normalize_model(t_model)
            t_year = int(target.get("year") or 0)
            t_trim = str(target.get("trim") or "").strip().lower()

            same_model = model_norm == t_model_norm or model_norm.startswith(t_model_norm) or t_model_norm.startswith(model_norm)
            if make != t_make or not same_model:
                continue
            if t_year and year and year != t_year:
                continue
            if t_trim and t_trim not in trim:
                continue
            return True
        return False

    def _distance(self, origin: tuple[float, float] | None, dealer: DealerSource) -> float:
        dealer_coords = _zip_coords(dealer.dealer_zip)
        if origin and dealer_coords:
            return round(_haversine_miles(origin[0], origin[1], dealer_coords[0], dealer_coords[1]), 1)
        return 0.0

    def _within_radius(self, *, origin: tuple[float, float] | None, dealer: DealerSource, radius_miles: int) -> bool:
        if origin is None:
            return True
        dealer_coords = _zip_coords(dealer.dealer_zip)
        if dealer_coords is None:
            return False
        return _haversine_miles(origin[0], origin[1], dealer_coords[0], dealer_coords[1]) <= float(radius_miles)







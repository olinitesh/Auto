from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "api-gateway"


class VehicleTarget(BaseModel):
    make: str
    model: str
    year: int = Field(ge=1990)
    trim: str | None = None


class DealerSiteInput(BaseModel):
    dealer_id: str = Field(min_length=1, max_length=64)
    dealer_name: str = Field(min_length=1, max_length=255)
    dealer_zip: str = Field(min_length=3, max_length=12)
    brand: str = Field(min_length=2, max_length=40)
    site_url: str = Field(min_length=8, max_length=512)
    inventory_url: str = Field(min_length=8, max_length=512)
    adapter_key: str = Field(min_length=2, max_length=40)


class OfferSearchRequest(BaseModel):
    user_zip: str = Field(min_length=3, max_length=12)
    radius_miles: int = Field(default=100, ge=1, le=250)
    budget_otd: float = Field(gt=0)
    targets: list[VehicleTarget] = Field(min_length=1)
    dealer_sites: list[DealerSiteInput] | None = None
    include_in_transit: bool = True
    include_pre_sold: bool = False
    include_hidden: bool = False


class DealerOffer(BaseModel):
    offer_id: str
    dealership_id: str
    dealership_name: str
    distance_miles: float = Field(ge=0)
    vehicle_id: str
    vehicle_label: str
    otd_price: float = Field(gt=0)
    listed_price: float | None = Field(default=None, ge=0)
    msrp: float | None = Field(default=None, ge=0)
    advertised_price: float | None = Field(default=None, ge=0)
    selling_price: float | None = Field(default=None, ge=0)
    dealer_discount: float | None = Field(default=None, ge=0)
    fees: float = Field(ge=0)
    market_adjustment: float = Field(ge=0)
    specs_score: float = Field(ge=0, le=100)
    data_provider: str | None = None
    days_on_market: int | None = Field(default=None, ge=0)
    days_on_market_source: str | None = None
    days_on_market_bucket: str | None = None
    price_drop_7d: float | None = Field(default=None, ge=0)
    price_drop_30d: float | None = Field(default=None, ge=0)
    inventory_status: str | None = None
    is_in_transit: bool = False
    is_pre_sold: bool = False
    is_hidden: bool = False
    listing_url: str | None = None
    dealer_url: str | None = None
    vin: str | None = None


class OfferSearchResponse(BaseModel):
    offers: list[DealerOffer]


class DealerFilterOption(BaseModel):
    id: str
    name: str


class OfferCatalogFilterOptions(BaseModel):
    dealers: list[DealerFilterOption]
    cities: list[str]
    states: list[str]
    makes: list[str]
    models: list[str]


class OfferCatalogResponse(BaseModel):
    offers: list[DealerOffer]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total_pages: int = Field(ge=1)
    filters: OfferCatalogFilterOptions


class OfferTrendKey(BaseModel):
    dealership_id: str = Field(min_length=1, max_length=64)
    vehicle_id: str = Field(min_length=1, max_length=128)


class OfferTrendItem(BaseModel):
    dealership_id: str
    vehicle_id: str
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    days_on_market: int | None = Field(default=None, ge=0)
    days_on_market_bucket: str | None = None
    price_drop_7d: float | None = Field(default=None, ge=0)
    price_drop_30d: float | None = Field(default=None, ge=0)
    snapshot_count: int = Field(default=0, ge=0)


class OfferTrendsBulkRequest(BaseModel):
    offers: list[OfferTrendKey] = Field(min_length=1)


class OfferTrendsBulkResponse(BaseModel):
    trends: list[OfferTrendItem]


class RankedOffer(BaseModel):
    rank: int = Field(ge=1)
    offer: DealerOffer
    score: float
    score_breakdown: dict[str, float]


class OfferRankRequest(BaseModel):
    budget_otd: float = Field(gt=0)
    offers: list[DealerOffer] = Field(min_length=1)


class OfferRankResponse(BaseModel):
    ranked_offers: list[RankedOffer]


class OfferHistoryPoint(BaseModel):
    otd_price: float = Field(gt=0)
    seen_at: str
    data_provider: str | None = None


class OfferHistoryResponse(BaseModel):
    dealership_id: str
    vehicle_id: str
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    days_on_market: int | None = Field(default=None, ge=0)
    points: list[OfferHistoryPoint]


class StartNegotiationRequest(BaseModel):
    user_id: str
    user_name: str
    saved_search_id: str | None = None
    offer_id: str | None = None
    dealership_id: str
    dealership_name: str
    dealership_email: str | None = None
    dealership_phone: str | None = None
    vehicle_id: str
    vehicle_label: str
    offer_rank: int | None = Field(default=None, ge=1)
    days_on_market: int | None = Field(default=None, ge=0)
    price_drop_7d: float | None = Field(default=None, ge=0)
    price_drop_30d: float | None = Field(default=None, ge=0)
    target_otd: float = Field(gt=0)
    dealer_otd: float = Field(gt=0)
    competitor_best_otd: float | None = None
    playbook: Literal["aggressive", "balanced", "conservative"] | None = "balanced"


class NegotiationDecision(BaseModel):
    action: str
    response_text: str
    anchor_otd: float
    rationale: str


class StartNegotiationResponse(BaseModel):
    session_id: str
    status: str
    decision: NegotiationDecision


class EnqueueRoundRequest(BaseModel):
    user_name: str


class EnqueueRoundResponse(BaseModel):
    session_id: str
    job_id: str
    queue: str
    status: str



class AutopilotUpdateRequest(BaseModel):
    enabled: bool
    mode: str | None = Field(default=None, min_length=3, max_length=32)

class NegotiationSessionUpdateRequest(BaseModel):
    playbook: Literal["aggressive", "balanced", "conservative"]

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    queue: str | None = None
    enqueued_at: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    session_id: str | None = None
    error: str | None = None


class NegotiationMessageOut(BaseModel):
    id: str
    direction: str
    channel: str
    sender_identity: str
    body: str
    created_at: str


class NegotiationSessionOut(BaseModel):
    id: str
    user_id: str
    saved_search_id: str | None = None
    offer_id: str | None = None
    dealership_id: str
    dealership_name: str | None = None
    vehicle_id: str
    vehicle_label: str | None = None
    status: str
    best_offer_otd: float | None
    autopilot_enabled: bool = False
    autopilot_mode: str = "manual"
    playbook: str = "balanced"
    playbook_policy: dict | None = None
    last_job_id: str | None = None
    last_job_status: str | None = None
    last_job_at: str | None = None
    created_at: str
    updated_at: str
    messages: list[NegotiationMessageOut]

class SavedSearchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    user_zip: str = Field(min_length=3, max_length=12)
    radius_miles: int = Field(default=100, ge=1, le=250)
    budget_otd: float = Field(gt=0)
    targets: list[VehicleTarget] = Field(min_length=1)
    dealer_sites: list[DealerSiteInput] | None = None
    include_in_transit: bool = True
    include_pre_sold: bool = False
    include_hidden: bool = False


class SavedSearchOut(BaseModel):
    id: str
    name: str
    user_zip: str
    radius_miles: int
    budget_otd: float
    targets: list[VehicleTarget]
    dealer_sites: list[DealerSiteInput] | None = None
    include_in_transit: bool
    include_pre_sold: bool
    include_hidden: bool
    created_at: str
    updated_at: str


class SavedSearchListResponse(BaseModel):
    searches: list[SavedSearchOut]


class SavedSearchDeleteResponse(BaseModel):
    deleted: bool


class SavedSearchAlertOut(BaseModel):
    id: str
    saved_search_id: str
    alert_type: str
    dealership_id: str
    vehicle_id: str
    title: str
    message: str
    metadata: dict | None = None
    acknowledged: bool
    created_at: str
    seen_at: str


class SavedSearchAlertListResponse(BaseModel):
    alerts: list[SavedSearchAlertOut]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=1)


class SavedSearchAlertAckResponse(BaseModel):
    acknowledged: bool


class SavedSearchAlertAckAllRequest(BaseModel):
    alert_ids: list[str] | None = None


class SavedSearchAlertAckAllResponse(BaseModel):
    acknowledged_count: int = Field(ge=0)










class AssistantChatMessage(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=4000)


class AssistantContext(BaseModel):
    budget_otd: float | None = Field(default=None, gt=0)
    offers: list[DealerOffer] = Field(default_factory=list)
    ranked_offers: list[RankedOffer] = Field(default_factory=list)


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[AssistantChatMessage] = Field(default_factory=list)
    context: AssistantContext | None = None
    use_live_web: bool = False


class AssistantChatResponse(BaseModel):
    answer: str
    suggestions: list[str] = Field(default_factory=list)
    cited_offer_ids: list[str] = Field(default_factory=list)
    checked_urls: list[str] = Field(default_factory=list)
    model: str | None = None








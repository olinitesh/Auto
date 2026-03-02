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


class OfferSearchResponse(BaseModel):
    offers: list[DealerOffer]


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
    dealership_id: str
    dealership_name: str
    dealership_email: str | None = None
    dealership_phone: str | None = None
    vehicle_id: str
    vehicle_label: str
    target_otd: float = Field(gt=0)
    dealer_otd: float = Field(gt=0)
    competitor_best_otd: float | None = None


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
    dealership_id: str
    vehicle_id: str
    status: str
    best_offer_otd: float | None
    messages: list[NegotiationMessageOut]

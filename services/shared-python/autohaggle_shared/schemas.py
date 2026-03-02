from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "api-gateway"


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

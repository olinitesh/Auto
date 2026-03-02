from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from autohaggle_shared.communication_client import send_negotiation_email, send_negotiation_sms
from autohaggle_shared.database import get_db, init_db
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.jobs import run_autonomous_round
from autohaggle_shared.negotiation import run_negotiation_strategy
from autohaggle_shared.queueing import get_queue
from autohaggle_shared.repository import add_message, create_session, get_session_with_messages, list_sessions
from autohaggle_shared.schemas import (
    EnqueueRoundRequest,
    EnqueueRoundResponse,
    HealthResponse,
    NegotiationDecision,
    NegotiationMessageOut,
    NegotiationSessionOut,
    StartNegotiationRequest,
    StartNegotiationResponse,
)

app = FastAPI(title="AutoHaggle AI API Gateway", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/negotiations/start", response_model=StartNegotiationResponse)
def start_negotiation(payload: StartNegotiationRequest, db: Session = Depends(get_db)) -> StartNegotiationResponse:
    session = create_session(db, payload)
    strategy = run_negotiation_strategy(
        user_name=payload.user_name,
        target_otd=payload.target_otd,
        dealer_otd=payload.dealer_otd,
        competitor_best_otd=payload.competitor_best_otd,
    )

    message = add_message(
        db=db,
        session_id=session.id,
        direction="outbound",
        channel="email",
        sender_identity=f"AI Assistant representing {payload.user_name}",
        body=strategy["response_text"],
        metadata={
            "action": strategy["action"],
            "anchor_otd": strategy["anchor_otd"],
            "rationale": strategy["rationale"],
        },
    )
    db.commit()
    delivery = {"status": "not_sent", "reason": "missing_dealer_contact"}
    try:
        if payload.dealership_email:
            delivery = send_negotiation_email(payload.dealership_email, strategy["response_text"])
        elif payload.dealership_phone:
            delivery = send_negotiation_sms(payload.dealership_phone, strategy["response_text"])
    except Exception as exc:
        delivery = {"status": "error", "reason": str(exc)}

    publish_session_event(
        session_id=session.id,
        event_type="negotiation.session.started",
        payload={"message_id": message.id, "action": strategy["action"], "delivery": delivery},
    )

    decision = NegotiationDecision(
        action=strategy["action"],
        response_text=strategy["response_text"],
        anchor_otd=strategy["anchor_otd"],
        rationale=strategy["rationale"],
    )
    return StartNegotiationResponse(session_id=session.id, status="active", decision=decision)


@app.get("/negotiations", response_model=list[NegotiationSessionOut])
def get_negotiations(db: Session = Depends(get_db)) -> list[NegotiationSessionOut]:
    sessions = list_sessions(db)
    return [to_session_out(session) for session in sessions]


@app.get("/negotiations/{session_id}", response_model=NegotiationSessionOut)
def get_negotiation(session_id: str, db: Session = Depends(get_db)) -> NegotiationSessionOut:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")
    return to_session_out(session)


@app.post("/negotiations/{session_id}/autonomous-round", response_model=EnqueueRoundResponse)
def enqueue_autonomous_round(
    session_id: str,
    payload: EnqueueRoundRequest,
    db: Session = Depends(get_db),
) -> EnqueueRoundResponse:
    session = get_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")

    queue = get_queue()
    job = queue.enqueue(run_autonomous_round, session_id, payload.user_name)
    publish_session_event(
        session_id=session_id,
        event_type="negotiation.round.queued",
        payload={"job_id": job.id, "queue": queue.name},
    )
    return EnqueueRoundResponse(
        session_id=session_id,
        job_id=job.id,
        queue=queue.name,
        status="queued",
    )


def to_session_out(session) -> NegotiationSessionOut:
    return NegotiationSessionOut(
        id=session.id,
        user_id=session.user_id,
        dealership_id=session.dealership_id,
        vehicle_id=session.vehicle_id,
        status=session.status,
        best_offer_otd=float(session.best_offer_otd) if session.best_offer_otd is not None else None,
        messages=[
            NegotiationMessageOut(
                id=message.id,
                direction=message.direction,
                channel=message.channel,
                sender_identity=message.sender_identity,
                body=message.body,
                created_at=message.created_at.isoformat(),
            )
            for message in session.messages
        ],
    )


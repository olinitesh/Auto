from sqlalchemy import select
from sqlalchemy.orm import Session

from autohaggle_shared.models import Dealer, NegotiationMessage, NegotiationSession
from autohaggle_shared.schemas import StartNegotiationRequest


def get_or_create_dealer(
    db: Session,
    dealership_id: str,
    dealership_name: str,
    dealership_email: str | None = None,
    dealership_phone: str | None = None,
) -> Dealer:
    dealer = db.get(Dealer, dealership_id)
    if dealer:
        if dealership_email and not dealer.email:
            dealer.email = dealership_email
        if dealership_phone and not dealer.phone:
            dealer.phone = dealership_phone
        return dealer

    dealer = Dealer(
        id=dealership_id,
        name=dealership_name,
        email=dealership_email,
        phone=dealership_phone,
    )
    db.add(dealer)
    db.flush()
    return dealer


def create_session(db: Session, payload: StartNegotiationRequest) -> NegotiationSession:
    get_or_create_dealer(
        db,
        payload.dealership_id,
        payload.dealership_name,
        dealership_email=payload.dealership_email,
        dealership_phone=payload.dealership_phone,
    )

    session = NegotiationSession(
        user_id=payload.user_id,
        vehicle_id=payload.vehicle_id,
        dealership_id=payload.dealership_id,
        status="active",
        best_offer_otd=payload.dealer_otd,
    )
    db.add(session)
    db.flush()
    return session


def add_message(
    db: Session,
    session_id: str,
    direction: str,
    channel: str,
    sender_identity: str,
    body: str,
    metadata: dict | None = None,
) -> NegotiationMessage:
    message = NegotiationMessage(
        session_id=session_id,
        direction=direction,
        channel=channel,
        sender_identity=sender_identity,
        body=body,
        metadata=metadata,
    )
    db.add(message)
    db.flush()
    return message


def get_session_with_messages(db: Session, session_id: str) -> NegotiationSession | None:
    session = db.get(NegotiationSession, session_id)
    if not session:
        return None
    _ = list(session.messages)
    return session


def list_sessions(db: Session) -> list[NegotiationSession]:
    rows = db.execute(select(NegotiationSession)).scalars().all()
    for row in rows:
        _ = list(row.messages)
    return rows

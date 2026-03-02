from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from autohaggle_shared.models import Dealer, NegotiationMessage, NegotiationSession, OfferObservation, OfferPriceHistory
from autohaggle_shared.schemas import OfferHistoryPoint, StartNegotiationRequest


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


def upsert_offer_observations(db: Session, offers: list[dict]) -> dict[str, int]:
    now = datetime.utcnow()
    days_by_offer_id: dict[str, int] = {}

    for offer in offers:
        dealership_id = str(offer.get("dealership_id") or "").strip()
        dealership_name = str(offer.get("dealership_name") or "Unknown Dealer").strip() or "Unknown Dealer"
        offer_id = str(offer.get("offer_id") or "").strip()
        vehicle_key = str(offer.get("vehicle_id") or offer_id).strip()

        if not dealership_id or not vehicle_key or not offer_id:
            continue

        get_or_create_dealer(db, dealership_id=dealership_id, dealership_name=dealership_name)

        existing = db.execute(
            select(OfferObservation).where(
                OfferObservation.dealership_id == dealership_id,
                OfferObservation.vehicle_key == vehicle_key,
            )
        ).scalar_one_or_none()

        year = int(offer.get("year")) if offer.get("year") is not None else None
        make = str(offer.get("make") or "").strip() or None
        model = str(offer.get("model") or "").strip() or None
        trim = str(offer.get("trim") or "").strip() or None

        if existing is None:
            existing = OfferObservation(
                dealership_id=dealership_id,
                vehicle_key=vehicle_key,
                vin=(str(offer.get("vin") or offer.get("vehicle_id") or "").upper() or None),
                year=year,
                make=make,
                model=model,
                trim=trim,
                data_provider=offer.get("data_provider"),
                last_otd_price=float(offer.get("otd_price") or 0.0),
                first_seen_at=now,
                last_seen_at=now,
                last_payload=offer,
            )
            db.add(existing)
        else:
            existing.vin = str(offer.get("vin") or offer.get("vehicle_id") or existing.vin or "").upper() or existing.vin
            existing.year = year or existing.year
            existing.make = make or existing.make
            existing.model = model or existing.model
            existing.trim = trim or existing.trim
            existing.data_provider = str(offer.get("data_provider") or existing.data_provider or "") or None
            existing.last_otd_price = float(offer.get("otd_price") or existing.last_otd_price or 0.0)
            existing.last_seen_at = now
            existing.last_payload = offer

        db.add(
            OfferPriceHistory(
                dealership_id=dealership_id,
                vehicle_key=vehicle_key,
                vin=(str(offer.get("vin") or offer.get("vehicle_id") or "").upper() or None),
                otd_price=float(offer.get("otd_price") or 0.0),
                data_provider=str(offer.get("data_provider") or "") or None,
                seen_at=now,
            )
        )

        delta = now.date() - existing.first_seen_at.date()
        days_by_offer_id[offer_id] = max(delta.days, 0)

    db.commit()
    return days_by_offer_id


def get_offer_trend_signals(
    db: Session,
    *,
    dealership_id: str,
    vehicle_key: str,
) -> dict[str, float | None]:
    rows = (
        db.execute(
            select(OfferPriceHistory)
            .where(
                OfferPriceHistory.dealership_id == dealership_id,
                OfferPriceHistory.vehicle_key == vehicle_key,
            )
            .order_by(OfferPriceHistory.seen_at.asc())
            .limit(400)
        )
        .scalars()
        .all()
    )

    if not rows:
        return {"price_drop_7d": None, "price_drop_30d": None}

    latest = float(rows[-1].otd_price)
    now = rows[-1].seen_at

    def _drop(days: int) -> float | None:
        cutoff = now - timedelta(days=days)
        baseline = None
        for row in rows:
            if row.seen_at >= cutoff:
                baseline = float(row.otd_price)
                break
        if baseline is None:
            return None
        return round(max(0.0, baseline - latest), 2)

    return {
        "price_drop_7d": _drop(7),
        "price_drop_30d": _drop(30),
    }


def get_offer_history(
    db: Session,
    *,
    dealership_id: str,
    vehicle_key: str,
    limit: int = 90,
) -> tuple[list[OfferHistoryPoint], str | None, str | None, int | None]:
    history_rows = (
        db.execute(
            select(OfferPriceHistory)
            .where(
                OfferPriceHistory.dealership_id == dealership_id,
                OfferPriceHistory.vehicle_key == vehicle_key,
            )
            .order_by(OfferPriceHistory.seen_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    points = [
        OfferHistoryPoint(
            otd_price=float(row.otd_price),
            seen_at=row.seen_at.isoformat(),
            data_provider=row.data_provider,
        )
        for row in reversed(history_rows)
    ]

    observation = db.execute(
        select(OfferObservation).where(
            OfferObservation.dealership_id == dealership_id,
            OfferObservation.vehicle_key == vehicle_key,
        )
    ).scalar_one_or_none()

    if observation is None:
        return points, None, None, None

    first_seen = observation.first_seen_at.isoformat()
    last_seen = observation.last_seen_at.isoformat()
    days_on_market = max((observation.last_seen_at.date() - observation.first_seen_at.date()).days, 0)

    if not points and observation.last_otd_price is not None:
        points = [
            OfferHistoryPoint(
                otd_price=float(observation.last_otd_price),
                seen_at=observation.last_seen_at.isoformat(),
                data_provider=observation.data_provider,
            )
        ]

    return points, first_seen, last_seen, days_on_market


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
        message_metadata=metadata,
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

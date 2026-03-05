from datetime import datetime, timedelta

from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.orm import Session

from autohaggle_shared.models import Dealer, NegotiationMessage, NegotiationSession, OfferObservation, OfferPriceHistory, SavedSearch, SavedSearchAlert
from autohaggle_shared.schemas import DealerFilterOption, DealerOffer, DealerSiteInput, OfferCatalogFilterOptions, OfferHistoryPoint, OfferTrendItem, SavedSearchAlertOut, SavedSearchCreateRequest, SavedSearchOut, StartNegotiationRequest, VehicleTarget


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


def _dom_bucket(days: int | None) -> str | None:
    if days is None:
        return None
    if days <= 7:
        return "0-7"
    if days <= 14:
        return "8-14"
    if days <= 30:
        return "15-30"
    if days <= 60:
        return "31-60"
    return "61+"


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


def get_offer_trend_summary(
    db: Session,
    *,
    dealership_id: str,
    vehicle_key: str,
) -> OfferTrendItem:
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

    observation = db.execute(
        select(OfferObservation).where(
            OfferObservation.dealership_id == dealership_id,
            OfferObservation.vehicle_key == vehicle_key,
        )
    ).scalar_one_or_none()

    first_seen_at: str | None = None
    last_seen_at: str | None = None
    days_on_market: int | None = None

    if observation is not None:
        first_seen_at = observation.first_seen_at.isoformat()
        last_seen_at = observation.last_seen_at.isoformat()
        days_on_market = max((observation.last_seen_at.date() - observation.first_seen_at.date()).days, 0)

    if not rows:
        return OfferTrendItem(
            dealership_id=dealership_id,
            vehicle_id=vehicle_key,
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            days_on_market=days_on_market,
            days_on_market_bucket=_dom_bucket(days_on_market),
            price_drop_7d=None,
            price_drop_30d=None,
            snapshot_count=0,
        )

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

    return OfferTrendItem(
        dealership_id=dealership_id,
        vehicle_id=vehicle_key,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        days_on_market=days_on_market,
        days_on_market_bucket=_dom_bucket(days_on_market),
        price_drop_7d=_drop(7),
        price_drop_30d=_drop(30),
        snapshot_count=len(rows),
    )


def get_offer_trend_signals(
    db: Session,
    *,
    dealership_id: str,
    vehicle_key: str,
) -> dict[str, float | None]:
    trend = get_offer_trend_summary(db, dealership_id=dealership_id, vehicle_key=vehicle_key)
    return {
        "price_drop_7d": trend.price_drop_7d,
        "price_drop_30d": trend.price_drop_30d,
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
        saved_search_id=payload.saved_search_id,
        offer_id=payload.offer_id,
        vehicle_id=payload.vehicle_id,
        vehicle_label=payload.vehicle_label,
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
    rows = db.execute(select(NegotiationSession).order_by(NegotiationSession.created_at.desc())).scalars().all()
    for row in rows:
        _ = list(row.messages)
    return rows


def update_session_status(
    db: Session,
    *,
    session_id: str,
    status: str,
    last_job_id: str | None = None,
    last_job_status: str | None = None,
) -> bool:
    session = db.get(NegotiationSession, session_id)
    if session is None:
        return False

    session.status = status
    if last_job_id is not None:
        session.last_job_id = last_job_id
    if last_job_status is not None:
        session.last_job_status = last_job_status
    session.last_job_at = datetime.utcnow()
    db.commit()
    return True



def update_session_autopilot(
    db: Session,
    *,
    session_id: str,
    enabled: bool,
    mode: str | None = None,
) -> bool:
    session = db.get(NegotiationSession, session_id)
    if session is None:
        return False

    session.autopilot_enabled = bool(enabled)
    if mode is not None and mode.strip():
        session.autopilot_mode = mode.strip().lower()
    elif enabled and session.autopilot_mode == "manual":
        session.autopilot_mode = "autopilot"
    elif not enabled:
        session.autopilot_mode = "manual"

    session.last_job_at = datetime.utcnow()
    db.commit()
    return True

def update_session_job_metadata(
    db: Session,
    *,
    session_id: str,
    last_job_id: str | None = None,
    last_job_status: str | None = None,
) -> bool:
    session = db.get(NegotiationSession, session_id)
    if session is None:
        return False

    if last_job_id is not None:
        session.last_job_id = last_job_id
    if last_job_status is not None:
        session.last_job_status = last_job_status
    session.last_job_at = datetime.utcnow()
    db.commit()
    return True


def update_session_best_offer(
    db: Session,
    *,
    session_id: str,
    best_offer_otd: float,
) -> bool:
    session = db.get(NegotiationSession, session_id)
    if session is None:
        return False

    session.best_offer_otd = best_offer_otd
    session.last_job_at = datetime.utcnow()
    db.commit()
    return True


def _saved_search_to_schema(row: SavedSearch) -> SavedSearchOut:
    target_payload = row.targets if isinstance(row.targets, list) else []
    site_payload = row.dealer_sites if isinstance(row.dealer_sites, list) else None

    return SavedSearchOut(
        id=row.id,
        name=row.name,
        user_zip=row.user_zip,
        radius_miles=int(row.radius_miles),
        budget_otd=float(row.budget_otd),
        targets=[VehicleTarget(**item) for item in target_payload],
        dealer_sites=[DealerSiteInput(**item) for item in site_payload] if site_payload else None,
        include_in_transit=bool(row.include_in_transit),
        include_pre_sold=bool(row.include_pre_sold),
        include_hidden=bool(row.include_hidden),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def create_saved_search(db: Session, payload: SavedSearchCreateRequest) -> SavedSearchOut:
    row = SavedSearch(
        name=payload.name.strip(),
        user_zip=payload.user_zip.strip(),
        radius_miles=int(payload.radius_miles),
        budget_otd=float(payload.budget_otd),
        targets=[item.model_dump() for item in payload.targets],
        dealer_sites=[item.model_dump() for item in payload.dealer_sites] if payload.dealer_sites else None,
        include_in_transit=bool(payload.include_in_transit),
        include_pre_sold=bool(payload.include_pre_sold),
        include_hidden=bool(payload.include_hidden),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _saved_search_to_schema(row)


def list_saved_searches(db: Session, limit: int = 50) -> list[SavedSearchOut]:
    rows = (
        db.execute(select(SavedSearch).order_by(SavedSearch.updated_at.desc()).limit(max(1, min(limit, 200))))
        .scalars()
        .all()
    )
    return [_saved_search_to_schema(row) for row in rows]


def delete_saved_search(db: Session, search_id: str) -> bool:
    row = db.get(SavedSearch, search_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True



def _saved_search_alert_to_schema(row: SavedSearchAlert) -> SavedSearchAlertOut:
    return SavedSearchAlertOut(
        id=row.id,
        saved_search_id=row.saved_search_id,
        alert_type=row.alert_type,
        dealership_id=row.dealership_id,
        vehicle_id=row.vehicle_id,
        title=row.title,
        message=row.message,
        metadata=row.metadata_json,
        acknowledged=bool(row.acknowledged),
        created_at=row.created_at.isoformat(),
        seen_at=row.seen_at.isoformat(),
    )


def create_or_touch_saved_search_alert(
    db: Session,
    *,
    saved_search_id: str,
    alert_type: str,
    dealership_id: str,
    vehicle_id: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> SavedSearchAlertOut:
    row = (
        db.execute(
            select(SavedSearchAlert).where(
                SavedSearchAlert.saved_search_id == saved_search_id,
                SavedSearchAlert.alert_type == alert_type,
                SavedSearchAlert.dealership_id == dealership_id,
                SavedSearchAlert.vehicle_id == vehicle_id,
                SavedSearchAlert.acknowledged.is_(False),
            )
        )
        .scalars()
        .first()
    )

    now = datetime.utcnow()

    if row is None:
        row = SavedSearchAlert(
            saved_search_id=saved_search_id,
            alert_type=alert_type,
            dealership_id=dealership_id,
            vehicle_id=vehicle_id,
            title=title,
            message=message,
            metadata_json=metadata,
            acknowledged=False,
            created_at=now,
            seen_at=now,
        )
        db.add(row)
    else:
        row.title = title
        row.message = message
        row.metadata_json = metadata
        row.seen_at = now

    db.commit()
    db.refresh(row)
    return _saved_search_alert_to_schema(row)


def list_saved_search_alerts(
    db: Session,
    *,
    include_acknowledged: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SavedSearchAlertOut], int]:
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 100))

    stmt = select(SavedSearchAlert)
    count_stmt = select(func.count()).select_from(SavedSearchAlert)

    if not include_acknowledged:
        stmt = stmt.where(SavedSearchAlert.acknowledged.is_(False))
        count_stmt = count_stmt.where(SavedSearchAlert.acknowledged.is_(False))

    total = int(db.execute(count_stmt).scalar_one())
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = max(1, min(safe_page, total_pages))

    rows = (
        db.execute(
            stmt.order_by(SavedSearchAlert.created_at.desc())
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
        )
        .scalars()
        .all()
    )
    return [_saved_search_alert_to_schema(row) for row in rows], total


def acknowledge_saved_search_alert(db: Session, alert_id: str) -> bool:
    row = db.get(SavedSearchAlert, alert_id)
    if row is None:
        return False

    row.acknowledged = True
    row.seen_at = datetime.utcnow()
    db.commit()
    return True


def acknowledge_saved_search_alerts(db: Session, *, alert_ids: list[str] | None = None) -> int:
    stmt = select(SavedSearchAlert).where(SavedSearchAlert.acknowledged.is_(False))
    if alert_ids:
        stmt = stmt.where(SavedSearchAlert.id.in_(alert_ids))

    rows = db.execute(stmt).scalars().all()
    if not rows:
        return 0

    now = datetime.utcnow()
    for row in rows:
        row.acknowledged = True
        row.seen_at = now

    db.commit()
    return len(rows)

def list_offer_catalog(
    db: Session,
    *,
    dealer_id: str | None = None,
    dealer_name: str | None = None,
    city: str | None = None,
    state: str | None = None,
    make: str | None = None,
    model: str | None = None,
    min_otd: float | None = None,
    max_otd: float | None = None,
    min_dom: int | None = None,
    max_dom: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[DealerOffer], int, OfferCatalogFilterOptions]:
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 200))

    base_stmt = select(OfferObservation, Dealer).join(Dealer, Dealer.id == OfferObservation.dealership_id)

    conditions = []
    if dealer_id:
        conditions.append(OfferObservation.dealership_id == dealer_id.strip())
    if dealer_name:
        conditions.append(Dealer.name.ilike(f"%{dealer_name.strip()}%"))
    if city:
        conditions.append(Dealer.city.ilike(f"%{city.strip()}%"))
    if state:
        conditions.append(Dealer.state.ilike(f"%{state.strip()}%"))
    if make:
        conditions.append(OfferObservation.make.ilike(f"%{make.strip()}%"))
    if model:
        conditions.append(OfferObservation.model.ilike(f"%{model.strip()}%"))
    if min_otd is not None:
        conditions.append(OfferObservation.last_otd_price >= float(min_otd))
    if max_otd is not None:
        conditions.append(OfferObservation.last_otd_price <= float(max_otd))

    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))

    total = int(
        db.execute(
            select(func.count())
            .select_from(OfferObservation)
            .join(Dealer, Dealer.id == OfferObservation.dealership_id)
            .where(and_(*conditions))
            if conditions
            else select(func.count()).select_from(OfferObservation)
        ).scalar_one()
    )

    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = min(safe_page, total_pages)

    rows = (
        db.execute(
            base_stmt.order_by(desc(OfferObservation.last_seen_at))
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
        )
        .all()
    )

    offers: list[DealerOffer] = []
    for observation, dealer in rows:
        payload = observation.last_payload if isinstance(observation.last_payload, dict) else {}

        first_seen = observation.first_seen_at
        last_seen = observation.last_seen_at
        dom_days = max((last_seen.date() - first_seen.date()).days, 0) if first_seen and last_seen else None

        if min_dom is not None and (dom_days is None or dom_days < min_dom):
            continue
        if max_dom is not None and (dom_days is None or dom_days > max_dom):
            continue

        offer_id = str(payload.get("offer_id") or f"{observation.dealership_id}-{observation.vehicle_key}")
        vehicle_label = str(payload.get("vehicle_label") or "").strip()
        if not vehicle_label:
            parts = [
                str(observation.year or "").strip(),
                str(observation.make or "").strip(),
                str(observation.model or "").strip(),
                str(observation.trim or "").strip(),
            ]
            vehicle_label = " ".join([part for part in parts if part]).strip() or observation.vehicle_key

        otd_price = float(observation.last_otd_price or 0.0)
        if otd_price <= 0:
            continue

        offer = DealerOffer(
            offer_id=offer_id,
            dealership_id=observation.dealership_id,
            dealership_name=dealer.name,
            distance_miles=float(payload.get("distance_miles") or dealer.distance_miles or 0.0),
            vehicle_id=observation.vehicle_key,
            vehicle_label=vehicle_label,
            otd_price=otd_price,
            listed_price=float(payload.get("listed_price") or 0.0) if payload.get("listed_price") is not None else None,
            msrp=float(payload.get("msrp") or 0.0) if payload.get("msrp") is not None else None,
            advertised_price=float(payload.get("advertised_price") or payload.get("advertized_price") or 0.0)
            if (payload.get("advertised_price") is not None or payload.get("advertized_price") is not None)
            else None,
            selling_price=float(payload.get("selling_price") or 0.0) if payload.get("selling_price") is not None else None,
            dealer_discount=float(payload.get("dealer_discount") or 0.0) if payload.get("dealer_discount") is not None else None,
            fees=float(payload.get("fees") or 0.0),
            market_adjustment=max(0.0, float(payload.get("market_adjustment") or 0.0)),
            specs_score=max(0.0, min(100.0, float(payload.get("specs_score") or 0.0))),
            data_provider=observation.data_provider,
            days_on_market=dom_days,
            days_on_market_source="tracked",
            days_on_market_bucket=_dom_bucket(dom_days),
            price_drop_7d=float(payload.get("price_drop_7d") or 0.0) if payload.get("price_drop_7d") is not None else None,
            price_drop_30d=float(payload.get("price_drop_30d") or 0.0) if payload.get("price_drop_30d") is not None else None,
            inventory_status=str(payload.get("inventory_status") or "") or None,
            is_in_transit=bool(payload.get("is_in_transit") or False),
            is_pre_sold=bool(payload.get("is_pre_sold") or False),
            is_hidden=bool(payload.get("is_hidden") or False),
            listing_url=str(payload.get("listing_url") or "") or None,
            dealer_url=str(payload.get("dealer_url") or "") or None,
            vin=(str(payload.get("vin") or observation.vin or "").upper() or None),
        )
        offers.append(offer)

    dealer_rows = db.execute(select(Dealer.id, Dealer.name).order_by(asc(Dealer.name)).limit(500)).all()
    city_rows = db.execute(select(Dealer.city).where(Dealer.city.is_not(None)).distinct().order_by(asc(Dealer.city)).limit(500)).all()
    state_rows = db.execute(select(Dealer.state).where(Dealer.state.is_not(None)).distinct().order_by(asc(Dealer.state)).limit(100)).all()
    make_rows = db.execute(select(OfferObservation.make).where(OfferObservation.make.is_not(None)).distinct().order_by(asc(OfferObservation.make)).limit(200)).all()
    model_rows = db.execute(select(OfferObservation.model).where(OfferObservation.model.is_not(None)).distinct().order_by(asc(OfferObservation.model)).limit(400)).all()

    filters = OfferCatalogFilterOptions(
        dealers=[DealerFilterOption(id=row[0], name=row[1]) for row in dealer_rows if row[0] and row[1]],
        cities=[str(row[0]) for row in city_rows if row[0]],
        states=[str(row[0]) for row in state_rows if row[0]],
        makes=[str(row[0]) for row in make_rows if row[0]],
        models=[str(row[0]) for row in model_rows if row[0]],
    )

    return offers, total, filters







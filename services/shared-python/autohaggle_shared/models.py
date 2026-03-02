from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from autohaggle_shared.database import Base


class Dealer(Base):
    __tablename__ = "dealership"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sessions: Mapped[list["NegotiationSession"]] = relationship(back_populates="dealer")


class VehicleListing(Base):
    __tablename__ = "vehicle_listing"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dealership_id: Mapped[str] = mapped_column(ForeignKey("dealership.id"), nullable=False)
    vin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    year: Mapped[int] = mapped_column(nullable=False)
    make: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    trim: Mapped[str | None] = mapped_column(String(120), nullable=True)
    msrp: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    listed_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    specs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class OfferObservation(Base):
    __tablename__ = "offer_observation"
    __table_args__ = (UniqueConstraint("dealership_id", "vehicle_key", name="uq_offer_observation_dealer_vehicle"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dealership_id: Mapped[str] = mapped_column(ForeignKey("dealership.id"), nullable=False)
    vehicle_key: Mapped[str] = mapped_column(String(80), nullable=False)
    vin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    year: Mapped[int | None] = mapped_column(nullable=True)
    make: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trim: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_otd_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class OfferPriceHistory(Base):
    __tablename__ = "offer_price_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dealership_id: Mapped[str] = mapped_column(ForeignKey("dealership.id"), nullable=False)
    vehicle_key: Mapped[str] = mapped_column(String(80), nullable=False)
    vin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    otd_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    data_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class NegotiationSession(Base):
    __tablename__ = "negotiation_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(36), nullable=False)
    dealership_id: Mapped[str] = mapped_column(ForeignKey("dealership.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="new")
    strategy_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    best_offer_otd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    dealer: Mapped[Dealer] = relationship(back_populates="sessions")
    messages: Mapped[list["NegotiationMessage"]] = relationship(back_populates="session")


class NegotiationMessage(Base):
    __tablename__ = "negotiation_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("negotiation_session.id"), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_identity: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    session: Mapped[NegotiationSession] = relationship(back_populates="messages")

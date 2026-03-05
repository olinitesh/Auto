from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from autohaggle_shared.config import settings

engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from autohaggle_shared import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Backward-compatible safety patch for older local databases that predate
    # negotiation linkage fields. This keeps startup resilient when migrations
    # were not run yet.
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE negotiation_session "
                "ADD COLUMN IF NOT EXISTS saved_search_id VARCHAR(36), "
                "ADD COLUMN IF NOT EXISTS offer_id VARCHAR(128), "
                "ADD COLUMN IF NOT EXISTS vehicle_label VARCHAR(255), "
                "ADD COLUMN IF NOT EXISTS last_job_id VARCHAR(64), "
                "ADD COLUMN IF NOT EXISTS last_job_status VARCHAR(32), "
                "ADD COLUMN IF NOT EXISTS last_job_at TIMESTAMPTZ, "
                "ADD COLUMN IF NOT EXISTS autopilot_enabled BOOLEAN NOT NULL DEFAULT FALSE, "
                "ADD COLUMN IF NOT EXISTS autopilot_mode VARCHAR(32) NOT NULL DEFAULT 'manual'"
            )
        )
        conn.execute(text("ALTER TABLE negotiation_session ALTER COLUMN vehicle_id TYPE VARCHAR(128)"))

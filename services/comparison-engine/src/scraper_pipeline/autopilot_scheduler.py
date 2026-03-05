from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import select

from autohaggle_shared.database import SessionLocal
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.jobs import run_autonomous_round
from autohaggle_shared.models import NegotiationSession
from autohaggle_shared.queueing import get_queue
from autohaggle_shared.repository import update_session_status


ACTIVE_JOB_STATUSES = {"queued", "scheduled", "deferred", "started", "running"}


def queue_autopilot_rounds(
    *,
    limit: int = 25,
    cooldown_seconds: int = 120,
    user_name: str = "Buyer",
) -> dict[str, int]:
    safe_limit = max(1, min(limit, 500))
    safe_cooldown = max(0, cooldown_seconds)

    db = SessionLocal()
    try:
        queue = get_queue()
        now = datetime.now(timezone.utc)

        candidates = (
            db.execute(
                select(NegotiationSession)
                .where(
                    NegotiationSession.autopilot_enabled.is_(True),
                    NegotiationSession.status == "responded",
                )
                .order_by(NegotiationSession.updated_at.asc())
                .limit(safe_limit)
            )
            .scalars()
            .all()
        )

        queued = 0
        skipped_inflight = 0
        skipped_cooldown = 0

        for session in candidates:
            last_job_status = (session.last_job_status or "").strip().lower()
            if last_job_status in ACTIVE_JOB_STATUSES:
                skipped_inflight += 1
                continue

            if safe_cooldown > 0 and session.last_job_at is not None:
                last_job_at = session.last_job_at
                if last_job_at.tzinfo is None:
                    last_job_at = last_job_at.replace(tzinfo=timezone.utc)
                elapsed = (now - last_job_at).total_seconds()
                if elapsed < safe_cooldown:
                    skipped_cooldown += 1
                    continue

            job = queue.enqueue(run_autonomous_round, session.id, user_name)
            update_session_status(
                db,
                session_id=session.id,
                status="queued",
                last_job_id=job.id,
                last_job_status="queued",
            )
            publish_session_event(
                session_id=session.id,
                event_type="negotiation.round.queued",
                payload={"job_id": job.id, "queue": queue.name, "source": "autopilot-scheduler"},
            )
            queued += 1

        return {
            "candidates": len(candidates),
            "queued": queued,
            "skipped_inflight": skipped_inflight,
            "skipped_cooldown": skipped_cooldown,
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue AI negotiation rounds for autopilot-enabled sessions")
    parser.add_argument("--limit", type=int, default=25, help="Max sessions to scan each run")
    parser.add_argument(
        "--cooldown-seconds",
        type=int,
        default=120,
        help="Minimum seconds between re-queue attempts for the same session",
    )
    parser.add_argument("--user-name", type=str, default="Buyer", help="User name used in AI outbound messages")
    args = parser.parse_args()

    result = queue_autopilot_rounds(
        limit=args.limit,
        cooldown_seconds=args.cooldown_seconds,
        user_name=args.user_name.strip() or "Buyer",
    )
    print(
        "autopilot_scheduler: "
        f"candidates={result['candidates']}, "
        f"queued={result['queued']}, "
        f"skipped_inflight={result['skipped_inflight']}, "
        f"skipped_cooldown={result['skipped_cooldown']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

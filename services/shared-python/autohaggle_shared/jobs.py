from sqlalchemy.orm import Session

from autohaggle_shared.communication_client import send_negotiation_email, send_negotiation_sms
from autohaggle_shared.database import SessionLocal
from autohaggle_shared.events import publish_session_event
from autohaggle_shared.negotiation import run_negotiation_strategy
from autohaggle_shared.repository import add_message, get_session_with_messages, update_session_status


def run_autonomous_round(session_id: str, user_name: str) -> dict:
    db: Session = SessionLocal()
    try:
        update_session_status(db, session_id=session_id, status="running", last_job_status="started")
        session = get_session_with_messages(db, session_id)
        if not session:
            return {"ok": False, "error": "session_not_found", "session_id": session_id}

        current_offer = float(session.best_offer_otd or 0)
        target_otd = current_offer - 750 if current_offer > 0 else 30000
        competitor_otd = current_offer - 350 if current_offer > 0 else None

        decision = run_negotiation_strategy(
            user_name=user_name,
            target_otd=target_otd,
            dealer_otd=current_offer or target_otd + 900,
            competitor_best_otd=competitor_otd,
        )

        msg = add_message(
            db=db,
            session_id=session_id,
            direction="outbound",
            channel="email",
            sender_identity=f"AI Assistant representing {user_name}",
            body=decision["response_text"],
            metadata={
                "action": decision["action"],
                "anchor_otd": decision["anchor_otd"],
                "rationale": decision["rationale"],
                "mode": "autonomous_round",
            },
        )
        db.commit()
        delivery = {"status": "not_sent", "reason": "missing_dealer_contact"}
        try:
            if session.dealer and session.dealer.email:
                delivery = send_negotiation_email(session.dealer.email, decision["response_text"])
            elif session.dealer and session.dealer.phone:
                delivery = send_negotiation_sms(session.dealer.phone, decision["response_text"])
        except Exception as exc:
            delivery = {"status": "error", "reason": str(exc)}

        next_status = "responded" if decision["action"] == "counter_offer" else "closed"
        update_session_status(db, session_id=session_id, status=next_status, last_job_status="finished")

        publish_session_event(
            session_id=session_id,
            event_type="negotiation.message.sent",
            payload={
                "message_id": msg.id,
                "direction": msg.direction,
                "channel": msg.channel,
                "body": msg.body,
                "delivery": delivery,
                "session_status": next_status,
            },
        )

        return {"ok": True, "session_id": session_id, "action": decision["action"], "status": next_status}
    except Exception:
        update_session_status(db, session_id=session_id, status="failed", last_job_status="failed")
        raise
    finally:
        db.close()

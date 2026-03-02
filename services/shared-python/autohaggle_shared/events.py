import json
from datetime import datetime, timezone

from redis import Redis

from autohaggle_shared.config import settings


def _event_channel(session_id: str) -> str:
    return f"warroom:session:{session_id}"


def publish_session_event(session_id: str, event_type: str, payload: dict) -> None:
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    message = {
        "event_type": event_type,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    client.publish(_event_channel(session_id), json.dumps(message))

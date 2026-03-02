import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from autohaggle_shared.config import settings

app = FastAPI(title="AutoHaggle War Room Realtime", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "war-room-realtime"}


@app.websocket("/ws/negotiations/{session_id}")
async def websocket_session_feed(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = f"warroom:session:{session_id}"
    await pubsub.subscribe(channel)

    try:
        await websocket.send_json(
            {
                "event_type": "warroom.connected",
                "session_id": session_id,
                "payload": {"channel": channel},
            }
        )
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                try:
                    payload = json.loads(message["data"])
                except json.JSONDecodeError:
                    payload = {"event_type": "warroom.raw", "payload": {"data": message["data"]}}
                await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis.close()


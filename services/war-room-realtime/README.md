# War Room Realtime
FastAPI websocket service that streams per-session negotiation events from Redis Pub/Sub.

## Endpoints
- GET `/health`
- WS `/ws/negotiations/{session_id}`

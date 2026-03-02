# API Endpoints

## API Gateway (`:8000`)
- GET `/health`
- POST `/negotiations/start`
- POST `/negotiations/{session_id}/autonomous-round`
- GET `/negotiations`
- GET `/negotiations/{session_id}`

## Communication Service (`:8010`)
- GET `/health`
- POST `/send/email`
- POST `/send/sms`
- POST `/send/voice`
- POST `/webhooks/twilio/sms`
- POST `/webhooks/sendgrid/email`

## War Room Realtime (`:8020`)
- GET `/health`
- WS `/ws/negotiations/{session_id}`

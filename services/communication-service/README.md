# Communication Service
FastAPI service that sends outbound messages through SendGrid and Twilio and receives inbound webhooks.

## Endpoints
- GET `/health`
- POST `/send/email`
- POST `/send/sms`
- POST `/send/voice`
- POST `/webhooks/twilio/sms`
- POST `/webhooks/sendgrid/email`

If credentials are missing, send endpoints return `dry_run` instead of sending externally.

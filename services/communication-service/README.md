# Communication Service
FastAPI service that sends outbound messages through SendGrid and Twilio and receives inbound webhooks.

## Endpoints
- GET `/health`
- POST `/send/email`
- POST `/send/sms`
- POST `/send/voice`
- POST `/webhooks/twilio/sms`
- POST `/webhooks/sendgrid/email`
- POST `/webhooks/gmail/poll` (manual Gmail inbox sync for local/dev)

If credentials are missing, send endpoints return `dry_run` instead of sending externally.

Gmail inbound sync (local/dev):
```bash
curl -X POST http://localhost:8010/webhooks/gmail/poll \
  -H "Content-Type: application/json" \
  --data-raw '{"mailbox":"INBOX","max_messages":10,"unseen_only":true}'
```
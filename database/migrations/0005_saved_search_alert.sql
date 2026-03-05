CREATE TABLE IF NOT EXISTS saved_search_alert (
  id VARCHAR(36) PRIMARY KEY,
  saved_search_id VARCHAR(36) NOT NULL REFERENCES saved_search(id),
  alert_type VARCHAR(40) NOT NULL,
  dealership_id VARCHAR(64) NOT NULL,
  vehicle_id VARCHAR(128) NOT NULL,
  title VARCHAR(220) NOT NULL,
  message TEXT NOT NULL,
  metadata JSONB,
  acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now(),
  seen_at TIMESTAMPTZ DEFAULT now()
);

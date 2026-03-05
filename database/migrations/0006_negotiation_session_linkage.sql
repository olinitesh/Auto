ALTER TABLE negotiation_session
  ADD COLUMN IF NOT EXISTS saved_search_id VARCHAR(36) REFERENCES saved_search(id),
  ADD COLUMN IF NOT EXISTS offer_id VARCHAR(128),
  ADD COLUMN IF NOT EXISTS vehicle_label VARCHAR(255);

ALTER TABLE negotiation_session
  ALTER COLUMN vehicle_id TYPE VARCHAR(128);

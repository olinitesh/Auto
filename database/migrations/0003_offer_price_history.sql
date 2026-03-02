CREATE TABLE IF NOT EXISTS offer_price_history (
  id VARCHAR(36) PRIMARY KEY,
  dealership_id VARCHAR(36) NOT NULL REFERENCES dealership(id),
  vehicle_key VARCHAR(80) NOT NULL,
  vin VARCHAR(32),
  otd_price NUMERIC(12,2) NOT NULL,
  data_provider VARCHAR(80),
  seen_at TIMESTAMPTZ DEFAULT now()
);

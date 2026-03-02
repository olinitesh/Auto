CREATE TABLE IF NOT EXISTS offer_observation (
  id VARCHAR(36) PRIMARY KEY,
  dealership_id VARCHAR(36) NOT NULL REFERENCES dealership(id),
  vehicle_key VARCHAR(80) NOT NULL,
  vin VARCHAR(32),
  year INT,
  make VARCHAR(120),
  model VARCHAR(120),
  trim VARCHAR(120),
  data_provider VARCHAR(80),
  last_otd_price NUMERIC(12,2),
  first_seen_at TIMESTAMPTZ DEFAULT now(),
  last_seen_at TIMESTAMPTZ DEFAULT now(),
  last_payload JSONB,
  CONSTRAINT uq_offer_observation_dealer_vehicle UNIQUE (dealership_id, vehicle_key)
);
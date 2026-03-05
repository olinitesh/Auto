CREATE TABLE IF NOT EXISTS dealership (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  city VARCHAR(120),
  state VARCHAR(80),
  distance_miles NUMERIC(6,2),
  phone VARCHAR(40),
  email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS vehicle_listing (
  id VARCHAR(36) PRIMARY KEY,
  dealership_id VARCHAR(36) NOT NULL REFERENCES dealership(id),
  vin VARCHAR(32),
  year INT NOT NULL,
  make VARCHAR(120) NOT NULL,
  model VARCHAR(120) NOT NULL,
  trim VARCHAR(120),
  msrp NUMERIC(12,2),
  listed_price NUMERIC(12,2),
  specs JSONB,
  source VARCHAR(80),
  captured_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS negotiation_session (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  saved_search_id VARCHAR(36),
  offer_id VARCHAR(128),
  vehicle_id VARCHAR(128) NOT NULL,
  vehicle_label VARCHAR(255),
  dealership_id VARCHAR(36) NOT NULL REFERENCES dealership(id),
  status VARCHAR(40) DEFAULT 'new',
  strategy_state JSONB,
  best_offer_otd NUMERIC(12,2),
  autopilot_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  autopilot_mode VARCHAR(32) NOT NULL DEFAULT 'manual',
  last_job_id VARCHAR(64),
  last_job_status VARCHAR(32),
  last_job_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS negotiation_message (
  id VARCHAR(36) PRIMARY KEY,
  session_id VARCHAR(36) NOT NULL REFERENCES negotiation_session(id),
  direction VARCHAR(20) NOT NULL,
  channel VARCHAR(20) NOT NULL,
  sender_identity VARCHAR(255) NOT NULL,
  body TEXT NOT NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

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
CREATE TABLE IF NOT EXISTS offer_price_history (
  id VARCHAR(36) PRIMARY KEY,
  dealership_id VARCHAR(36) NOT NULL REFERENCES dealership(id),
  vehicle_key VARCHAR(80) NOT NULL,
  vin VARCHAR(32),
  otd_price NUMERIC(12,2) NOT NULL,
  data_provider VARCHAR(80),
  seen_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS saved_search (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  user_zip VARCHAR(12) NOT NULL,
  radius_miles INT NOT NULL DEFAULT 100,
  budget_otd NUMERIC(12,2) NOT NULL,
  targets JSONB NOT NULL,
  dealer_sites JSONB,
  include_in_transit BOOLEAN NOT NULL DEFAULT TRUE,
  include_pre_sold BOOLEAN NOT NULL DEFAULT FALSE,
  include_hidden BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

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


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
  vehicle_id VARCHAR(36) NOT NULL,
  dealership_id VARCHAR(36) NOT NULL REFERENCES dealership(id),
  status VARCHAR(40) DEFAULT 'new',
  strategy_state JSONB,
  best_offer_otd NUMERIC(12,2),
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

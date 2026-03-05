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

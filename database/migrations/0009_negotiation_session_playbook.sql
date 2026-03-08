ALTER TABLE negotiation_session
  ADD COLUMN IF NOT EXISTS playbook VARCHAR(32) NOT NULL DEFAULT 'balanced';

ALTER TABLE negotiation_session
  ADD COLUMN IF NOT EXISTS playbook_policy JSONB;

UPDATE negotiation_session
SET playbook = 'balanced'
WHERE playbook IS NULL OR trim(playbook) = '';

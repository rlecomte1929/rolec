ALTER TABLE relocation_cases
  ADD COLUMN IF NOT EXISTS payment_status TEXT NOT NULL DEFAULT 'unpaid'
    CHECK (payment_status IN ('unpaid', 'roadmap_paid', 'essentials_paid')),
  ADD COLUMN IF NOT EXISTS access_tier TEXT NOT NULL DEFAULT 'free'
    CHECK (access_tier IN ('free', 'roadmap', 'essentials')),
  ADD COLUMN IF NOT EXISTS stripe_payment_intent_id TEXT,
  ADD COLUMN IF NOT EXISTS stripe_session_id TEXT,
  ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS paid_amount_cents INTEGER,
  ADD COLUMN IF NOT EXISTS paid_currency TEXT DEFAULT 'eur';

CREATE INDEX IF NOT EXISTS idx_relocation_cases_access_tier
  ON relocation_cases(access_tier);
CREATE INDEX IF NOT EXISTS idx_relocation_cases_stripe_session
  ON relocation_cases(stripe_session_id)
  WHERE stripe_session_id IS NOT NULL;

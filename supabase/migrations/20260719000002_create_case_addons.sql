CREATE TABLE IF NOT EXISTS case_addons (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES relocation_cases(id) ON DELETE CASCADE,
  addon_type TEXT NOT NULL CHECK (addon_type IN (
    'vendor_movers','vendor_immigration','vendor_tax','vendor_schools','vendor_pets'
  )),
  payment_status TEXT NOT NULL DEFAULT 'unpaid'
    CHECK (payment_status IN ('unpaid','paid')),
  stripe_session_id TEXT,
  stripe_payment_intent_id TEXT,
  paid_at TIMESTAMPTZ,
  paid_amount_cents INTEGER,
  paid_currency TEXT DEFAULT 'eur',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_case_addons_case_id ON case_addons(case_id);
CREATE INDEX IF NOT EXISTS idx_case_addons_stripe_session
  ON case_addons(stripe_session_id)
  WHERE stripe_session_id IS NOT NULL;

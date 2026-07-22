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

-- RLS (mandatory hard gate — payment records are sensitive PII). case_addons is written
-- only by the Stripe fulfilment path (service_role) and read server-side; the browser
-- never queries it directly (the unlock decision is always the server's). So: service_role
-- writes/reads, admin read for ops, anon fully revoked. Employees reach their own add-on
-- state through the backend, not PostgREST.
ALTER TABLE public.case_addons ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS case_addons_service_all ON public.case_addons;
CREATE POLICY case_addons_service_all ON public.case_addons
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS case_addons_admin_read ON public.case_addons;
CREATE POLICY case_addons_admin_read ON public.case_addons
  FOR SELECT TO authenticated USING (public.is_admin());

REVOKE ALL ON public.case_addons FROM anon;

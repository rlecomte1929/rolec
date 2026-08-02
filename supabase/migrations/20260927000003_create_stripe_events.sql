-- Stripe webhook idempotency ledger (portable-webhook spec §6). The fulfilment brain
-- inserts event_id here BEFORE doing anything; a duplicate (Stripe retries, or the
-- portable dual-path — Render + Audos relay — delivering the same event twice) hits the
-- PK and is short-circuited as already-processed. This single guard is what makes the
-- checkout→webhook→unlock flow safe to retry.
--
-- Purely internal (never client-read): service_role writes/reads, admin read for ops,
-- anon fully revoked — the mandatory RLS hard gate for a new public table. The anon key
-- ships in the frontend bundle and PostgREST exposes public.*, so a table without RLS is
-- world-readable (this is what caused SEC-002). No frontend role ever reads this table.
--
-- case_id is TEXT (not uuid) on purpose: it is copied verbatim from untrusted Stripe
-- metadata, and the brain must never 500 on a malformed/absent value — a bad string must
-- land as data, not raise on insert.

CREATE TABLE IF NOT EXISTS public.stripe_events (
  event_id     TEXT PRIMARY KEY,                 -- Stripe event.id (evt_…) — the idempotency key
  type         TEXT NOT NULL,                    -- e.g. checkout.session.completed
  received_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  case_id      TEXT,                             -- resolved case, when present in metadata (nullable)
  status       TEXT NOT NULL DEFAULT 'applied'   -- applied | duplicate | ignored
);
CREATE INDEX IF NOT EXISTS idx_stripe_events_received_at ON public.stripe_events (received_at);

ALTER TABLE public.stripe_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS stripe_events_service_all ON public.stripe_events;
CREATE POLICY stripe_events_service_all ON public.stripe_events
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS stripe_events_admin_read ON public.stripe_events;
CREATE POLICY stripe_events_admin_read ON public.stripe_events
  FOR SELECT TO authenticated USING (public.is_admin());

REVOKE ALL ON public.stripe_events FROM anon;

-- IMM-15 · rfq_requests.immigration_context — link a vendor RFQ to its case's immigration context (AIQ-121)
--
-- When HR clicks "Request Quote" from an immigration vendor, the RFQ should carry
-- the case's structured immigration context (visa type, corridor, employee
-- nationality, dependents, risk flags) so the vendor network sees the situation
-- ReloPass already knows — without HR re-typing it.
--
-- This adds ONE nullable JSONB column to the existing public.rfq_requests table.
-- It is deliberately backward-compatible:
--   * Nullable, no default — existing (non-immigration) RFQs are untouched and
--     keep NULL, so no backfill and no behaviour change for the AIQ-40-C flow.
--   * ADD COLUMN IF NOT EXISTS — safe to replay against an environment where the
--     column already exists (the rfq_requests table itself was created out of
--     band and is not owned by an in-repo migration).
--
-- Shape written by backend/app/routers/hr_rfq.py (all keys optional):
--   {
--     "visa_type": "blue_card",
--     "corridor_from": "FR",
--     "corridor_to": "DE",
--     "employee_nationality": "Indian",
--     "has_dependents": true,
--     "risk_flags": ["bfa_pre_approval"]
--   }

ALTER TABLE public.rfq_requests
  ADD COLUMN IF NOT EXISTS immigration_context jsonb;

COMMENT ON COLUMN public.rfq_requests.immigration_context IS
  'IMM-15 (AIQ-121): structured immigration case context captured when the RFQ '
  'originates from the immigration panel. NULL for non-immigration RFQs.';

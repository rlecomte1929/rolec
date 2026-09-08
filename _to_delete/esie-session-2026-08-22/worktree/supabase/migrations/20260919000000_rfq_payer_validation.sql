-- AIQ-1524 — separate the employee's PROPOSAL from HR's VALIDATION on an RFQ.
--
-- MODEL: employee-led RFQ, HR = payer.
--   The EMPLOYEE runs the RFQ and PROPOSES the offer they want  -> rfqs.preferred_quote_id
--   HR is the PAYER and VALIDATES the offer the company will pay -> rfqs.validated_quote_id
--   HR may validate a DIFFERENT offer than the employee proposed, and the reason is recorded
--   and surfaced back to the employee              -> rfqs.validation_reason
--
-- Why new columns rather than a new quote status: public.quotes has
--   CHECK (status = ANY (ARRAY['proposed','accepted','rejected']))
-- so "the employee prefers this one" cannot be expressed as a status without widening that
-- constraint — and it isn't a status of the QUOTE anyway, it's a fact about the REQUEST.
-- One preferred quote and one validated quote per RFQ; both live naturally on rfqs.
--
-- Safety: all columns are NULLABLE with no default, added to an EXISTING table.
-- public.rfqs has 0 rows in prod (the whole RFQ subsystem is currently unwritten), so this
-- cannot rewrite or lock anything meaningful. RLS on rfqs is unchanged — no new table, no new
-- policy needed.
--
-- FKs are ON DELETE SET NULL: deleting a quote must not delete the request it belonged to.

BEGIN;

ALTER TABLE public.rfqs
  ADD COLUMN IF NOT EXISTS preferred_quote_id   uuid REFERENCES public.quotes(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS preferred_by_user_id text,
  ADD COLUMN IF NOT EXISTS preferred_at         timestamptz,
  ADD COLUMN IF NOT EXISTS validated_quote_id   uuid REFERENCES public.quotes(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS validated_by_user_id text,
  ADD COLUMN IF NOT EXISTS validated_at         timestamptz,
  ADD COLUMN IF NOT EXISTS validation_reason    text;

COMMENT ON COLUMN public.rfqs.preferred_quote_id IS
  'AIQ-1524: the offer the EMPLOYEE proposed. A proposal, not an approval — it commits no spend.';
COMMENT ON COLUMN public.rfqs.validated_quote_id IS
  'AIQ-1524: the offer HR (the payer) validated. This is the spend approval. HR-only.';
COMMENT ON COLUMN public.rfqs.validation_reason IS
  'AIQ-1524: why HR validated this offer — required when HR overrides the employee''s proposal, and surfaced back to the employee.';

COMMIT;

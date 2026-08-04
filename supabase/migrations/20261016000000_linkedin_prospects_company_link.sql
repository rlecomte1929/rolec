-- P0.2 — link a CONVERTED LinkedIn Outreach contact to the company/tenant it became.
--
-- Additive column on an existing, RLS-protected table (public.linkedin_prospects),
-- mirroring prospect_candidates.onboarded_company_id. This is NOT a new table, so the
-- CLAUDE.md new-table RLS gate does not apply: the table's existing "Admin full access"
-- policy and the anon REVOKE already cover the new column. Idempotent.
--
-- Stored as a plain TEXT reference (not an enforced FK) to match onboarded_company_id —
-- companies live in the legacy db layer, so we intentionally avoid a cross-boundary FK.

ALTER TABLE public.linkedin_prospects
  ADD COLUMN IF NOT EXISTS company_id TEXT;

COMMENT ON COLUMN public.linkedin_prospects.company_id IS
  'Company/tenant this outreach contact converted into, set by the convert endpoint. NULL until converted.';

CREATE INDEX IF NOT EXISTS idx_linkedin_prospects_company_id
  ON public.linkedin_prospects (company_id);

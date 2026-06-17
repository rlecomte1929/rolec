-- AIQ-1136 / NAV-HR-2-FU: internal notes on a relocation case (HR annotates a
-- case in context). New public table -> full 3-part RLS gate per CLAUDE.md.
-- APPLIED to prod (nsvefcvpvwwwhuqyuqmp) 2026-06-17 via execute_sql + recorded
-- schema_migrations(version=20260701000000). Idempotent.
CREATE TABLE IF NOT EXISTS public.case_notes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id         TEXT NOT NULL,
  company_id      TEXT,
  author_user_id  TEXT NOT NULL,
  author_name     TEXT,
  body            TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_case_notes_case_id    ON public.case_notes(case_id);
CREATE INDEX IF NOT EXISTS idx_case_notes_company_id ON public.case_notes(company_id);

ALTER TABLE public.case_notes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_all_case_notes" ON public.case_notes;
CREATE POLICY "service_role_all_case_notes" ON public.case_notes
  FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "hr_read_own_company_case_notes" ON public.case_notes;
CREATE POLICY "hr_read_own_company_case_notes" ON public.case_notes
  FOR SELECT USING (
    auth.role() = 'authenticated'
    AND company_id = (SELECT raw_user_meta_data->>'company_id' FROM auth.users WHERE id = auth.uid())
  );

REVOKE ALL ON public.case_notes FROM anon;

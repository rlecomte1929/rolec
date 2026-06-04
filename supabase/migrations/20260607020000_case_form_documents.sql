-- ============================================================
-- [P1-05c / AIQ-678] case_form_documents — per-form supporting uploads
-- Date: 2026-06-04
--
-- Stores supporting documents the employee uploads against a specific
-- dossier form (e.g. passport scan for the work-permit form). Files live in
-- the existing private `case-documents` Storage bucket; this table holds the
-- metadata + storage path, scoped to (case_id, case_form_id).
--
-- NOTE: this is a NEW form-scoped table, deliberately separate from the
-- existing `public.case_documents` table — that one's case_id FKs to
-- `mobility_cases` (a different case system), whereas dossier `case_forms`
-- FK to `public.cases`. Reusing it would be an FK mismatch.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.case_form_documents (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_form_id  uuid        NOT NULL REFERENCES public.case_forms(id) ON DELETE CASCADE,
  case_id       uuid        NOT NULL REFERENCES public.cases(id)      ON DELETE CASCADE,
  file_name     text        NOT NULL,
  storage_path  text        NOT NULL,                 -- path within the `case-documents` bucket
  content_type  text,
  size_bytes    bigint,
  uploaded_by   uuid        REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.case_form_documents IS
  'Supporting documents uploaded by the employee against a specific dossier case_form. Files stored in the private case-documents Storage bucket; this row holds metadata + storage_path. Scoped to (case_id, case_form_id). [P1-05c]';

CREATE INDEX IF NOT EXISTS idx_case_form_documents_form_id
  ON public.case_form_documents(case_form_id);
CREATE INDEX IF NOT EXISTS idx_case_form_documents_case_id
  ON public.case_form_documents(case_id);

-- updated_at trigger (same moddatetime pattern as the other dossier tables)
DROP TRIGGER IF EXISTS handle_updated_at ON public.case_form_documents;
CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.case_form_documents
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

-- ── RLS ───────────────────────────────────────────────────────
-- Mirrors the case_form_comments policy: employee who owns the case, plus
-- HR/Admin in the case's company. Joins case_forms → cases → profiles.
ALTER TABLE public.case_form_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "case_form_documents_access"
  ON public.case_form_documents
  FOR ALL
  USING (
    EXISTS (
      SELECT 1
      FROM public.case_forms cf
      JOIN public.cases c ON c.id = cf.case_id
      JOIN public.profiles p ON p.id = auth.uid()
      WHERE cf.id = case_form_documents.case_form_id
        AND (
          p.role = 'ADMIN'
          OR c.employee_id = auth.uid()
          OR (p.role = 'HR' AND p.company_id = c.company_id)
        )
    )
  );

-- Defense-in-depth: the anon key ships in the frontend bundle. PostgREST must
-- never expose this PII-bearing table to unauthenticated callers.
REVOKE ALL ON public.case_form_documents FROM anon;

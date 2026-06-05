-- =============================================================================
-- BL-OCR.1 / AIQ-747 · immigration_documents table + immigration-documents bucket
--
-- Foundation for OCR/AI on uploaded immigration documents (passports, permits,
-- supporting evidence). One row per uploaded file, linked to a relocation case
-- and (optionally) to its immigration_cases permit-tracking record.
--
-- Conventions follow the existing immigration schema
-- (20260518120000_immigration_core_tables.sql), NOT the uuid/FK/org_id template
-- in the task brief, which assumes a model this repo does not use:
--   * TEXT ids (gen_random_uuid()::text), TEXT user refs (auth.uid()::text)
--   * NO FK to public.immigration_cases — that table lives only in the remote
--     baseline (no local CREATE), so a hard FK would break fresh replay.
--     immigration_case_id is a nullable soft link instead.
--   * RLS scoped via a public.case_assignments join (employee_user_id / hr_user_id),
--     there is no org_id JWT claim in this codebase.
--
-- Bucket is hardened in-line per SEC-006 (private, 20 MiB cap, mime allowlist)
-- so it does not need a follow-up hardening migration.
--
-- Idempotent / replay-safe: IF NOT EXISTS, DROP POLICY IF EXISTS,
-- ON CONFLICT DO NOTHING. References only case_assignments + storage.* (baseline).
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.immigration_documents (
  id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,

  -- Relocation case — RLS scoping anchor (matches sibling immigration tables).
  case_id             TEXT NOT NULL,
  -- Soft link to public.immigration_cases.id (no FK: that table is baseline-only
  -- and a hard FK would break fresh replay). Nullable until a permit case exists.
  immigration_case_id TEXT,

  uploaded_by         TEXT NOT NULL,            -- auth.uid()::text

  file_name           TEXT NOT NULL,
  storage_path        TEXT NOT NULL,            -- path inside the 'immigration-documents' bucket: <case_id>/<file>
  mime_type           TEXT NOT NULL CHECK (mime_type IN (
                        'application/pdf','image/png','image/jpeg','image/webp','image/tiff')),
  file_size_bytes     BIGINT NOT NULL,

  -- OCR pipeline state
  ocr_status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (ocr_status IN ('pending','processing','done','failed')),
  ocr_result          JSONB,                    -- structured extraction output

  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_immigration_documents_case_id
  ON public.immigration_documents(case_id);

-- OCR worker polls for unprocessed documents.
CREATE INDEX IF NOT EXISTS idx_immigration_documents_ocr_status
  ON public.immigration_documents(ocr_status);

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE public.immigration_documents ENABLE ROW LEVEL SECURITY;

-- CLAUDE.md hard gate: defence-in-depth anon revoke.
REVOKE ALL ON public.immigration_documents FROM anon;

-- Employee or HR assigned to the relocation case can read its documents.
DROP POLICY IF EXISTS immigration_documents_select ON public.immigration_documents;
CREATE POLICY immigration_documents_select
  ON public.immigration_documents FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = immigration_documents.case_id
        AND (ca.employee_user_id = auth.uid()::text OR ca.hr_user_id = auth.uid()::text)
    )
  );

-- Employee or HR assigned to the case can upload; uploader stamp must be self.
DROP POLICY IF EXISTS immigration_documents_insert ON public.immigration_documents;
CREATE POLICY immigration_documents_insert
  ON public.immigration_documents FOR INSERT TO authenticated
  WITH CHECK (
    uploaded_by = auth.uid()::text
    AND EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = immigration_documents.case_id
        AND (ca.employee_user_id = auth.uid()::text OR ca.hr_user_id = auth.uid()::text)
    )
  );

-- Backend OCR pipeline / admin operations.
DROP POLICY IF EXISTS immigration_documents_service_role ON public.immigration_documents;
CREATE POLICY immigration_documents_service_role
  ON public.immigration_documents FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- Storage bucket (private; hardened per SEC-006)
-- ---------------------------------------------------------------------------

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'immigration-documents',
  'immigration-documents',
  false,
  20971520,  -- 20 MiB
  array['application/pdf','image/png','image/jpeg','image/webp','image/tiff']
)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS mirrors the table: case-scoped read/write via case_assignments.
-- Path convention: <case_id>/<filename>  -> (storage.foldername(name))[1] = case_id.
-- service_role bypasses RLS, so no explicit service_role policy is required.

DROP POLICY IF EXISTS immigration_documents_objects_read ON storage.objects;
CREATE POLICY immigration_documents_objects_read ON storage.objects
  FOR SELECT TO authenticated
  USING (
    bucket_id = 'immigration-documents'
    AND (storage.foldername(name))[1] IN (
      SELECT ca.case_id FROM public.case_assignments ca
      WHERE ca.employee_user_id = auth.uid()::text OR ca.hr_user_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS immigration_documents_objects_write ON storage.objects;
CREATE POLICY immigration_documents_objects_write ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'immigration-documents'
    AND (storage.foldername(name))[1] IN (
      SELECT ca.case_id FROM public.case_assignments ca
      WHERE ca.employee_user_id = auth.uid()::text OR ca.hr_user_id = auth.uid()::text
    )
  );

COMMIT;

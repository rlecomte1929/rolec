-- AIQ-1148: document_ocr_results — general document OCR output (Mistral Document AI)
-- ─────────────────────────────────────────────────────────────────────────────
-- Stores the result of POST /api/ocr/process: the extracted markdown + page count
-- for any uploaded document (expense receipts, leases, visa docs, ...). raw_markdown
-- is document content (PHI) — RLS tenant-scoped, anon revoked. Mirrors the
-- support_tickets RLS template (20260524000005).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.document_ocr_results (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Tenant + actor (resolved from the caller's JWT on insert)
  company_id       TEXT,                       -- caller's company; null for unlinked employees
  uploaded_by      TEXT,                       -- Supabase auth user id of the uploader

  -- Document + OCR output
  document_type    TEXT        NOT NULL DEFAULT 'generic',
  source_filename  TEXT,
  mime_type        TEXT,
  pages_count      INT         NOT NULL DEFAULT 0,
  raw_markdown     TEXT,                        -- OCR text (PHI) — protected by RLS below
  extracted_fields JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_document_ocr_results_company_id  ON public.document_ocr_results(company_id);
CREATE INDEX IF NOT EXISTS idx_document_ocr_results_created_at  ON public.document_ocr_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_ocr_results_uploaded_by ON public.document_ocr_results(uploaded_by);

-- ── Row Level Security (hard gate: ENABLE + policy + REVOKE anon) ─────────────
ALTER TABLE public.document_ocr_results ENABLE ROW LEVEL SECURITY;

-- Service role full access (backend writes go through this connection).
-- NB: CREATE POLICY has no IF NOT EXISTS — use DROP IF EXISTS + CREATE for idempotency.
DROP POLICY IF EXISTS "service_role_all_document_ocr_results" ON public.document_ocr_results;
CREATE POLICY "service_role_all_document_ocr_results"
  ON public.document_ocr_results FOR ALL
  USING (auth.role() = 'service_role');

-- HR can read OCR results for their own company.
DROP POLICY IF EXISTS "hr_read_own_company_ocr_results" ON public.document_ocr_results;
CREATE POLICY "hr_read_own_company_ocr_results"
  ON public.document_ocr_results FOR SELECT
  USING (
    auth.role() = 'authenticated'
    AND company_id = (
      SELECT raw_user_meta_data->>'company_id'
      FROM auth.users WHERE id = auth.uid()
    )
  );

-- Uploaders can read their own OCR results.
DROP POLICY IF EXISTS "user_read_own_ocr_results" ON public.document_ocr_results;
CREATE POLICY "user_read_own_ocr_results"
  ON public.document_ocr_results FOR SELECT
  USING (
    auth.role() = 'authenticated'
    AND uploaded_by = auth.uid()::text
  );

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
REVOKE ALL ON public.document_ocr_results FROM anon;

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE  public.document_ocr_results              IS 'AIQ-1148: general document OCR output (Mistral Document AI). raw_markdown is PHI — RLS tenant-scoped, anon revoked.';
COMMENT ON COLUMN public.document_ocr_results.raw_markdown IS 'OCR-extracted markdown (PHI). Never logged; readable only via RLS-scoped SELECT or the service role.';
COMMENT ON COLUMN public.document_ocr_results.extracted_fields IS 'Per-document_type structured fields — populated by the follow-up LLM extraction step (AIQ-1149+); {} until then.';

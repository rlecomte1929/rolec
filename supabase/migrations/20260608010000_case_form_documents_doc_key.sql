-- ============================================================
-- [P1-05 checklist] case_form_documents.doc_key
-- Date: 2026-06-04
--
-- Lets an uploaded supporting document be tagged to a specific required-document
-- checklist item (the checklist is derived from the form template's fields that
-- carry requires_original=true). When an upload's doc_key matches a checklist
-- item, that item shows as provided on the Dossier form card.
--
-- Nullable column add on an existing RLS-enabled table (case_form_documents,
-- created in 20260607020000) — no new RLS gate required.
-- ============================================================

ALTER TABLE public.case_form_documents
  ADD COLUMN IF NOT EXISTS doc_key text;

COMMENT ON COLUMN public.case_form_documents.doc_key IS
  'Optional: the required-document checklist item this upload satisfies (matches a form field id whose requires_original=true). NULL = a general/other attachment. [P1-05 checklist]';

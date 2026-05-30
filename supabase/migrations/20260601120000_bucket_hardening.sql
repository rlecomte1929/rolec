-- SEC-006 / AIQ-478 — storage bucket hardening.
--
-- Live audit (project nsvefcvpvwwwhuqyuqmp, 2026-05-30) found every bucket
-- already private (public=false) but two of three with NULL file_size_limit
-- and NULL allowed_mime_types — i.e. accepting files of any size and any type.
-- This migration locks the configuration in source control:
--
--   * public            = false           (defence-in-depth; assert, don't assume)
--   * file_size_limit   = 20 MiB          (20 * 1024 * 1024 = 20971520 bytes)
--   * allowed_mime_types = SEC-006 allowlist, per bucket purpose
--
-- These are storage.buckets config rows (not a new public.* table), so the
-- migration RLS hard-gate does not apply. RLS on storage.objects already
-- exists (see 20260301022000_hr_policies_bucket.sql).
--
-- Idempotent: pure UPDATEs keyed by bucket id; re-running is a no-op.

begin;

-- hr-policies: HR uploads policy PDFs / DOCX.
update storage.buckets
set
  public = false,
  file_size_limit = 20971520,
  allowed_mime_types = array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
where id = 'hr-policies';

-- form-templates: admin-uploaded blank form PDFs.
update storage.buckets
set
  public = false,
  file_size_limit = 20971520,
  allowed_mime_types = array['application/pdf']
where id = 'form-templates';

-- case-documents: employee/HR case documents and scanned images. Keep the
-- image scan types (webp/tiff) the bucket already permitted so existing
-- upload flows do not start 415-ing; just drop the size ceiling to 20 MiB
-- and re-assert private.
update storage.buckets
set
  public = false,
  file_size_limit = 20971520,
  allowed_mime_types = array[
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/tiff'
  ]
where id = 'case-documents';

commit;

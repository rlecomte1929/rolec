-- Create the `company-logos` storage bucket used by HR company-logo uploads.
--
-- Bug: POST /api/hr/company-profile/logo uploaded to the `company-logos` bucket via
-- the Supabase service role, but that bucket was never provisioned — the
-- 20260228000000_company_profile_and_logos migration only added the
-- companies.logo_url column, not the bucket. So every HR logo upload got
-- `{"statusCode":400,"error":"Bucket not found"}` from Storage and the backend
-- returned 502 "Logo upload failed" (surfaced to HR as "Upload failed.").
--
-- Unlike the other buckets (SEC-006 / 20260601120000_bucket_hardening keeps
-- hr-policies / form-templates / case-documents PRIVATE + signed URLs), company
-- logos are non-PII public branding and the backend serves them via PUBLIC object
-- URLs (SUPABASE_URL/storage/v1/object/public/company-logos/...), so this bucket
-- is intentionally `public = true`.
--
-- Writes are backend-only (service role bypasses RLS); the frontend never writes
-- to storage directly, so no storage.objects policies are required (public read
-- works without a SELECT policy on a public bucket).
--
-- Config mirrors the validation in backend/main.py::upload_company_logo
-- (2 MiB cap, PNG/JPEG/SVG) as a defence-in-depth backstop, per SEC-006's
-- "lock bucket config in source control" convention. Idempotent.

begin;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'company-logos',
  'company-logos',
  true,
  2097152, -- 2 * 1024 * 1024
  array['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

commit;

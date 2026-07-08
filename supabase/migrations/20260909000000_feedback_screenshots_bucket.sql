-- [AIQ-1480] feedback-screenshots: PRIVATE storage bucket for annotated feedback screenshots.
--
-- A feedback screenshot captures the reporter's page and can contain PII, so the bucket
-- is PRIVATE (public=false): the backend uploads via the service role, and the admin
-- console reads through short-lived signed URLs minted by the authed admin API. The
-- frontend never touches Storage directly, so no storage.objects policies are required
-- (a private bucket denies anon/authenticated access by default; the service role bypasses
-- RLS for backend uploads + signing). Mirrors the SEC-006 private-bucket convention
-- (20260601120000_bucket_hardening) and the company-logos bucket provisioning pattern.
--
-- + public.feedback.screenshot_url: the object path within this bucket. The existing
-- base64 feedback.screenshot_data column is KEPT as a fallback for when a Storage upload
-- fails (so a screenshot is never lost). Idempotent.

begin;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'feedback-screenshots',
  'feedback-screenshots',
  false,
  5242880, -- 5 * 1024 * 1024
  array['image/png', 'image/jpeg']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

alter table public.feedback add column if not exists screenshot_url text;

commit;

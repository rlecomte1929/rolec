-- ============================================================
-- [P1-2B] Storage bucket for form template PDFs + RLS policies
-- Date: 2026-05-21
--
-- Purpose: lets admins upload the original government form PDF alongside
-- the form_templates row created via the admin editor. Bucket is private
-- (not publicly listable); reads go through Supabase Storage signed URLs.
--
-- Path convention: <template_code>/<version>.pdf
--   e.g. 'UTL-2011/1.0.0.pdf'
-- This lets us version PDFs alongside the templates and avoid filename
-- collisions when a template is bumped to a new version.
--
-- Security model:
--   - Any authenticated user can read PDFs (reference material, not PII)
--   - Only ADMIN role users can write (mirrors the hr-policies pattern)
-- ============================================================

BEGIN;

-- 1. Bucket (private — reads via signed URLs, not public links)
INSERT INTO storage.buckets (id, name, public)
VALUES ('form-templates', 'form-templates', false)
ON CONFLICT (id) DO NOTHING;

-- 2. Read policy: any authenticated user can SELECT objects in this bucket.
--    Form templates are reference material — every employee and HR user
--    needs to be able to view the official PDF when filling out their forms.
DROP POLICY IF EXISTS form_templates_pdfs_read ON storage.objects;
CREATE POLICY form_templates_pdfs_read ON storage.objects
  FOR SELECT TO authenticated
  USING (bucket_id = 'form-templates');

-- 3. Write policy: only ADMIN role users can INSERT/UPDATE/DELETE objects.
--    Role check via public.profiles (the same join used by hr-policies).
DROP POLICY IF EXISTS form_templates_pdfs_admin_write ON storage.objects;
CREATE POLICY form_templates_pdfs_admin_write ON storage.objects
  FOR ALL TO authenticated
  USING (
    bucket_id = 'form-templates'
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.role = 'admin'
    )
  )
  WITH CHECK (
    bucket_id = 'form-templates'
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.role = 'admin'
    )
  );

COMMIT;

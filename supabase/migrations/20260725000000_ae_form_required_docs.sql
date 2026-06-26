-- [AIQ-1257c] AE corridor required documents.
--
-- The AE form_templates seed (20260610090000_seed_ae_form_templates.sql) shipped
-- every field with `requires_original: false`, so the dossier never derived a
-- required-document checklist for the UAE corridor. This migration flips the
-- document-backed fields to `requires_original: true` and adds an optional
-- `doc_format` acceptance-guidance string (consumed by AIQ-1257a/b) on each.
--
-- Convention (no new table — AIQ-1257a decision): per-form required documents
-- flow as form_templates.fields[].requires_original === true, derived server-side
-- in backend/app/routers/cases_read.py into required_documents:[{key,label,format}].
--
-- Idempotent: each UPDATE rebuilds the fields array in place, merging the target
-- keys onto the matching elements with `||`. Re-running sets the same values, and
-- order is preserved via WITH ORDINALITY. Untargeted fields are left untouched.

-- AE-ENTRY-PERMIT — Employment entry permit (passport bio page)
UPDATE public.form_templates t
SET fields = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'passport_number'
        THEN elem || '{"requires_original": true, "doc_format": "Passport bio page — original + copy"}'::jsonb
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(t.fields) WITH ORDINALITY AS e(elem, ord)
)
WHERE t.code = 'AE-ENTRY-PERMIT' AND t.version = '1.0.0';

-- AE-WORK-PERMIT — Labour card / work permit (passport + attested contract)
UPDATE public.form_templates t
SET fields = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'passport_number'
        THEN elem || '{"requires_original": true, "doc_format": "Passport bio page — original + copy"}'::jsonb
      WHEN elem->>'id' = 'employer_name'
        THEN elem || '{"requires_original": true, "doc_format": "Attested employment contract — original"}'::jsonb
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(t.fields) WITH ORDINALITY AS e(elem, ord)
)
WHERE t.code = 'AE-WORK-PERMIT' AND t.version = '1.0.0';

-- AE-EMIRATES-ID — Emirates ID (proof of UAE address)
UPDATE public.form_templates t
SET fields = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'local_address'
        THEN elem || '{"requires_original": true, "doc_format": "Tenancy contract (Ejari) — certified copy"}'::jsonb
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(t.fields) WITH ORDINALITY AS e(elem, ord)
)
WHERE t.code = 'AE-EMIRATES-ID' AND t.version = '1.0.0';

-- AE-EJARI — Tenancy registration (title deed / landlord contract)
UPDATE public.form_templates t
SET fields = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'local_address'
        THEN elem || '{"requires_original": true, "doc_format": "Title deed or landlord contract — original"}'::jsonb
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(t.fields) WITH ORDINALITY AS e(elem, ord)
)
WHERE t.code = 'AE-EJARI' AND t.version = '1.0.0';

-- AE-BANK — UAE bank account (proof of address)
UPDATE public.form_templates t
SET fields = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'local_address'
        THEN elem || '{"requires_original": true, "doc_format": "Proof of address — original + copy"}'::jsonb
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(t.fields) WITH ORDINALITY AS e(elem, ord)
)
WHERE t.code = 'AE-BANK' AND t.version = '1.0.0';

-- AE-FAM-SPOUSE — Family sponsorship, spouse (marriage certificate)
UPDATE public.form_templates t
SET fields = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'spouse_full_name'
        THEN elem || '{"requires_original": true, "doc_format": "Marriage certificate — attested + translated"}'::jsonb
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(t.fields) WITH ORDINALITY AS e(elem, ord)
)
WHERE t.code = 'AE-FAM-SPOUSE' AND t.version = '1.0.0';

-- AE-FAM-CHILD — Family sponsorship, child (birth certificate)
UPDATE public.form_templates t
SET fields = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'child_full_name'
        THEN elem || '{"requires_original": true, "doc_format": "Birth certificate — attested + translated"}'::jsonb
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(t.fields) WITH ORDINALITY AS e(elem, ord)
)
WHERE t.code = 'AE-FAM-CHILD' AND t.version = '1.0.0';

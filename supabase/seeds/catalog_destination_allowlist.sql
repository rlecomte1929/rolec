-- Seed: catalog_destination_allowlist
-- ----------------------------------------------------------------------
-- Bootstraps the destinations HR can pick from on /hr/vendor-curation
-- so the AI scraper can be fired without an admin manually clicking
-- "approve" for each city.
--
-- Schema (see supabase/migrations/20260427140000_catalog_scrape_safety.sql):
--   city       text  not null
--   country    text  not null
--   approved_by uuid                                -- nullable
--   approved_at timestamptz not null default now()
--   notes      text
--   primary key (city, country)
--
-- Idempotent via ON CONFLICT on the composite PK.
-- approved_by is left NULL to mark these rows as system-seeded.
--
-- RLS note: this table allows INSERT only for ADMIN profiles. Run this
-- seed via the Supabase SQL editor or a service_role connection — the
-- audit trigger trg_audit_cda will fire either way.
-- ----------------------------------------------------------------------

INSERT INTO public.catalog_destination_allowlist (city, country, approved_by, notes)
VALUES
  ('London',    'United Kingdom', NULL, 'system seed'),
  ('Singapore', 'Singapore',      NULL, 'system seed'),
  ('Paris',     'France',         NULL, 'system seed'),
  ('Frankfurt', 'Germany',        NULL, 'system seed'),
  ('Amsterdam', 'Netherlands',    NULL, 'system seed')
ON CONFLICT (city, country) DO NOTHING;

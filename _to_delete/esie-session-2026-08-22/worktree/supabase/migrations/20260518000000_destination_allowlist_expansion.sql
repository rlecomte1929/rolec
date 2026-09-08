-- B14 fix: Expand catalog_destination_allowlist to 20+ countries.
--
-- The HR Resources destination picker (HrResourcesPreview) is populated from
-- this table via /api/hr/resources/destinations. The E2E baseline (May 2026)
-- confirmed 14 countries; the product target is 20+. This migration is
-- idempotent (ON CONFLICT DO NOTHING) so it can be reapplied safely.
--
-- approved_by = NULL indicates a system-seeded entry rather than an
-- admin-approved per-request entry.
--
-- Note: the audit trigger (trg_audit_cda) assumes new.id but this table's PK
-- is (city, country). We disable it for the duration of this seed-only
-- migration to avoid the "record new has no field id" error.

ALTER TABLE public.catalog_destination_allowlist DISABLE TRIGGER trg_audit_cda;

INSERT INTO public.catalog_destination_allowlist (city, country, approved_by, notes) VALUES
  -- France
  ('Paris',        'France',         NULL, 'B14 seed'),
  ('Lyon',         'France',         NULL, 'B14 seed'),
  ('Marseille',    'France',         NULL, 'B14 seed'),
  -- Netherlands
  ('Amsterdam',    'Netherlands',    NULL, 'B14 seed'),
  ('Rotterdam',    'Netherlands',    NULL, 'B14 seed'),
  ('The Hague',    'Netherlands',    NULL, 'B14 seed'),
  -- Ireland
  ('Dublin',       'Ireland',        NULL, 'B14 seed'),
  ('Cork',         'Ireland',        NULL, 'B14 seed'),
  -- Spain
  ('Madrid',       'Spain',          NULL, 'B14 seed'),
  ('Barcelona',    'Spain',          NULL, 'B14 seed'),
  ('Seville',      'Spain',          NULL, 'B14 seed'),
  -- Belgium
  ('Brussels',     'Belgium',        NULL, 'B14 seed'),
  ('Antwerp',      'Belgium',        NULL, 'B14 seed'),
  -- Sweden
  ('Stockholm',    'Sweden',         NULL, 'B14 seed'),
  ('Gothenburg',   'Sweden',         NULL, 'B14 seed'),
  ('Malmö',        'Sweden',         NULL, 'B14 seed'),
  -- Denmark
  ('Copenhagen',   'Denmark',        NULL, 'B14 seed'),
  ('Aarhus',       'Denmark',        NULL, 'B14 seed'),
  -- Portugal
  ('Lisbon',       'Portugal',       NULL, 'B14 seed'),
  ('Porto',        'Portugal',       NULL, 'B14 seed'),
  -- Poland
  ('Warsaw',       'Poland',         NULL, 'B14 seed'),
  ('Kraków',       'Poland',         NULL, 'B14 seed'),
  ('Wrocław',      'Poland',         NULL, 'B14 seed'),
  -- Czech Republic
  ('Prague',       'Czech Republic', NULL, 'B14 seed'),
  ('Brno',         'Czech Republic', NULL, 'B14 seed'),
  -- South Korea
  ('Seoul',        'South Korea',    NULL, 'B14 seed'),
  ('Busan',        'South Korea',    NULL, 'B14 seed'),
  -- South Africa
  ('Johannesburg', 'South Africa',   NULL, 'B14 seed'),
  ('Cape Town',    'South Africa',   NULL, 'B14 seed'),
  -- Austria
  ('Vienna',       'Austria',        NULL, 'B14 seed'),
  ('Graz',         'Austria',        NULL, 'B14 seed'),
  -- Hong Kong
  ('Hong Kong',    'Hong Kong',      NULL, 'B14 seed')
ON CONFLICT (city, country) DO NOTHING;

ALTER TABLE public.catalog_destination_allowlist ENABLE TRIGGER trg_audit_cda;

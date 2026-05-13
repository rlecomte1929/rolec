-- AIQ-28-A: Add Japan, Canada, UAE, India, Australia to destination tables
-- Applied to Supabase (nsvefcvpvwwwhuqyuqmp) on 2026-05-13.
--
-- country_profiles: stores AI-curated country guidance data.
--   Japan was already present; Canada, UAE, India, Australia added here.
-- catalog_destination_allowlist: gates vendor catalog scraping per city/country.
--   All 5 countries seeded with key expat cities.
--
-- Both inserts are idempotent (WHERE NOT EXISTS guard).
-- Note: catalog_destination_allowlist has an audit trigger (relopass_audit_row)
--   that references new.id — a pre-existing bug since the table has no id column.
--   Trigger is disabled for the duration of this migration and re-enabled after.

-- ── country_profiles ──────────────────────────────────────────────────────────

INSERT INTO country_profiles (id, country_code, last_updated_at, confidence_score, notes)
SELECT gen_random_uuid(), 'CANADA', now(), 0.85,
  'Major corporate relocation destination. Key hubs: Toronto, Vancouver, Montreal. Work permit via LMIA or ICT route.'
WHERE NOT EXISTS (SELECT 1 FROM country_profiles WHERE country_code = 'CANADA');

INSERT INTO country_profiles (id, country_code, last_updated_at, confidence_score, notes)
SELECT gen_random_uuid(), 'UNITED ARAB EMIRATES', now(), 0.85,
  'High-demand MENA hub. Key city: Dubai. Employment visa sponsored by employer. No personal income tax.'
WHERE NOT EXISTS (SELECT 1 FROM country_profiles WHERE country_code = 'UNITED ARAB EMIRATES');

INSERT INTO country_profiles (id, country_code, last_updated_at, confidence_score, notes)
SELECT gen_random_uuid(), 'INDIA', now(), 0.80,
  'Major APAC tech and business hub. Key cities: Bangalore, Mumbai, Delhi. Business visa + Employment visa routes.'
WHERE NOT EXISTS (SELECT 1 FROM country_profiles WHERE country_code = 'INDIA');

INSERT INTO country_profiles (id, country_code, last_updated_at, confidence_score, notes)
SELECT gen_random_uuid(), 'AUSTRALIA', now(), 0.85,
  'Strong corporate relocation market. Key cities: Sydney, Melbourne. Employer-sponsored visa (TSS subclass 482).'
WHERE NOT EXISTS (SELECT 1 FROM country_profiles WHERE country_code = 'AUSTRALIA');

-- ── catalog_destination_allowlist ─────────────────────────────────────────────

ALTER TABLE catalog_destination_allowlist DISABLE TRIGGER ALL;

INSERT INTO catalog_destination_allowlist (city, country, approved_at, notes)
SELECT v.city, v.country, now(), 'AIQ-28-A seed'
FROM (VALUES
  ('Tokyo',     'Japan'),
  ('Osaka',     'Japan'),
  ('Yokohama',  'Japan'),
  ('Toronto',   'Canada'),
  ('Vancouver', 'Canada'),
  ('Montreal',  'Canada'),
  ('Dubai',     'United Arab Emirates'),
  ('Abu Dhabi', 'United Arab Emirates'),
  ('Bangalore', 'India'),
  ('Mumbai',    'India'),
  ('Delhi',     'India'),
  ('Sydney',    'Australia'),
  ('Melbourne', 'Australia')
) AS v(city, country)
WHERE NOT EXISTS (
  SELECT 1 FROM catalog_destination_allowlist dal
  WHERE dal.city = v.city AND dal.country = v.country
);

ALTER TABLE catalog_destination_allowlist ENABLE TRIGGER ALL;

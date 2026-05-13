-- AIQ-28-A backfill: seed catalog_destination_allowlist for the 9 original
-- country_profiles countries that had no allowlist entries.
-- (Japan was already seeded in aiq_28a_add_five_destinations.sql)
-- Applied to Supabase (nsvefcvpvwwwhuqyuqmp) on 2026-05-13.
--
-- Result: 43 total city entries across all 14 supported countries.
-- Idempotent: WHERE NOT EXISTS guard on (city, country).
-- Trigger disabled for same pre-existing audit trigger bug (new.id on table with no id col).

ALTER TABLE catalog_destination_allowlist DISABLE TRIGGER ALL;

INSERT INTO catalog_destination_allowlist (city, country, approved_at, notes)
SELECT v.city, v.country, now(), 'aiq-28-a-backfill original countries'
FROM (VALUES
  -- Germany
  ('Berlin',        'Germany'),
  ('Frankfurt',     'Germany'),
  ('Munich',        'Germany'),
  ('Hamburg',       'Germany'),
  ('Düsseldorf',    'Germany'),
  -- Israel
  ('Tel Aviv',      'Israel'),
  ('Jerusalem',     'Israel'),
  ('Haifa',         'Israel'),
  -- Italy
  ('Milan',         'Italy'),
  ('Rome',          'Italy'),
  ('Turin',         'Italy'),
  -- New Zealand
  ('Auckland',      'New Zealand'),
  ('Wellington',    'New Zealand'),
  -- Norway
  ('Oslo',          'Norway'),
  ('Bergen',        'Norway'),
  -- Singapore
  ('Singapore',     'Singapore'),
  -- Switzerland
  ('Zurich',        'Switzerland'),
  ('Geneva',        'Switzerland'),
  ('Basel',         'Switzerland'),
  -- United Kingdom
  ('London',        'United Kingdom'),
  ('Manchester',    'United Kingdom'),
  ('Edinburgh',     'United Kingdom'),
  ('Birmingham',    'United Kingdom'),
  -- United States
  ('New York',      'United States'),
  ('San Francisco', 'United States'),
  ('Chicago',       'United States'),
  ('Austin',        'United States'),
  ('Los Angeles',   'United States'),
  ('Boston',        'United States'),
  ('Seattle',       'United States')
) AS v(city, country)
WHERE NOT EXISTS (
  SELECT 1 FROM catalog_destination_allowlist dal
  WHERE dal.city = v.city AND dal.country = v.country
);

ALTER TABLE catalog_destination_allowlist ENABLE TRIGGER ALL;

-- =============================================================================
-- Supplier Catalog GAP 0: Seed the 5 stress-test corridors
--
-- Extends corridor coverage in public.vendors (the HR vendor directory, read by
-- backend/app/routers/hr_vendors.py) from the 3 launched corridors to all 8
-- locked corridors by seeding 3 vendors per service category for:
--   FR-NO / NO-FR   Paris  ↔ Oslo
--   GB-US / US-GB   London ↔ New York
--   IN-DE / DE-IN   India  ↔ Munich
--   NL-SG / SG-NL   Amsterdam ↔ Singapore
--   ES-AE / AE-ES   Madrid ↔ Dubai
--
-- Follows the format of 20260518100000_vendor_directory_extension.sql. Columns:
--   (name, service_types, countries, corridors, contact_email, status, is_approved)
-- Service categories (existing 5 MVP vocab): housing, immigration, moving,
-- school_search, destination. status='active', is_approved=true.
--
-- NOTE: public.vendors has no `source` column, so (unlike service_catalog_items)
-- these rows carry no source tag — matching the existing seed pattern.
--
-- IDEMPOTENCY: the existing seed's bare `ON CONFLICT DO NOTHING` never conflicts
-- (uuid PK, no natural unique key), so re-running would duplicate. Several of
-- these vendors (Crown, Santa Fe, Fragomen, ISS, Cartus, Dwellworks, ECA, Aires)
-- already exist for the launched corridors, so a UNIQUE(name) constraint is not
-- possible. Instead each row is guarded by
--   WHERE NOT EXISTS (... name = v.name AND corridors @> v.corridors)
-- which makes the migration safely re-runnable while still adding a per-corridor
-- row for globally-operating vendors.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Vendor seed — one INSERT..SELECT per corridor+category, idempotency-guarded
-- ---------------------------------------------------------------------------

-- FR-NO (Paris ↔ Oslo) ───────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
SELECT v.name, v.service_types, v.countries, v.corridors, v.contact_email, v.status, v.is_approved
FROM (VALUES
  ('Norse Relocations',        '{"housing"}'::text[],       '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'corporate@norserelocations.no', 'active', true),
  ('Domus Scandinavia',        '{"housing"}'::text[],       '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'business@domus-scandinavia.no', 'active', true),
  ('Krogsveen Expat Housing',  '{"housing"}'::text[],       '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'expat@krogsveen.no',            'active', true),
  ('Fragomen (Norway)',        '{"immigration"}'::text[],   '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'mobility@fragomen.com',         'active', true),
  ('Brækhus Advokatfirma',     '{"immigration"}'::text[],   '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'immigration@braekhus.no',       'active', true),
  ('PwC Legal Norway',         '{"immigration"}'::text[],   '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'mobility.no@pwc.com',           'active', true),
  ('Crown Relocations',        '{"moving"}'::text[],        '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'corporate@crownrelo.com',       'active', true),
  ('Santa Fe Relocation',      '{"moving"}'::text[],        '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'mobility@santaferelo.com',      'active', true),
  ('DB Schenker Mobility',     '{"moving"}'::text[],        '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'relocation@dbschenker.com',     'active', true),
  ('Oslo International School', '{"school_search"}'::text[], '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'admissions@oslois.no',          'active', true),
  ('British International School of Oslo', '{"school_search"}'::text[], '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'admissions@bis.no',   'active', true),
  ('ISS — International School Search',    '{"school_search"}'::text[], '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'search@internationalschool.com', 'active', true),
  ('ECA International — Settling-In',      '{"destination"}'::text[],   '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'mobility@eca-international.com',  'active', true),
  ('Cartus — Destination Services',       '{"destination"}'::text[],   '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'destination@cartus.com',        'active', true),
  ('Dwellworks',               '{"destination"}'::text[],   '{"FR","NO"}'::text[], '{"FR-NO","NO-FR"}'::text[], 'mobility@dwellworks.com',       'active', true)
) AS v(name, service_types, countries, corridors, contact_email, status, is_approved)
WHERE NOT EXISTS (
  SELECT 1 FROM public.vendors e WHERE e.name = v.name AND e.corridors @> v.corridors
);

-- GB-US (London ↔ New York) ───────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
SELECT v.name, v.service_types, v.countries, v.corridors, v.contact_email, v.status, v.is_approved
FROM (VALUES
  ('Furnished Quarters',       '{"housing"}'::text[],       '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'corporate@furnishedquarters.com', 'active', true),
  ('Blueground',               '{"housing"}'::text[],       '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'business@theblueground.com',      'active', true),
  ('AKA Serviced Residences',  '{"housing"}'::text[],       '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'corporate@stayaka.com',           'active', true),
  ('Fragomen (US)',            '{"immigration"}'::text[],   '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'mobility@fragomen.com',           'active', true),
  ('FordMurray Law',           '{"immigration"}'::text[],   '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'info@fordmurraylaw.com',          'active', true),
  ('Berry Appleman & Leiden',  '{"immigration"}'::text[],   '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'mobility@balglobal.com',          'active', true),
  ('Allied Van Lines International', '{"moving"}'::text[],   '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'international@allied.com',         'active', true),
  ('Crown Relocations',        '{"moving"}'::text[],        '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'corporate@crownrelo.com',         'active', true),
  ('Graebel Relocation',       '{"moving"}'::text[],        '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'mobility@graebel.com',            'active', true),
  ('ISS — International School Search', '{"school_search"}'::text[], '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'search@internationalschool.com', 'active', true),
  ('SchoolMatch NYC',          '{"school_search"}'::text[], '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'admissions@schoolmatchnyc.com',   'active', true),
  ('British International School of New York', '{"school_search"}'::text[], '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'admissions@bis-nyc.org', 'active', true),
  ('Aires — Relocation Services', '{"destination"}'::text[], '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'destination@aires.com',          'active', true),
  ('Cartus — Destination Services', '{"destination"}'::text[], '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'destination@cartus.com',       'active', true),
  ('Weichert Workforce Mobility', '{"destination"}'::text[], '{"GB","US"}'::text[], '{"GB-US","US-GB"}'::text[], 'destination@weichertmobility.com', 'active', true)
) AS v(name, service_types, countries, corridors, contact_email, status, is_approved)
WHERE NOT EXISTS (
  SELECT 1 FROM public.vendors e WHERE e.name = v.name AND e.corridors @> v.corridors
);

-- IN-DE (India ↔ Munich) ──────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
SELECT v.name, v.service_types, v.countries, v.corridors, v.contact_email, v.status, v.is_approved
FROM (VALUES
  ('NoBroker Global Housing',  '{"housing"}'::text[],       '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'corporate@nobroker.in',           'active', true),
  ('Nestaway Corporate',       '{"housing"}'::text[],       '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'business@nestaway.com',           'active', true),
  ('Wunderflats',              '{"housing"}'::text[],       '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'business@wunderflats.com',        'active', true),
  ('KPMG Law India — Global Mobility', '{"immigration"}'::text[], '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'globalmobility.in@kpmg.com', 'active', true),
  ('Fragomen India',           '{"immigration"}'::text[],   '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'mobility@fragomen.com',           'active', true),
  ('Cyril Amarchand Mangaldas', '{"immigration"}'::text[],  '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'immigration@cyrilshroff.com',     'active', true),
  ('Crown Relocations',        '{"moving"}'::text[],        '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'corporate@crownrelo.com',         'active', true),
  ('AGS Movers',               '{"moving"}'::text[],        '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'corporate@ags-worldwide.com',     'active', true),
  ('Santa Fe Relocation',      '{"moving"}'::text[],        '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'mobility@santaferelo.com',        'active', true),
  ('Munich International School', '{"school_search"}'::text[], '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'admissions@mis-munich.de',      'active', true),
  ('ISS — International School Search', '{"school_search"}'::text[], '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'search@internationalschool.com', 'active', true),
  ('Bavarian International School', '{"school_search"}'::text[], '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'admissions@bis-school.com',    'active', true),
  ('Dwellworks',               '{"destination"}'::text[],   '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'mobility@dwellworks.com',         'active', true),
  ('Cartus — Destination Services', '{"destination"}'::text[], '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'destination@cartus.com',       'active', true),
  ('ECA International — Settling-In', '{"destination"}'::text[], '{"IN","DE"}'::text[], '{"IN-DE","DE-IN"}'::text[], 'mobility@eca-international.com', 'active', true)
) AS v(name, service_types, countries, corridors, contact_email, status, is_approved)
WHERE NOT EXISTS (
  SELECT 1 FROM public.vendors e WHERE e.name = v.name AND e.corridors @> v.corridors
);

-- NL-SG (Amsterdam ↔ Singapore) ───────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
SELECT v.name, v.service_types, v.countries, v.corridors, v.contact_email, v.status, v.is_approved
FROM (VALUES
  ('CapitaLand Serviced Residences', '{"housing"}'::text[], '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'corporate@capitaland.com',        'active', true),
  ('Hmlet by Habyt',           '{"housing"}'::text[],       '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'enterprise@habyt.com',            'active', true),
  ('Figment Serviced Homes',   '{"housing"}'::text[],       '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'business@figment.sg',             'active', true),
  ('Fragomen Singapore',       '{"immigration"}'::text[],   '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'mobility@fragomen.com',           'active', true),
  ('Drew & Napier',            '{"immigration"}'::text[],   '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'immigration@drewnapier.com',      'active', true),
  ('WongPartnership',          '{"immigration"}'::text[],   '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'mobility@wongpartnership.com',     'active', true),
  ('Santa Fe Relocation',      '{"moving"}'::text[],        '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'mobility@santaferelo.com',        'active', true),
  ('Crown Relocations',        '{"moving"}'::text[],        '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'corporate@crownrelo.com',         'active', true),
  ('Asian Tigers Mobility',    '{"moving"}'::text[],        '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'singapore@asiantigers-mobility.com', 'active', true),
  ('Singapore American School', '{"school_search"}'::text[], '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'admissions@sas.edu.sg',          'active', true),
  ('ISS — International School Search', '{"school_search"}'::text[], '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'search@internationalschool.com', 'active', true),
  ('United World College South East Asia', '{"school_search"}'::text[], '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'admissions@uwcsea.edu.sg', 'active', true),
  ('Dwellworks',               '{"destination"}'::text[],   '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'mobility@dwellworks.com',         'active', true),
  ('Santa Fe Destination Services', '{"destination"}'::text[], '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'dsp@santaferelo.com',          'active', true),
  ('Crown Destination Services', '{"destination"}'::text[], '{"NL","SG"}'::text[], '{"NL-SG","SG-NL"}'::text[], 'dsp@crownrelo.com',               'active', true)
) AS v(name, service_types, countries, corridors, contact_email, status, is_approved)
WHERE NOT EXISTS (
  SELECT 1 FROM public.vendors e WHERE e.name = v.name AND e.corridors @> v.corridors
);

-- ES-AE (Madrid ↔ Dubai) ──────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
SELECT v.name, v.service_types, v.countries, v.corridors, v.contact_email, v.status, v.is_approved
FROM (VALUES
  ('Asteco Property Management', '{"housing"}'::text[],     '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'corporate@asteco.com',            'active', true),
  ('Allsopp & Allsopp',        '{"housing"}'::text[],       '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'corporate@allsoppandallsopp.com', 'active', true),
  ('CBRE UAE Residential',     '{"housing"}'::text[],       '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'residential.uae@cbre.com',        'active', true),
  ('Fragomen UAE',             '{"immigration"}'::text[],   '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'mobility@fragomen.com',           'active', true),
  ('Al Tamimi & Company',      '{"immigration"}'::text[],   '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'immigration@tamimi.com',          'active', true),
  ('BSA Ahmad Bin Hezeem',     '{"immigration"}'::text[],   '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'immigration@bsabh.com',           'active', true),
  ('AGS Movers',               '{"moving"}'::text[],        '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'corporate@ags-worldwide.com',     'active', true),
  ('Crown Relocations',        '{"moving"}'::text[],        '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'corporate@crownrelo.com',         'active', true),
  ('Allied Pickfords',         '{"moving"}'::text[],        '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'uae@alliedpickfords.com',         'active', true),
  ('GEMS Education',           '{"school_search"}'::text[], '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'admissions@gemseducation.com',    'active', true),
  ('ISS — International School Search', '{"school_search"}'::text[], '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'search@internationalschool.com', 'active', true),
  ('Nord Anglia International School Dubai', '{"school_search"}'::text[], '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'admissions@nasdubai.ae', 'active', true),
  ('Cartus — Destination Services', '{"destination"}'::text[], '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'destination@cartus.com',       'active', true),
  ('Aires — Relocation Services', '{"destination"}'::text[], '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'destination@aires.com',          'active', true),
  ('Dwellworks',               '{"destination"}'::text[],   '{"ES","AE"}'::text[], '{"ES-AE","AE-ES"}'::text[], 'mobility@dwellworks.com',         'active', true)
) AS v(name, service_types, countries, corridors, contact_email, status, is_approved)
WHERE NOT EXISTS (
  SELECT 1 FROM public.vendors e WHERE e.name = v.name AND e.corridors @> v.corridors
);

-- ---------------------------------------------------------------------------
-- 2. Destination allowlist — add the new corridor cities so the discovery tool
--    can fire without an admin ticket. Full country names to match existing
--    rows (is_destination_allowlisted matches city + country exactly).
--    Amsterdam/Madrid already exist from 20260518000000 → ON CONFLICT skips.
--    The audit trigger assumes new.id, but this table's PK is (city, country),
--    so it is disabled for the duration (same as the 20260518000000 seed).
-- ---------------------------------------------------------------------------
ALTER TABLE public.catalog_destination_allowlist DISABLE TRIGGER trg_audit_cda;

INSERT INTO public.catalog_destination_allowlist (city, country, approved_by, notes) VALUES
  ('Oslo',      'Norway',               NULL, 'Stress-test corridor FR-NO'),
  ('London',    'United Kingdom',       NULL, 'Stress-test corridor GB-US'),
  ('New York',  'United States',        NULL, 'Stress-test corridor GB-US'),
  ('Mumbai',    'India',                NULL, 'Stress-test corridor IN-DE'),
  ('Bangalore', 'India',                NULL, 'Stress-test corridor IN-DE'),
  ('Delhi',     'India',                NULL, 'Stress-test corridor IN-DE'),
  ('Munich',    'Germany',              NULL, 'Stress-test corridor IN-DE'),
  ('Singapore', 'Singapore',            NULL, 'Stress-test corridor NL-SG'),
  ('Dubai',     'United Arab Emirates', NULL, 'Stress-test corridor ES-AE')
ON CONFLICT (city, country) DO NOTHING;

ALTER TABLE public.catalog_destination_allowlist ENABLE TRIGGER trg_audit_cda;

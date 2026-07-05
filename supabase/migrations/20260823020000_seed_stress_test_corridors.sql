-- =============================================================================
-- Supplier Catalog GAP 0: Stress-test corridor allowlist seeding
--
-- Adds the 5 stress-test corridors' destination cities to
-- catalog_destination_allowlist so the discovery tool can fire on them without
-- an admin ticket. Full country names to match existing rows
-- (is_destination_allowlisted matches city + country exactly). Amsterdam/Madrid
-- already exist from 20260518000000 → ON CONFLICT skips. The audit trigger
-- assumes new.id, but this table's PK is (city, country), so it is disabled for
-- the duration (same as the 20260518000000 seed).
--
-- NOTE (2026-07-05): This migration originally also seeded public.vendors, but
-- prod's vendors table is the redesign schema (is_active / corridor_codes /
-- countries_served / email — no corridors/status/is_approved/contact_email/
-- countries columns), so those INSERTs could never apply. The vendors seed was
-- removed; recommendation/corridor coverage flows through suppliers +
-- recommendation datasets (System A), and the destination-city dataset rows for
-- this corridor (Dubai living_areas/schools) ship in this same PR as JSON, not
-- SQL. Renamed from 20260823000000 to avoid a version collision with the
-- already-applied 20260823000000_create_auth_page_config.sql.
-- =============================================================================

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

-- Migration: 20260522180000_add_pet_import_rules.sql
-- Purpose: Creates the pet_import_rules lookup table used by the Pets section
--          to surface country-specific import requirements on the Destination page.
-- Task: AIQ-160-D  Created: 2026-05-22

-- ─── Table ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.pet_import_rules (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  destination_country_code  char(2)   NOT NULL,            -- ISO 3166-1 alpha-2
  species               text        NOT NULL,              -- 'dog' | 'cat' | 'other'
  requirements          jsonb       NOT NULL DEFAULT '[]'::jsonb,  -- string[]
  quarantine_days       integer,                           -- NULL = none required
  microchip_required    boolean     NOT NULL DEFAULT false,
  rabies_cert_required  boolean     NOT NULL DEFAULT false,
  health_cert_required  boolean     NOT NULL DEFAULT false,
  notes                 text,
  source_url            text,
  last_verified_at      date,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT pet_import_rules_species_check
    CHECK (species IN ('dog', 'cat', 'other')),
  CONSTRAINT pet_import_rules_quarantine_check
    CHECK (quarantine_days IS NULL OR quarantine_days >= 0),
  CONSTRAINT pet_import_rules_requirements_is_array
    CHECK (jsonb_typeof(requirements) = 'array'),
  UNIQUE (destination_country_code, species)
);

COMMENT ON TABLE public.pet_import_rules IS
  'Country-level pet import rules used by the Pets section to warn HR about '
  'breed bans, quarantine timelines, and certification windows.';

-- ─── Indexes ─────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_pet_import_rules_country
  ON public.pet_import_rules (destination_country_code);

CREATE INDEX IF NOT EXISTS idx_pet_import_rules_country_species
  ON public.pet_import_rules (destination_country_code, species);

-- ─── updated_at trigger ───────────────────────────────────────────────────────

CREATE OR REPLACE TRIGGER trg_pet_import_rules_updated_at
  BEFORE UPDATE ON public.pet_import_rules
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─── RLS ─────────────────────────────────────────────────────────────────────

ALTER TABLE public.pet_import_rules ENABLE ROW LEVEL SECURITY;

-- All authenticated users can read: rules are reference data, not company-scoped.
CREATE POLICY "pet_import_rules_read_authenticated"
  ON public.pet_import_rules
  FOR SELECT
  TO authenticated
  USING (true);

-- Only admins can write (insert/update/delete).
CREATE POLICY "pet_import_rules_write_admin"
  ON public.pet_import_rules
  FOR ALL
  TO authenticated
  USING (public.my_role() = 'admin')
  WITH CHECK (public.my_role() = 'admin');

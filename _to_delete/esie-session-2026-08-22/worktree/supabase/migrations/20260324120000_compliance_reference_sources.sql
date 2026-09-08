-- Optional DB-backed reference store (Phase 11). Runtime v1 reads seed JSON from the API repo.
-- Populate later via admin tooling or SQL; until then `backend/seed_data/compliance_reference_sources.json` is canonical.

CREATE TABLE IF NOT EXISTS public.compliance_reference_sources (
  id text PRIMARY KEY,
  source_key text NOT NULL UNIQUE,
  destination_key text,
  route_key text,
  topic text,
  source_type text NOT NULL,
  reference_strength text NOT NULL DEFAULT 'internal',
  source_title text NOT NULL,
  source_url text,
  source_publisher text,
  reviewed_by text,
  reviewed_at timestamptz,
  effective_date date,
  last_seen_date date,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_compliance_ref_dest_route
  ON public.compliance_reference_sources (destination_key, route_key);

COMMENT ON TABLE public.compliance_reference_sources IS
  'Structured provenance for readiness/compliance; optional mirror of repo seed JSON.';

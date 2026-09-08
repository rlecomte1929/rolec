-- Ledger reconciliation for `otto_staging_schema` (CLAUDE.md § Ledger reconciliation).
--
-- Applied to production out-of-band via MCP `apply_migration` on 2026-08-11 at 22:19:00,
-- which stamps its own wall-clock version and leaves
-- `supabase_migrations.schema_migrations` holding a version with no repo file. That drift
-- fails `check_migration_drift.py` for EVERY migration PR repo-wide, not just the one that
-- caused it — it turned PR #1814 red two minutes after the apply.
--
-- SQL recovered verbatim from that ledger row's `statements` column; it was already
-- idempotent as applied.
--
-- **Third such orphan on 2026-08-11**, all from the same ROR/Otto research workstream:
--   20260811144840  widen_destination_country_checks_relopass_destinations  (→ PR #1803)
--   20260811170803  ror_coverage_ledger                                     (→ PR #1813)
--   20260811221900  otto_staging_schema                                     (this file)
-- Reconciling after the fact is a treadmill. The fix is for that workstream to stop using
-- `apply_migration` and instead commit the migration file first — see CLAUDE.md
-- § "Migration discipline (MANDATORY)".
--
-- Security note, unlike the ror_* tables in 20260811170803: this one is correct. The
-- schema is NOT `public`, and it revokes anon + authenticated at the schema level, so
-- PostgREST cannot reach these tables with the anon key that ships in the frontend bundle.
-- They are consequently outside `check_rls_coverage.py`'s AUDITED_SCHEMAS (public + rce),
-- which is the right answer for a schema-level revoke — but worth knowing that a
-- policy-less table added here would not be flagged.

CREATE SCHEMA IF NOT EXISTS otto_staging;
REVOKE ALL ON SCHEMA otto_staging FROM anon, authenticated;
CREATE TABLE IF NOT EXISTS otto_staging.immigration_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  destination_country text NOT NULL, domain_area text NOT NULL DEFAULT 'immigration',
  topic_key text NOT NULL, title text NOT NULL, batch_id text NOT NULL,
  source text NOT NULL DEFAULT 'otto_research', created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (destination_country, topic_key));
CREATE TABLE IF NOT EXISTS otto_staging.immigration_fact_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  destination_country text NOT NULL, entity_topic_key text NOT NULL,
  fact_type text, fact_key text, fact_text text NOT NULL, applies_to jsonb,
  source_url text NOT NULL, evidence_quote text, confidence text,
  confidence_score numeric NOT NULL, accuracy_tier text NOT NULL,
  extraction_method text NOT NULL DEFAULT 'otto_research', batch_id text NOT NULL,
  dedupe_key text, status text NOT NULL DEFAULT 'new', created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dedupe_key));

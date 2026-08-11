-- Ledger reconciliation — NOT a new change.
--
-- This DDL was applied to production out-of-band on 2026-08-11 22:26:05 UTC and recorded in
-- supabase_migrations.schema_migrations as `otto_staging_ledger_and_queue`, with no matching
-- repo file. That mismatch fails the `migration-drift` CI job on EVERY migration PR, not just
-- the one that introduced it — which is how it surfaced here, on an unrelated rfq_recipients
-- change.
--
-- The body below is recovered verbatim from `statements` on that ledger row, so it is exactly
-- what ran rather than a reconstruction. Both tables were confirmed present in prod at
-- reconciliation time (otto_staging: immigration_entities, immigration_fact_candidates,
-- load_log, processing_queue).
--
-- Note the schema: `otto_staging`, not `public`. The RLS + policy + REVOKE-from-anon gate in
-- CLAUDE.md applies to `public`, which PostgREST exposes; this schema is not exposed, and
-- access is granted explicitly to the `otto_writer` role at the end.
--
-- Per CLAUDE.md "Ledger reconciliation": commit a file at the exact applied version so the
-- repo and the ledger agree. Applying this again is a no-op.

-- Work queue: one row per Audos deliverable to extract. Drives the staged routine.
CREATE TABLE IF NOT EXISTS otto_staging.processing_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_label text NOT NULL UNIQUE,
  kind text NOT NULL,                       -- immigration | vendor | datasheet
  country text,
  expected_count integer,                   -- Otto's own metrics count, when known
  loaded_count integer NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'pending',   -- pending | in_progress | done | stuck
  attempts integer NOT NULL DEFAULT 0,
  last_note text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Ledger: one row per load+reconcile pass. The audit trail for "100% delivered".
CREATE TABLE IF NOT EXISTS otto_staging.load_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id text NOT NULL,
  source_label text NOT NULL,
  expected_count integer,
  loaded_count integer NOT NULL,
  reconcile_status text NOT NULL,           -- pass | partial | fail
  discrepancy text,
  notes text,
  run_ts timestamptz NOT NULL DEFAULT now()
);
GRANT INSERT, SELECT ON otto_staging.processing_queue, otto_staging.load_log TO otto_writer;

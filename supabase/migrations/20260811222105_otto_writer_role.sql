-- Ledger reconciliation for `otto_writer_role` (CLAUDE.md § Ledger reconciliation).
--
-- Applied to production out-of-band via MCP `apply_migration` on 2026-08-11 at 22:21:05 —
-- two minutes after 20260811221900 and while PR #1814 was already red from that one. SQL
-- recovered verbatim from the ledger row's `statements` column.
--
-- FOURTH orphan on 2026-08-11 from the same ROR/Otto research workstream (144840, 170803,
-- 221900, 222105). Each one fails `check_migration_drift.py` for every migration PR
-- repo-wide until someone commits a file like this. The fix is not faster reconciliation;
-- it is that workstream committing the file first — CLAUDE.md § "Migration discipline".
--
-- The SQL itself is sound and deliberately least-privilege: NOLOGIN with no password (so it
-- cannot be used until an operator enables login), USAGE + INSERT/SELECT confined to
-- otto_staging, and an explicit REVOKE from public. Nothing to fix here beyond the ledger.
--
-- Note for whoever runs a fresh `supabase db reset`: this is a role (cluster-level), not
-- schema. It is idempotent via the pg_roles guard, but the role will not exist on a local
-- stack unless this runs there too.

-- Least-privilege writer for Otto: can ONLY insert/read into otto_staging.
-- Created with NOLOGIN + no password; Romain enables login and sets the password himself.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='otto_writer') THEN
    CREATE ROLE otto_writer NOLOGIN;
  END IF;
END $$;
GRANT USAGE ON SCHEMA otto_staging TO otto_writer;
GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA otto_staging TO otto_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA otto_staging GRANT INSERT, SELECT ON TABLES TO otto_writer;
-- Explicitly keep it away from everything else:
REVOKE ALL ON SCHEMA public FROM otto_writer;

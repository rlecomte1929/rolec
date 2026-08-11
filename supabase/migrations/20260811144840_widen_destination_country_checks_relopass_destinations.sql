-- Ledger reconciliation. NOT new work — this file documents DDL that is ALREADY APPLIED
-- to production, so that the ledger row has a matching repo file.
--
-- WHY THIS FILE EXISTS. On 2026-08-11 at 14:48:40 UTC a migration was applied to production
-- through MCP `apply_migration`. That tool stamps its own version from the wall clock, so
-- the ledger gained
--
--     20260811144840  widen_destination_country_checks_relopass_destinations
--
-- with no corresponding file in supabase/migrations/. `scripts/check_migration_drift.py`
-- fails on exactly that shape (Direction A: "prod version with no repo file"), which
-- blocked EVERY open migration PR repo-wide until reconciled — it is a shared gate, not a
-- per-PR one.
--
-- The script's own prevention note names the cause: "don't pre-apply repo-tracked
-- migrations via MCP apply_migration — commit the file and let the main-push migration
-- workflow apply it (it records the repo version)." CLAUDE.md says the same under
-- "Migration discipline (MANDATORY)". `apply_migration` cannot record a repo version
-- because it has no repo file to read one from; that is inherent to the tool, not a
-- misuse of it, which is why the rule is "don't use it for repo-tracked schema changes"
-- rather than "use it carefully".
--
-- The safe route for an out-of-band apply is `execute_sql` for the DDL followed by
--   supabase migration repair --status applied <repo version> --db-url "$DATABASE_URL"
-- (port 5432 — `repair` fails against the 6543 transaction pooler with
-- 'prepared statement "lrupsc_1_0" already exists'), which records the REPO version and
-- leaves no orphan.
--
-- PROVENANCE OF THE SQL BELOW. Recovered verbatim from
-- `supabase_migrations.schema_migrations.statements` for version 20260811144840, then
-- checked against the live constraint definitions via pg_get_constraintdef — both
-- `requirement_entities_destination_country_check` and
-- `knowledge_packs_destination_country_check` carry exactly this 21-country array in
-- production. This file is a description of reality, not a proposal.
--
-- WHAT IT DOES. Widens the permitted `destination_country` values on the two
-- requirements-engine tables from a narrower list to the 21 ReloPass destinations. Adding
-- values to a CHECK's allowed set cannot invalidate an existing row, so this is safe to
-- replay.
--
-- Idempotent, unlike the original: the applied statements used a bare `DROP CONSTRAINT`,
-- which errors on a second run. `IF EXISTS` plus a guarded re-add lets this file be
-- replayed against a fresh branch database, which is the point of committing it at all.

ALTER TABLE public.requirement_entities
  DROP CONSTRAINT IF EXISTS requirement_entities_destination_country_check;
ALTER TABLE public.requirement_entities
  ADD CONSTRAINT requirement_entities_destination_country_check
  CHECK (destination_country = ANY (ARRAY[
    'SG','US','DE','GB','ES','IT','AE','FR','NO','JP','NZ',
    'DK','BE','AT','PT','CA','AU','NL','CH','SE','IE'
  ]));

ALTER TABLE public.knowledge_packs
  DROP CONSTRAINT IF EXISTS knowledge_packs_destination_country_check;
ALTER TABLE public.knowledge_packs
  ADD CONSTRAINT knowledge_packs_destination_country_check
  CHECK (destination_country = ANY (ARRAY[
    'SG','US','DE','GB','ES','IT','AE','FR','NO','JP','NZ',
    'DK','BE','AT','PT','CA','AU','NL','CH','SE','IE'
  ]));

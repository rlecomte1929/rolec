# #176 resolution plan (2026-06-02)

> **Scope:** concrete next-PR plan that closes `#176 — feat(C2-06-FOLLOWUP): policy-gap adapter + rce.case_artefacts + endpoint`. **Doc-only deliverable** — no PR opened, no prod writes. Execute when ready.

## Background — why #176 was stuck

#176 carries two migrations: `20260529160000_rce_policy_gaps.sql` and `20260529161000_rce_case_artefacts.sql`. Both use bare `CREATE TABLE` + permissive RLS (`*_permissive` policies, `USING (true)` to authenticated). Yesterday's attempts (`audit/daytime-run-stuck.md` § #176 entries) surfaced three blockers:

1. **The migrations would fail on apply.** Both tables already exist on prod (applied out-of-band as `20260529125415_rce_policy_gaps` and `20260529125813_rce_case_artefacts` — neither has a repo source file). Bare `CREATE TABLE` → `relation already exists`.
2. **The permissive policies are a security regression.** Prod's policies are `<table>_service_role_only` (FOR ALL TO service_role). #176 declares `<table>_permissive` (FOR ALL TO authenticated, `USING(true)`). The names differ, so `DROP POLICY IF EXISTS <#176 name>` wouldn't catch the live ones — applying #176 would leave BOTH policies in place, OR-combining them. Authenticated users would gain read/write on tables that are currently service-role-only.
3. **Prod's schema is more evolved.** `rce.case_artefacts` on prod has two unique constraints absent from #176's migration: `case_artefacts_one_per_source_doc UNIQUE (source_document_id)` and `case_artefacts_one_per_source_cost UNIQUE (source_cost_id)`.

The root canonical policy comes from a **third** missing migration (`20260530111216 / 20260531020000_rce_service_role_only`) — a `DO $$` block that hardens every `rce.*` table to service-role-only. See `audit/migration-drift-definitive-2026-06-02.md` for the full drift picture.

## The unblock artifact — the prod canonical statements

### 1. `rce.policy_gaps` (prod version `20260529125415`)

```sql
CREATE TABLE rce.policy_gaps (
  gap_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  policy_clause_id  UUID NOT NULL REFERENCES rce.policy_clauses(policy_clause_id) ON DELETE CASCADE,
  clause_type       TEXT NOT NULL,
  family_member_id  UUID REFERENCES rce.family_members(family_member_id) ON DELETE CASCADE,
  subject_kind      TEXT NOT NULL CHECK (subject_kind IN (
                      'EMPLOYEE','SPOUSE','CHILD','DEPENDENT_PARENT','CASE')),
  gap_type          TEXT NOT NULL CHECK (gap_type IN (
                      'MISSING_BENEFIT_DELIVERY','MISSING_DOCUMENT','BELOW_ENTITLEMENT')),
  suggested_action  TEXT,
  evidence_payload  JSONB,
  citation          JSONB,
  detected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  cleared_at        TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX policy_gaps_open_unique
  ON rce.policy_gaps (
    case_id,
    policy_clause_id,
    gap_type,
    COALESCE(family_member_id, '00000000-0000-0000-0000-000000000000'::uuid)
  )
  WHERE cleared_at IS NULL;

CREATE INDEX policy_gaps_by_case_open
  ON rce.policy_gaps (case_id) WHERE cleared_at IS NULL;

ALTER TABLE rce.policy_gaps ENABLE ROW LEVEL SECURITY;
```

### 2. `rce.case_artefacts` (prod version `20260529125813`)

```sql
CREATE TABLE rce.case_artefacts (
  artefact_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id              UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  kind                 TEXT NOT NULL,
  subject_kind         TEXT NOT NULL CHECK (subject_kind IN (
                         'EMPLOYEE','SPOUSE','CHILD','DEPENDENT_PARENT','CASE')),
  family_member_id     UUID REFERENCES rce.family_members(family_member_id) ON DELETE CASCADE,
  payload              JSONB,
  magnitude            NUMERIC,
  unit                 TEXT,
  delivered_at         TIMESTAMPTZ,
  source_document_id   UUID REFERENCES rce.documents(document_id) ON DELETE CASCADE,
  source_cost_id       UUID REFERENCES rce.costs(cost_id) ON DELETE CASCADE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT case_artefacts_one_per_source_doc UNIQUE (source_document_id),
  CONSTRAINT case_artefacts_one_per_source_cost UNIQUE (source_cost_id),
  CONSTRAINT case_artefacts_subject_consistency CHECK (
    (subject_kind = 'CASE' AND family_member_id IS NULL)
    OR (subject_kind IN ('SPOUSE','CHILD','DEPENDENT_PARENT') AND family_member_id IS NOT NULL)
    OR (subject_kind = 'EMPLOYEE' AND family_member_id IS NULL)
  )
);

CREATE INDEX case_artefacts_by_case_kind ON rce.case_artefacts (case_id, kind);
CREATE INDEX case_artefacts_by_subject ON rce.case_artefacts (case_id, subject_kind, family_member_id);

ALTER TABLE rce.case_artefacts ENABLE ROW LEVEL SECURITY;
```

### 3. `rce_service_role_only` hardening (prod version `20260530111216`)

```sql
DO $$
DECLARE
  t text;
BEGIN
  FOR t IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'rce'
      AND c.relkind = 'r'
    ORDER BY c.relname
  LOOP
    EXECUTE format('drop policy if exists %I on rce.%I', t || '_permissive', t);
    EXECUTE format('drop policy if exists %I on rce.%I', t || '_permissive_all', t);

    EXECUTE format(
      'create policy %I on rce.%I for all to service_role using (true) with check (true)',
      t || '_service_role_only', t
    );

    EXECUTE format('revoke all on rce.%I from authenticated', t);
    EXECUTE format('revoke all on rce.%I from public', t);
    EXECUTE format('revoke all on rce.%I from anon', t);

    EXECUTE format('grant all on rce.%I to service_role', t);
  END LOOP;
END $$;

COMMENT ON SCHEMA rce IS
  'ReloPass Case Engine (RCE) ontology. As of C1-01a (SEC sprint, 2026-05-30) every table here is service_role-only — the backend reads via service key, no PostgREST anon/authenticated access. Restore tenant-scoped policies when the auth-to-rce bridge ships.';
```

## The new migration to author

**File:** `supabase/migrations/<NEXT-TS>_rce_policy_gaps_and_case_artefacts_with_service_role_hardening.sql`

**Timestamp:** strictly greater than the latest on `origin/main`. As of `bcb071b4` the latest is `20260602000000_rce_contradictions.sql` — use `20260602200000` (or whatever's strictly greater at execution time; re-check before commit).

**Structure (combine all three prod migrations into one file for replay-safety):**

```sql
-- ===========================================================================
-- Backfill for #176 — rce.policy_gaps + rce.case_artefacts + service-role-only
-- hardening, all in one file so a fresh `supabase db reset` reaches the same
-- end-state as prod (see audit/migration-drift-definitive-2026-06-02.md).
--
-- These three logical migrations were applied to prod out-of-band:
--   20260529125415  rce_policy_gaps              (table + permissive RLS)
--   20260529125813  rce_case_artefacts           (table + permissive RLS)
--   20260530111216  rce_service_role_only        (DO loop, flips rce.* policies)
-- None of them had repo source files. This migration is idempotent so it
-- applies cleanly to fresh DBs AND no-ops on prod (where the tables and
-- policies already exist in their final state).
-- ===========================================================================

-- Step 1 — tables (idempotent)

CREATE TABLE IF NOT EXISTS rce.policy_gaps (
  gap_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- ... (full column list above)
);

CREATE UNIQUE INDEX IF NOT EXISTS policy_gaps_open_unique
  ON rce.policy_gaps (
    case_id, policy_clause_id, gap_type,
    COALESCE(family_member_id, '00000000-0000-0000-0000-000000000000'::uuid)
  )
  WHERE cleared_at IS NULL;

CREATE INDEX IF NOT EXISTS policy_gaps_by_case_open
  ON rce.policy_gaps (case_id) WHERE cleared_at IS NULL;

CREATE TABLE IF NOT EXISTS rce.case_artefacts (
  artefact_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- ... (full column list above incl. the two UNIQUE constraints)
);

CREATE INDEX IF NOT EXISTS case_artefacts_by_case_kind ON rce.case_artefacts (case_id, kind);
CREATE INDEX IF NOT EXISTS case_artefacts_by_subject  ON rce.case_artefacts (case_id, subject_kind, family_member_id);

-- Step 2 — enable RLS (idempotent — Postgres no-ops if already enabled)

ALTER TABLE rce.policy_gaps    ENABLE ROW LEVEL SECURITY;
ALTER TABLE rce.case_artefacts ENABLE ROW LEVEL SECURITY;

-- Step 3 — service-role-only policies (the rce.* canonical convention)
-- Mirrors the DO-block at prod version 20260530111216 but targets only the
-- two tables this migration introduces, so it's safe to drop in.

DROP POLICY IF EXISTS policy_gaps_permissive          ON rce.policy_gaps;
DROP POLICY IF EXISTS policy_gaps_permissive_all      ON rce.policy_gaps;
DROP POLICY IF EXISTS policy_gaps_service_role_only   ON rce.policy_gaps;
CREATE POLICY policy_gaps_service_role_only
  ON rce.policy_gaps FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS case_artefacts_permissive        ON rce.case_artefacts;
DROP POLICY IF EXISTS case_artefacts_permissive_all    ON rce.case_artefacts;
DROP POLICY IF EXISTS case_artefacts_service_role_only ON rce.case_artefacts;
CREATE POLICY case_artefacts_service_role_only
  ON rce.case_artefacts FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- Step 4 — revoke from non-service-role, grant to service-role
-- Idempotent (REVOKE / GRANT are repeatable).

REVOKE ALL ON rce.policy_gaps    FROM anon, authenticated, public;
REVOKE ALL ON rce.case_artefacts FROM anon, authenticated, public;

GRANT ALL ON rce.policy_gaps    TO service_role;
GRANT ALL ON rce.case_artefacts TO service_role;
```

## Files to drop from #176's branch

```
supabase/migrations/20260529160000_rce_policy_gaps.sql
supabase/migrations/20260529161000_rce_case_artefacts.sql
```

Both carry stale duplicate-named migrations with the wrong (permissive) policies. Remove them from the branch entirely; the new combined migration above replaces both.

## What to KEEP from #176

- `backend/app/routers/policy_gaps.py` (router — already dual-layer registered correctly in BOTH `backend/app/main.py` and `backend/main.py`)
- `backend/app/services/policy_evidence/*.py` (detectors: housing_benefit, immigration_support, language_training)
- `backend/app/services/policy_gap_adapter.py` + adapter helpers
- Tests
- Frontend bits, if any

None of those require modification — they read/write the existing prod tables via the backend's service-role connection (the pooler bypasses RLS), so the policy change from permissive → service-role-only has no effect on them.

## Execution sequence (when ready)

1. **Rebase #176 on current main** (`origin/main` at execution time — likely past `bcb071b4`).
2. **Delete the two old migrations** from the branch.
3. **Author the new combined migration** at the file path above. Use the SQL spec in this doc verbatim for the `CREATE TABLE` blocks (copy from the unblock artifact section).
4. **Local sanity:**
   - `python3 -c "from backend.main import app; print(sorted([r.path for r in app.routes if '/policy-gaps' in r.path]))"` — confirm the policy_gaps endpoints mount on `backend.main:app` (no dual-layer regression).
   - `python scripts/check_router_registrations.py` — should print `PASS — every modular-app router is registered in backend/main.py or grandfathered (21 allowlisted, pending triage).`
   - `cd frontend && npx tsc --noEmit` — clean.
5. **Push, watch CI.** The dual-layer guard (live as of #215) will report PASS. Backend tests should pass — the router code is unchanged.
6. **Pause for Romain's approval before merge** — schema migrations always get the explicit-go checkpoint. Confirm:
   - Pre-merge guards green (main CI success, `/health` 200).
   - 5 real checks green with realistic durations.
   - Verify mergeable=CLEAN.
7. **Merge** `gh pr merge 176 --merge --delete-branch`.
8. **Apply migration via MCP** — `apply_migration` with the file's SQL content. **Expect success** (all `IF NOT EXISTS` / `DROP POLICY IF EXISTS` — true no-op on prod).
9. **Verify on prod (via MCP):**
   ```sql
   -- both tables exist
   SELECT table_name FROM information_schema.tables
     WHERE table_schema='rce' AND table_name IN ('policy_gaps','case_artefacts')
     ORDER BY 1;
   -- expect: case_artefacts, policy_gaps

   -- policies are the *service_role_only ones (and ONLY those)
   SELECT tablename, policyname, cmd, roles
     FROM pg_policies
     WHERE schemaname='rce' AND tablename IN ('policy_gaps','case_artefacts')
     ORDER BY tablename, policyname;
   -- expect 2 rows, each *_service_role_only, cmd=ALL, roles={service_role}
   -- HARD STOP if any *_permissive or *_permissive_all rows present.

   -- grants
   SELECT grantee, privilege_type
     FROM information_schema.role_table_grants
     WHERE table_schema='rce' AND table_name IN ('policy_gaps','case_artefacts')
     ORDER BY 1,2;
   -- expect service_role + postgres only; NO anon/authenticated.
   ```
10. **Anon smoke** (rce schema isn't PostgREST-exposed → 406, same pattern as `rce.contradictions` and `rce.rule_change_proposals`):
    ```bash
    ANON=$(grep '^VITE_SUPABASE_ANON_KEY=' frontend/.env.development | cut -d= -f2-)
    curl -s -o /dev/null -w "%{http_code}\n" \
      "https://nsvefcvpvwwwhuqyuqmp.supabase.co/rest/v1/policy_gaps?select=gap_id&limit=1" \
      -H "apikey: $ANON" -H "Accept-Profile: rce"
    # expect 406 "Invalid schema: rce"
    ```
11. **Update logs:**
    - `audit/daytime-run-stuck.md` — mark #176 RESOLVED with merge SHA + verification results.
    - `audit/migration-drift-definitive-2026-06-02.md` — strike-through hard-drift entries 1, 2, 5 (now backfilled). Drift count drops 6 → 3.

## Hard stops

- **MCP `apply_migration` fails for any reason:** stop, do not retry. Same gate that caught #194. Likely cause would be a typo in the SQL — open the migration file, eyeball the policy-name strings.
- **`pg_policies` verification shows any `*_permissive` row remaining** after migration apply: stop. Means the DROP POLICY IF EXISTS didn't catch a name we don't know about. Pull the policy list, name it explicitly in a follow-up.
- **Mount-check fails** (any of the policy_gaps endpoints not on `backend.main:app`): the dual-layer guard would have failed CI first, but if it didn't and the manual check fails, stop — the registration in `backend/main.py` regressed and needs fixing.
- **CI guard reports FAIL:** means the rebase lost the `backend/main.py` registration for `policy_gaps`. Re-add it manually.

## Open follow-ups (not part of this PR)

- **`rls_error_tracking_harden` landmine** — independent fix; see `audit/194-replay-landmine-2026-06-02.md`.
- **The other 3 hard-drift entries** (`public_agent_runs`, `enable_rls_tenant_tables`, `bucket_hardening_sec006`) — separate backfill PRs. Lower priority than #176 (none are blocking) but security-critical for replay correctness.
- **`_remote_stub` backfill** — the broader structural drift, see `migration-drift-definitive-2026-06-02.md` § structural finding.

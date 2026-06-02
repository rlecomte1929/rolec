# #194 replay landmine: `rls_error_tracking_harden` (2026-06-02)

> **Scope:** Problem statement + fix options. **No prod writes, no PR.** Diagnosed during the migration drift reconciliation session.

## The file in question

`supabase/migrations/20260530000000_rls_error_tracking_harden.sql` (on `origin/main` since the #194 merge `eab464eb`, 2026-06-01).

## Problem

The migration's admin policies use the predicate `profiles.id = auth.uid()::text`. In prod, `public.profiles.id` is `uuid`, not `text`. Running this SQL against any database where `profiles.id` is uuid raises:

```
ERROR 42883: operator does not exist: uuid = text
```

Result: **any `supabase db reset` on a clean local dev database aborts at this file.** The fresh-dev-setup path is broken.

## Why prod is not on fire

Prod was protected by the same error that broke the apply yesterday — the `apply_migration` MCP call returned `42883`, the transaction rolled back, and prod was untouched. The fix-forward was **#212** (`5ab3d39e`), which authored a new migration `20260601130000_fix_rls_error_harden_uuid_cast.sql` using the correct cast direction (`profiles.id::uuid = auth.uid()`). That migration applied cleanly and is the policy state prod is in today.

So:
- **Prod:** correct policies in place via #212.
- **Repo on main:** the broken #194 file is still there.
- **Fresh `supabase db reset`:** runs in timestamp order, hits `20260530000000` (the broken file) **before** reaching the `20260601130000` fix, fails, aborts.

## Why it slipped CI

CI's `frontend-build` and `backend-tests` jobs don't apply migrations against a real database. The `rls-coverage` job is gated off (`vars.RLS_COVERAGE_DATABASE_URL_SET` unset) and only validates *coverage* (policy-less tables vs allowlist) against the live DB as-is — it does not exercise pending migration SQL. Net effect: a migration with a type-mismatched predicate compiles fine syntactically, passes review and CI, and merges. This is the same gap captured in `audit/ci-gap-rls-migration-types.md` — that note remains current.

## Severity

**Medium.** Not blocking prod. Not blocking any pending PR (#176 and #209 don't share lineage with this file). Blocks **anyone** trying to set up a fresh dev database from this repo — and silently introduces an inconsistency between repo state and prod state that will eventually bite a Supabase branch preview or a CI-with-real-DB upgrade.

Higher priority than yesterday's framing suggested — Romain's morning note ranked it "Higher priority than #176, arguably." That stands: any time the team's onboarding path or any infra-as-code consumer (Supabase branches, schema diff tooling, fresh local clones) touches this, they will fail at this file and need to triage.

## Fix options

### Option (a) — in-place edit of the offending file

Edit `20260530000000_rls_error_tracking_harden.sql` directly to use the cast pattern from #212:

```sql
-- BEFORE (broken):
USING (auth.uid()::text = profiles.id)

-- AFTER (correct):
USING (profiles.id::uuid = auth.uid())
```

**Pros:** Minimal repo footprint. One-file change.
**Cons:** Rewrites git history of a merged migration file. Some teams strictly forbid this (the "migrations are append-only" rule). Doesn't change prod (already correct via #212), but the new file content would also be a no-op on prod via the `DROP POLICY IF EXISTS` clauses if it existed there.

### Option (b) — additional no-op-on-prod migration that supersedes (RECOMMENDED)

Author `<NEXT-TS>_rls_error_tracking_replay_safe.sql` that:

1. Drops the broken policies (if they somehow exist).
2. Recreates them with the correct cast direction.

```sql
-- Idempotent: applies cleanly on fresh DBs (replaces the broken predicate
-- before it ever hits prod-style data); no-op on prod (#212 already applied
-- these correct policies). See audit/194-replay-landmine-2026-06-02.md.

DROP POLICY IF EXISTS error_logs_admin_select  ON public.error_logs;
DROP POLICY IF EXISTS error_tickets_admin_select ON public.error_tickets;
DROP POLICY IF EXISTS error_tickets_admin_update ON public.error_tickets;

-- (Paste the exact policy bodies from migration 20260601130000_fix_rls_error_harden_uuid_cast.sql
--  which is the canonical correct version. The cast is `profiles.id::uuid = auth.uid()`.)
```

**Pros:** Preserves git history, follows the append-only convention, mirrors how #212 itself fixed the issue.
**Cons:** Adds a third file related to the same logical change. Doesn't address that `20260530000000_rls_error_tracking_harden.sql` will *still* fail when fresh-DB replay reaches it.

**This is the recommended path,** but it's incomplete — see (b+).

### Option (b+) — option (b) PLUS make the broken file a true no-op

Author the new migration as in (b), and **also** edit `20260530000000_rls_error_tracking_harden.sql` to be a no-op (e.g. comment out the body, leaving only `-- Superseded by …` references). This way:

- Replay walks past `20260530000000` cleanly (no SQL to fail on).
- The canonical fix lands at the NEW timestamp via the new file.
- Git history shows the original file *was* there (preserves provenance).

The edit-to-no-op is a defensible append-only-style amendment because no SQL executes — it's purely documentary. This is the **cleanest** of the three options.

### Option (c) — merge the #212 fix back into the offending file

Replace `20260530000000_rls_error_tracking_harden.sql` content with `20260601130000_fix_rls_error_harden_uuid_cast.sql` content, and delete `20260601130000_*`. One migration file at the original timestamp, with the correct SQL.

**Pros:** Lowest file count.
**Cons:** Rewrites two migration files. Most aggressive history change.

## Recommendation

**Option (b+)** — author the new replay-safe migration AND no-op the broken one. Matches how the repo already handles forward-fixes (the #212 chain) while solving the replay landmine.

## Estimated effort

~30 min:

- 10 min: write the new migration's SQL (mostly copy-paste from #212's existing file).
- 5 min: comment out the body of `20260530000000_rls_error_tracking_harden.sql` with provenance comment.
- 5 min: PR open + CI watch.
- 5 min: pre-merge guards + merge.
- 5 min: MCP `apply_migration` (no-op on prod, but proves the new migration applies cleanly) + verify pg_policies unchanged.

## Hard stops (if executed)

- MCP apply returns anything other than success: stop, surface. Prod is already correct so this should be a clean no-op; any error means the new migration's SQL has a real bug.
- After apply, `SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename IN ('error_logs','error_tickets')` returns ≠ 3 (1 on error_logs admin_select, 2 on error_tickets admin_select+admin_update): stop, surface.

## Open question for Romain

The repo has no documented "migrations are append-only" rule (CLAUDE.md doesn't speak to it). Decide whether option (b+)'s "no-op the body of the historical broken migration" amendment is acceptable per project convention, or whether to default to (b) and live with the replay landmine until the broader `_remote_stub` backfill addresses it.

# CI gap: RLS migration type mismatches go undetected

**Filed:** 2026-06-01 (follow-up for Tuesday-morning review — not for action today).
**Triggered by:** PR #194's `20260530000000_rls_error_tracking_harden.sql` merging green, then failing on apply to prod with `ERROR 42883: operator does not exist: uuid = text` (it gated admin policies on `profiles.id = auth.uid()::text` while prod `profiles.id` is `uuid`). Fixed forward in PR #212.

## The gap

CI cannot catch uuid/text (or any column-type) mismatches in RLS migration policies because **it never applies the migrations against a real database**. The `frontend-build` and `backend-tests` jobs don't touch Postgres, and the one job that would — `rls-coverage` (`scripts/check_rls_coverage.py`) — is **gated off**: it only runs when `vars.RLS_COVERAGE_DATABASE_URL_SET == 'true'`, which is currently unset, so it reports `skipping` on every PR. Even if it ran, it only checks *coverage* (policy-less tables vs the allowlist) against the live DB as-is; it does not apply pending migrations, so it still wouldn't exercise the new policy SQL.

Net effect: a migration with a type-mismatched predicate compiles fine as text, passes review and CI, merges, and only fails when a human applies it to prod — or worse, silently breaks a future `supabase db reset`/replay.

## Fix to consider

Add a CI job that spins up a throwaway Postgres (e.g. the `supabase/postgres` image or a service container), seeds the minimal schema the migrations need (or replays the full migration history), and **applies the PR's new migrations before asserting**. That would have surfaced the `uuid = text` error at PR time. Enabling `rls-coverage` against that fresh, migration-applied test DB (rather than the live DB) would catch both this class of type bug *and* missing-policy regressions in one job.

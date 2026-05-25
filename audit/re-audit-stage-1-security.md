# Re-audit — Stage 1 (Security & ops hygiene)

**Lens:** Security (CSO-style).
**Method:** Walk the audit findings closed/touched by Stage 1, verify each by inspection of merged code (or in-branch code for the Stage 1 PR), grep for new issues introduced, and recompute the lens score.

**Stage 1 baseline (`audit/02-expert-security.md`):** **6.5 / 10**
**After Stage 1:** **7.5 / 10** (+1.0)

The +1.0 is conservative because Stage 1 ships infrastructure (RLS audit script + CI guard) but not the actual RLS triage of 113 tables; that work is queued as AUDIT-A3-followup. A1 also has follow-up work (A1-followup) for deeper init_db silent-failure DDL.

---

## Findings status

### SEC-3 (P0): `cases.get_case` was unguarded in source
**Closed.** Verified at `backend/app/routers/cases.py:137` — handler now has `Depends(get_current_user)` parameter and `_assert_case_access(user, case_id)` call at line 142. This was landed by the team in commit `4a3b43c` (or adjacent), validated during Stage 1.
**Side discovery (open):** `patch_case` at the next handler in the same file does NOT have `Depends(get_current_user)`. Same latent risk class. Filed as a new finding (not on the Stage 1 PR — out of scope).

### SEC-2 (P0): RLS coverage gap
**Partially closed (instrumentation shipped; triage outstanding).**
- `scripts/check_rls_coverage.py` written. Runs the canonical `pg_tables × pg_policies` audit query.
- `supabase/rls_allowlist.txt` seeded with 113 policy-less tables found on the live DB on 2026-05-25. Each is marked PENDING SECURITY TRIAGE in the file header.
- CI step `rls-coverage` added to `.github/workflows/ci.yml`. Runs only when `RLS_COVERAGE_DATABASE_URL` secret is set (the team will need to set this in repo secrets pointing at a read-only DB role).
- CI passes today because the allowlist matches the current state. **The intent is that the list DRAINS, not grows.**
- Follow-up: AUDIT-A3-followup (Notion) tracks per-table triage. For each of the 113: add an RLS policy migration OR keep the entry with a per-table comment justifying server-role-only.

### SEC-1 (P0): `ensure_initialized` startup transaction abort
**Partially closed.** The originally-reported failing statement (`CREATE INDEX IF NOT EXISTS idx_sqlite_pc_benefits_version`) no longer fails. Specifically:
- 3 `_sqlite_ensure_*` helper functions (using `sqlite_master` / `PRAGMA`) now gated by `if _is_sqlite:` so they don't run on Postgres.
- 5 PRAGMA-using try blocks gated by `if _is_sqlite:`.
- 3 CREATE INDEX try blocks + 1 ALTER-loop wrapped in `conn.begin_nested()` savepoints so caught errors no longer abort the outer transaction.

**Remaining work (A1-followup):** during Stage 1 verification, restarting backend revealed the failure pattern continues at a different DDL statement further down in `init_db` (`CREATE TABLE IF NOT EXISTS support_cases`). The pattern is the same — silent ALTER/CREATE failure cascading via the giant `with self.engine.begin()` block. Proper fix is either (a) a top-level `if not _is_sqlite: return early` after `_maybe_ensure_postgres_*` helpers run, or (b) savepoint-wrap every remaining try/except DDL in init_db. Filed as AUDIT-A1-followup (Notion).

### SEC-4 (P1): Service-role key spread (`SUPABASE_SERVICE_ROLE_KEY`)
**Not touched by Stage 1.** Still 5 known call sites:
- `backend/database.py`, `backend/main.py`
- `backend/app/routers/ab_tests.py`
- `backend/services/supabase_client.py`, `backend/services/policy_storage_health.py`
Plan: Stage 7 or later — depends on whether refactoring `ab_tests.py` to use anon-key is worth the migration effort.

### SEC-5 (P1): OCR LLM call lacks retry/timeout/structured-output
**Not touched.** Slated for Stage 7 (LLM hardening) — out of Stage 1 scope.

### SEC-6 (P1): `assistant_router.ts` security
**Not touched.** Slated for Stage 7 follow-up.

### SEC-7 (P1): 7 routers with no auth import
**Not touched** — out of Stage 1 scope (each needs case-by-case decision; not a single PR).

### SEC-8 (P1): Webhook auth ambiguity
**Not touched** — out of scope.

---

## New findings introduced in Stage 1

| ID | Title | Notion | Priority |
|---|---|---|---|
| (new) | `patch_case` (next handler in `cases.py`) lacks `Depends(get_current_user)` | (to file) | P1 |
| AUDIT-A1-followup | Extend savepoint pattern to remaining `init_db` try/except DDL (or skip block entirely on Postgres) | (filed) | P1 |
| AUDIT-A3-followup | Triage 113 policy-less tables — RLS policy vs comment-justified allowlist entry | (filed) | P0 (security gap is real; the script just made it visible) |

---

## Scoring rationale

| Sub-dimension | Δ |
|---|---|
| `cases.get_case` is no longer source-unguarded (SEC-3 closed) | +0.5 |
| RLS coverage instrumentation + CI guard exists (SEC-2 started, not closed) | +0.3 |
| `ensure_initialized` no longer fails at the originally-reported site; class of issue still present (SEC-1 partial) | +0.3 |
| New finding: `patch_case` likely unguarded (discovered while validating SEC-3) | -0.1 |
| **Net** | **+1.0** |

**6.5 → 7.5** is a conservative read. Score moves toward 8.5 once A1-followup + A3-followup land.

---

## What Stage 1 explicitly did NOT do

- Actual triage of any of the 113 policy-less tables (queued).
- Fix the remaining silent-failure DDL in `init_db` (queued).
- Touch `patch_case` or any other handler outside the audit's named A2 target.
- Change service-role key usage.
- Run a `gitleaks` secret-history scan (still recommended; queued).

---

## Open questions for Stage 2 to act on

1. Does the `patch_case` finding belong to Stage 1 (security) or Stage 2 (which is copy-focused)? Recommend: file as P1 and address in Stage 8a alongside the route-auth CI check (which would have caught it).
2. Should the rls-coverage CI step run in `WARN` mode for an initial period? Currently it FAILS on missing entries. Today's allowlist matches state exactly so it passes; recommend keeping it strict so new gaps fail immediately.
3. Does the team have a read-only DB role to use for `RLS_COVERAGE_DATABASE_URL`? If not, the CI step's `if:` condition (`RLS_COVERAGE_DATABASE_URL_SET == 'true'`) will skip until the secret is set — safe default.

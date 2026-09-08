# ATT foundations — consolidation runbook (merge to main + apply migration to prod)

**Agent: Claude Code.** 🔴 First prod change for the attestation feature. Additive/safe; verify at every step, STOP on any surprise. Paste into a Claude Code session in `rolec`.

---

```
TASK — Consolidate the ATT foundations to main and apply the additive migration to prod.
🔴 FIRST prod change for this feature. Additive/safe, but verify at every step and STOP on any surprise.
relopass-dev-queue discipline; you have gh + prod DB access.

WHAT'S LANDING:
- #1995 foundations (AIQ-2103 promotion_policy+advance_review_status migration, AIQ-2108 case_id
  migration, AIQ-2105 _apply_promotion refactor) → #1997 (AIQ-2104 create accepts policy) → #2000
  (AIQ-2106 auto_on_sign). #1998 (AIQ-2109 case snapshot) branches independently off foundations.
- Migrations are additive; prod currently has NONE of the 3 columns (verified 0/0/0); nothing in prod
  reads them yet.
- CRITICAL ORDER: migration to prod BEFORE any merged code deploys. This repo has no apply-on-merge;
  a read that front-runs the column has 500'd prod before.

STEP 1 — APPLY THE MIGRATIONS TO PROD FIRST (before merging code):
- From feat/att-foundations (it holds the migration files). Use the project's STANDARD prod-migration
  mechanism — the one that advances the supabase_migrations ledger. Do NOT hand-run raw ALTERs that
  bypass the ledger; use the same files you validated on disposable PG, via the real runner.
- PRE-CHECK (must hold): information_schema shows 0 of {promotion_policy, advance_review_status,
  case_id} on public.corridor_attestation_requests.
- APPLY.
- POST-CHECK (ALL must hold): the 3 columns present + correctly typed; existing rows read
  promotion_policy='manual', advance_review_status=false, case_id NULL, scope='legal'; the CHECK
  rejects an invalid promotion_policy (test on a throwaway row, then delete it); the case_id index
  exists; the ledger advanced to include these versions.
- If any pre/post check is off → STOP and report. Do not proceed to merges.

STEP 2 — MERGE TO MAIN, IN ORDER: #1995 → #1997 → #2000 → #1998.
- Before each: gh confirms mergeable (no conflicts) and CI green.
- After all four: check out main and run `pytest backend/tests -k attestation` (expect ~65 passed) +
  check_serving_llm_isolation + check_route_auth.

STEP 3 — DEPLOY + VERIFY:
- Let main deploy via the normal path. The deployed code now reads columns that EXIST → no 500.
- Smoke (disposable data only): GET the admin attestation list → 200, unchanged; create a default
  (manual) attestation on a throwaway ZZ_TEST corridor → confirm promotion_policy defaults to 'manual'
  and behaviour is identical to pre-change; tear it down.
- Confirm serving unchanged: requirements_builder still approved-only; attested count across prod
  still 0 (nothing auto-promoted).

STEP 4 — NOTION + REPORT:
- Flip AIQ-2103, 2104, 2105, 2106, 2108, 2109 → Done / Final Validation Result Passed; append the merge
  SHA + "migration applied to prod + verified [date]" to each.
- Note that AIQ-2107, 2110, 2111 now build off main (stack resolved), and that 2110 still needs the
  case create path to accept the policy fields (ATT-3.2 was built independent of ATT-2.2).
- Report: migration pre/post evidence, the 4 merges, main test counts, deploy health, smoke result.

GOVERNANCE: 🔴 first prod change. Additive migration only — no data migration, no serving change.
Migration BEFORE code deploys. Stop on any surprise. Do NOT promote/attest any real row.
```

## After this lands
- The branch stack is gone; **2110 (🔴 auto-release)**, **2107 (tests)**, **2111 (FE)** build off a clean main.
- **2110 prompt will include** the "extend the case create path to accept promotion_policy/advance_review_status" fix (ATT-3.2 was built independent of ATT-2.2), so the case auto-release has the policy it needs.
- Standing items unchanged: verify AIQ-1887 (246 served facts w/ missing evidence), the DB-error-sanitizer card, the `"undefined"` case-row cleanup.
```

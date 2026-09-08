# Audos task brief — F14 follow-up: fix the real over-cap blocker

**Context date:** 2026-07-19 · **Repo:** `rlecomte1929/rolec`
**Prior work:** commit `121403c80b2ae3976259cd360264fc528b28e8e1` on `fix/f14-shared-taxonomy`

---

## 0. Read this before you plan anything

Your taxonomy commit is good work and I want it merged. **But it is not the F14 fix, and it will not make over-cap fire.** Please do not re-run it, extend it, or treat "over-cap now reachable" as achieved. Here is the evidence.

### 0.1 Production data — cases created in the last 30 days

| | Test-drive | Real |
|---|---|---|
| Cases | 87 | 21 |
| Company has a published policy | **12** | 11 |
| Company has **no** policy at all | **75 (86%)** | 10 |
| Cases with a row in `resolved_assignment_policies` | **0** | 3 |

### 0.2 What that means

The over-cap chain has three links:

```
(1) seed/publish a policy  →  (2) resolve it onto the assignment  →  (3) map service key to benefit key
        86% FAILING                    100% FAILING                        ← your commit fixed this
```

Your commit fixed link 3. Links 1 and 2 are both at zero for test-drive. A service→benefit map cannot map onto a cap that was never created or never resolved. **Do not attempt to fix over-cap by changing taxonomy code again — the data isn't there.**

### 0.3 Three specific corrections to the commit's claims

1. **Wrong surface.** The string on the Services page is `"No policy rule for this category"`, emitted by `backend/app/services/employee_services_policy_context.py:154`. Its module docstring says it *"Uses `resolved_assignment_policy` benefits."* **That file is not in your commit.** You fixed `compare_provider_estimates_to_published_caps`, which reads `list_policy_config_benefits(pub["id"])` — published caps, a different source serving a different surface.

2. **A fourth vocabulary survives.** You consolidated `PROVIDER_SERVICE_TO_POLICY_BENEFIT_KEY`, `_SERVICE_BENEFIT_KEYS` and `SERVICE_MODULE_BENEFIT_KEYS`. But `SERVICE_TO_BENEFIT` at `backend/app/services/policy_service_comparison.py:29` (`housing→temporary_housing`, `movers→shipment`, `banks→banking_setup`) is a fourth map, and it is the one the **employee-facing** path uses. "The broken third vocabulary is gone" is not accurate while this one is live.

3. **A competing fix already shipped — this is the blocking issue.** `backend/main.py:9790` carries an **AIQ-1631** comment stating this is *"the actual defect behind the F4↔F14 gap"*, and fixes it by calling `_with_legacy_benefit_key_aliases()` to alias matrix benefits **into** the legacy vocabulary at runtime. Your commit pushes the **canonical** vocabulary the other way. Two fixes, opposite directions, same defect. Merging without reconciling them produces behaviour that depends on which code path serves the request.

---

## 1. Scope of this task

**In scope:** reconcile the two competing fixes; fix the policy seed; make resolution eager; align the employee-facing vocabulary; prove it with data.

**Out of scope — do not touch:**
- The real-customer policy path. Every change must be safe for `is_test=false` cases or explicitly scoped to test-drive.
- Any new taxonomy consolidation work.
- The `insead-2026` campaign — it is live cohort data. Use a `qa-*` campaign.
- Anything requiring a schema migration, unless you stop and report first (see §6).

---

## 2. Step 0 — GATE: reconcile with AIQ-1631 before writing any code

**Goal.** One direction of travel for the vocabulary, not two.

**Do.** Read `backend/main.py:9785–9805` and `_with_legacy_benefit_key_aliases` in `policy_service_comparison.py`. Determine whether your `shared/service_benefit_taxonomy.json` approach and AIQ-1631's runtime aliasing can coexist, or whether one must be removed.

**Deliver — before any further work.** A short written recommendation: (a) which direction wins, (b) what gets deleted, (c) whether your commit needs amending before merge, (d) what breaks if both stay. **Stop and report. Do not implement your recommendation until Romain approves it.**

---

## 3. Step 1 — Fix the silent seed failure (largest population: 86%)

**Goal.** A test-drive company reliably gets a published default policy at provisioning.

**Spec.** `backend/app/routers/test_drive.py::_seed_default_published_policy` (defined ~line 210, called ~line 313) is best-effort and **swallows its exceptions at lines 229–232**. Result: 75 of 87 test-drive cases belong to a company with no published policy, and nothing surfaces the failure.

**Plan.**
1. First, **diagnose — do not fix blind.** Instrument the swallow so the actual exception is captured, provision a fresh test-drive session, and report the real error. It may be a permissions issue, a missing corridor default, or a `publish_draft` precondition. Report what it actually is before changing behaviour.
2. Replace the silent swallow with a structured error log including company id, session id, and the exception. Provisioning may still continue — this is a warning-to-error change, not a fail-the-request change — but the failure must be observable.
3. Fix the underlying cause identified in step 1.
4. Add a provisioning-time assertion or health counter so a future regression is visible without a database query.

**Metrics.** Test-drive companies with a published policy: **14% → ≥ 95%**. Silent seed failures: unbounded → **0**.

**Validation.** `pytest backend/tests/` covering the seed path, including a test that a forced seed failure **raises or logs a structured error** rather than passing silently. Manual: provision 3 fresh test-drive sessions, confirm all 3 have a published policy via the SQL in §5.

---

## 4. Step 2 — Make policy resolution eager

**Goal.** A resolved policy exists as soon as an assignment is created, without anyone opening a screen.

**Spec.** The only write path to `resolved_assignment_policies` is `backend/app/services/policy_resolution.py::resolve_policy_for_assignment` → `upsert_resolved_assignment_policy` (line 677). It is **not** called by `backend/app/services/unified_assignment_creation.py::run_assignment_post_creation_hooks`, which runs only five hooks (contact link, mobility case link, case person, passport doc, welcome message). Resolution currently fires only on a cache-miss read at `backend/main.py:7634`, `:7689`, `:9951`, and `policy_service_comparison.py:323`.

This is why even the 12 test-drive cases **that do have a published policy** still show 0 resolutions.

**Plan.**
1. Add `resolve_policy_for_assignment` as a sixth hook in `run_assignment_post_creation_hooks`.
2. Keep the lazy read path as a fallback — belt and braces, and it preserves behaviour for existing cases.
3. The hook must not fail assignment creation if resolution fails, but it **must** log a structured error. Note that `backend/main.py:9955` currently degrades a resolution failure to a warning; that is how this stayed invisible.
4. Confirm this is safe for real customers — resolution already runs for them lazily, so making it eager should only change *when*, not *what*.

**Metrics.** Test-drive cases with a resolution: **0 of 87 → ≥ 95%**. Time from assignment creation to resolved row: unbounded → **< 2s**.

**Validation.** A new test asserting a resolved row exists immediately after `create_assignment_with_contact_and_invites` **with no intervening read**. Manual: provision → HR assigns → query `resolved_assignment_policies` **without opening any policy screen** → row present.

---

## 5. Step 3 — Verify with data, not with assertion

Run this and paste the raw output in your report. Do not report success without it.

```sql
WITH pub AS (
  SELECT pc.company_id::text AS cid
  FROM policy_configs pc
  JOIN policy_config_versions pcv ON pcv.policy_config_id::text = pc.id::text
  WHERE pcv.status = 'published'
  GROUP BY 1
)
SELECT co.is_test,
       count(*)                                    AS cases,
       count(*) FILTER (WHERE pub.cid IS NOT NULL) AS company_has_published_policy,
       count(*) FILTER (WHERE pub.cid IS NULL)     AS company_missing_policy,
       count(rap.id)                               AS cases_with_resolution
FROM relocation_cases rc
JOIN companies co ON co.id::text = rc.company_id::text
LEFT JOIN pub ON pub.cid = co.id::text
LEFT JOIN resolved_assignment_policies rap ON rap.case_id::text = rc.id::text
WHERE rc.created_at::timestamptz > now() - interval '7 days'
GROUP BY co.is_test;
```

Then run **RUN 003 Segment B step B16** (`docs/audos-test-drive-e2e-scenario-run003.md`), pinned: `?campaign=qa-f14-verify&corridor=FR_NO`. B16 must move from BLOCKED to a Housing card showing a real cap comparison. Only then attempt B17 (over-cap selection) and Segment C (Policy Exception + HR notification).

---

## 6. Hard repo gates — violating any of these ships an incident

1. **Routers must be registered in BOTH `backend/main.py` AND `backend/app/main.py`.** Render boots `uvicorn backend.main:app`; registering only in the modular app returns **405 in production**. This has caused three incidents. Verify with:
   `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<prefix>' in r.path))"`
2. **Any new `public` table** needs `ENABLE ROW LEVEL SECURITY` + at least one policy + `REVOKE ALL ... FROM anon`. Non-negotiable — this caused SEC-002 (8 tables, GDPR-scope PII).
3. **Never apply a migration to production** and never insert into `supabase_migrations.schema_migrations`. Commit the file; the operator applies out-of-band. If this task turns out to need a migration, **stop and report** — it becomes a 🔴 Red human-gated task.
4. **Never log raw user input** — use `safe_log_text()` from `pii_masker.py`. Your new error logging must not leak PII.
5. Run `cd frontend && npx tsc --noEmit` (strict) and `cd backend && pytest` before reporting done.

---

## 7. Working rules

- **Do not work around blockers.** If a token lacks scope or a step is gated, stop and report — as you correctly did with the PR 403. That was the right call.
- **Do not claim a fix works without the §5 query output.** Three prior diagnoses of this defect were confidently wrong; evidence is the only currency here.
- **Branch:** off `main` unless you have a stated reason. Note your prior branch was cut from `fix/td-qa-services-batch-0719` — confirm whether that was intended, since the PR would target that branch rather than `main`.
- **PR scope:** the fine-grained PAT needs "Pull requests: Read and write". If it still 403s, stop and report.
- Autonomy tier: 🟡 **Yellow** for Steps 1–2 (no schema change, no auth boundary). Escalates to 🔴 **Red** if a migration is required.

---

## 8. Report format

```
STEP 0 — AIQ-1631 reconciliation
  Recommendation: ____  |  What gets deleted: ____  |  Amend the commit? ____
  [STOPPED FOR APPROVAL]

STEP 1 — Seed failure
  Actual exception found: ____
  Root cause: ____
  Fix: ____  |  Commit SHA: ____

STEP 2 — Eager resolution
  Hook added: ____  |  Commit SHA: ____
  Real-customer safety argument: ____

STEP 3 — Verification
  [paste raw SQL output]
  RUN 003 B16: BLOCKED → ____
  RUN 003 B17: ____
  RUN 003 Segment C (Policy Exception + HR notification): ____

BLOCKED / NOT DONE: ____
```

**Sequencing note:** Step 0 is a hard gate — report and wait. Steps 1 and 2 can proceed in the same PR once Step 0 is approved. Step 1 first: it is 86% of the population and probably a small change once the swallowed exception is visible.

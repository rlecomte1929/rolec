# Step H RESULT — Conjoint analysis on benefit preferences

_Run: run-20260530-174625 | Branch: audit/parker-step-H-conjoint_

## Summary
Shipped a backend choice-based-conjoint (CBC) micro-service for stated-preference benefit
studies — the headline commercial artefact ("your employees prefer bundle X over Y by Z%").
HR admins create a study (attributes → levels); employees are served balanced choice sets
and pick a preferred benefit bundle; the service fits an aggregate effects-coded
conditional-logit model via `scipy.optimize` to estimate per-attribute-level part-worths,
then simulates market share and recommends a budget-constrained utility-maximising bundle.
The fit's learned utilities are bridged best-effort into Step B's `benefit_priors`
(`source='conjoint'`) so the optimizer can consume real preference data once B merges. Both
UIs (employee choice flow, HR results page) are deferred to a follow-up prompt per the
UI-reuse mandate; this PR is backend + service + API + migration only.

## Files changed
```
backend/app/main.py                             |   2 +
 backend/app/routers/conjoint.py                 | 201 +++++++++++++++
 backend/app/services/conjoint_repo.py           | 305 ++++++++++++++++++++++
 backend/app/services/conjoint_service.py        | 322 ++++++++++++++++++++++++
 backend/requirements.txt                        |   4 +
 backend/tests/test_conjoint_router.py           | 179 +++++++++++++
 backend/tests/test_conjoint_service.py          | 138 ++++++++++
 supabase/migrations/20260601090000_conjoint.sql | 132 ++++++++++
 8 files changed, 1283 insertions(+)
```
_(diff stat against the PR base `feature/sec-004-rate-limit-coverage`, not `main` — this
step stacks on the pre-merge pipeline base like D–G.)_

## Tests added
- `backend/tests/test_conjoint_service.py` — fits an effects-coded conditional logit on a
  synthetic Sawtooth-style dataset generated from known part-worths via Gumbel-max MNL
  sampling (no licensed data). Asserts: convergence + correct `n_obs`; McFadden R² clears
  the excellent-fit floor (≥0.25); dominant-attribute ordering recovered; effects coding
  sums to zero per attribute; empty-dataset yields a zeroed fit (never raises); market-share
  softmax ranks/normalises; budget-constrained recommender honours budget + hard
  constraints and returns `None` when nothing is affordable; `design_study` shape +
  within-set distinctness. `importorskip` numpy/scipy so CI without the numerical stack
  skips cleanly rather than failing.
- `backend/tests/test_conjoint_router.py` — drives the router over in-memory SQLite
  (monkeypatched `SessionLocal`) exercising the real auth deps. Asserts: non-HR create →
  403; wrong-company HR → 403; multi-level attribute validation → 422; cross-company study
  access → 404 (admin bypasses scope but the study still isn't in the other company);
  results 404 before fit; respondent submission idempotency (two identical posts → one
  persisted row, second `deduplicated:true`); fit persists a results row and HR results
  never leak `respondent_user_id`.

## Test result
- pytest (conjoint suite): **14 passed** (`backend/tests/test_conjoint_service.py` +
  `backend/tests/test_conjoint_router.py`, `0.94s`).
- pytest (full `backend/tests`, `--continue-on-collection-errors`): **137 failed, 1815
  passed, 69 skipped, 16 errors**. Verified against a detached worktree at the base commit
  `81d98bc8`: baseline is **138 failed, 1800 passed, 69 skipped, 16 errors**. So this branch
  introduces **zero new failures or errors** and adds the +15 passing conjoint cases (one
  baseline failure also flips green). The 137 pre-existing failures + 16 collection errors
  are the repo's known-red local baseline — DB-dependent tests and legacy `services.*`
  un-migrated import paths (AUDIT-A9.3), unrelated to this step.
- tsc: **pass** (`cd frontend && npx tsc --noEmit`, no frontend changes in this step).

## Migration applied?
- File: `supabase/migrations/20260601090000_conjoint.sql` — **NOT applied.** Per repo
  workflow, migrations are left for human review and applied via the Supabase MCP
  `apply_migration` (`supabase db push` is blocked by ~95-row history drift).
- RLS posture (per new table — CLAUDE.md hard gate satisfied for all three):
  - `conjoint_studies`: RLS **enabled**. Policy `conjoint_studies_company_scoped` (FOR ALL,
    authenticated) — `company_id::text in (select public.hr_company_ids()) or
    public.is_admin()`; `service_role` catch-all. `REVOKE ALL ... FROM anon` ✓.
  - `conjoint_responses`: RLS **enabled**. `conjoint_responses_own` (respondent scoped to
    own rows via `auth.uid()`), `conjoint_responses_company_read` (HR/admin SELECT only, to
    fit — aggregates only ever leave the API), `service_role` catch-all. `REVOKE ALL ...
    FROM anon` ✓.
  - `conjoint_results`: RLS **enabled**. `conjoint_results_company_scoped` (FOR ALL via the
    parent study's company), `service_role` catch-all. `REVOKE ALL ... FROM anon` ✓.

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| POST | /api/hr/{company_id}/conjoint/studies | require_admin_or_hr + path-company-vs-caller (admin bypass) | backend/app/routers/conjoint.py |
| GET | /api/hr/{company_id}/conjoint/studies/{study_id}/next-choice-set | get_current_user (any authenticated respondent) | backend/app/routers/conjoint.py |
| POST | /api/hr/{company_id}/conjoint/studies/{study_id}/responses | get_current_user (respondent; scoped to own rows) | backend/app/routers/conjoint.py |
| POST | /api/hr/{company_id}/conjoint/studies/{study_id}/fit | require_admin_or_hr + path-company-vs-caller (admin bypass) | backend/app/routers/conjoint.py |
| GET | /api/hr/{company_id}/conjoint/studies/{study_id}/results | require_admin_or_hr + path-company-vs-caller (admin bypass) | backend/app/routers/conjoint.py |

The fit endpoint computes part-worths, persists a `conjoint_results` row, and best-effort
calls `push_to_benefit_priors`. Results are aggregate-only — `respondent_user_id` is never
returned to HR.

## New tables / schema changes
- `conjoint_studies` — `id uuid pk default gen_random_uuid()`, `company_id uuid not null →
  companies(id) on delete cascade`, `name text`, `status text default 'draft'`,
  `attributes_json jsonb`, `n_responses_target int default 100`, `opened_at timestamptz`,
  `closed_at timestamptz`, `created_at timestamptz default now()`. Index on `(company_id)`.
- `conjoint_responses` — `id uuid pk`, `study_id uuid not null → conjoint_studies(id) on
  delete cascade`, `respondent_user_id uuid`, `choice_set_json jsonb`, `choice_set_hash
  text`, `chosen_index int`, `responded_at timestamptz default now()`. Index on
  `(study_id)`; **unique** `(study_id, respondent_user_id, choice_set_hash)` for idempotent
  submit.
- `conjoint_results` — `id uuid pk`, `study_id uuid not null → conjoint_studies(id) on
  delete cascade`, `part_worths_json jsonb`, `fit_quality_json jsonb`, `computed_at
  timestamptz default now()`. Index on `(study_id)`.

## Configuration / env vars added
- None. (No new env vars. `RELOPASS_DISABLE_RATE_LIMITS=1` is the existing test bypass.)
- New dependency: `statsmodels>=0.14` added to `backend/requirements.txt` to transitively
  pin the numpy/scipy/pandas numerical stack the fit lazy-imports. See deviation #1.

## UI changes summary
- New routes added: none (backend only).
- New components added: none.
- Existing antigravity components reused: none (no frontend work this step).
- UI-PROPOSAL.md status: **deferred to follow-up prompt** — the employee choice flow and HR
  results page are deferred to `prompts/followups/H-frontend.md` per the UI-reuse mandate
  (explicit in the task body, STAGE 1.5).

## Deviations from the original audit prompt
1. **Fit uses a transparent scipy conditional-logit MLE, not statsmodels/sklearn.** CBC
   requires a conditional logit over the alternatives *within each choice set*, which
   statsmodels has no first-class CBC helper for, and plain `sklearn.LogisticRegression` is
   the wrong model. `statsmodels>=0.14` is still added to `requirements.txt` per deliverable
   #1 (it transitively pins numpy/scipy/pandas for prod); the fit itself uses
   `scipy.optimize.minimize(jac=True, method="BFGS")`. numpy/scipy are lazy-imported inside
   `fit_conjoint` so the module imports cleanly without them (tests `importorskip`).
2. **`push_to_benefit_priors` is best-effort / no-op when `benefit_priors` is absent.** Step
   B (which owns the table) is unmerged, so the table isn't in this branch's tree. The
   bridge writes `(company_id, category=attribute, attr_key=level,
   expected_satisfaction=part-worth, source='conjoint')` rows when present and logs a TODO +
   returns 0 when absent. Column names match B's schema exactly so it activates once both
   merge.
3. **Portable text UUID ids on the repo/test path** (Python-generated `uuid4` strings) so
   persistence works identically on SQLite; the migration still uses
   `uuid`/`gen_random_uuid()` for Postgres.
4. **RLS verified by inspection, not an automated two-company SQLite test** (SQLite can't
   enforce Postgres RLS). The app-layer path-company-vs-caller check is unit-tested instead;
   the migration RLS is reviewed against the CLAUDE.md hard-gate checklist.
5. **Frontend deferred** to `prompts/followups/H-frontend.md` per the UI-reuse mandate.

## What downstream steps will need from this step
- **Step B (benefit-optimizer)**: once B's `benefit_priors` migration is applied and both
  branches merge, the conjoint fit automatically upserts learned part-worths via
  `conjoint_repo.push_to_benefit_priors(session, company_id=..., part_worths=...)` as
  `source='conjoint'`, keyed by `(company_id, category, attr_key)` = `(company_id,
  attribute, level)`. No code change needed in B — it reads the same rows via
  `benefit_priors_repo.load_company_priors`. The `expected_satisfaction` column receives the
  raw part-worth (effects-coded, sums to zero per attribute); B should treat magnitude as
  relative preference, not an absolute satisfaction score.
- **Frontend follow-up (`prompts/followups/H-frontend.md`)**: the API contract is the 5
  routes above. Employee flow polls `GET …/next-choice-set` (returns
  `{done, choice_set:{index, choice_set_hash, alternatives:[{attr:level,…}]}}`) and posts
  `{alternatives, chosen_index}` to `…/responses`. HR results page reads `GET …/results`
  (`{part_worths:{attr:{level:float}}, fit_quality:{log_likelihood, mcfadden_r2, n_obs,
  converged}, computed_at}`). `respondent_user_id` is never in any HR-facing payload.
- **Design constants**: every respondent sees the same balanced design —
  `conjoint_repo.CHOICE_SETS_PER_STUDY = 10`, `N_ALTS = 3`, seed derived deterministically
  from the study id. Changing these changes the choice-set hashes (and thus idempotency
  keys), so treat them as part of the study's identity.

## Known gaps / follow-ups
- **Employee + HR UI deferred** to `prompts/followups/H-frontend.md` (above). Map to a
  Notion AI Work Queue follow-up task when scheduled.
- **`benefit_priors` bridge is dormant** until Step B merges + its migration applies; a
  one-line re-fit (or a backfill of existing studies) may be wanted once B lands so the
  optimizer picks up already-collected preference data. (Notion AI Work Queue follow-up.)
- **Migration not applied** — left for human MCP `apply_migration` review (3 new public
  tables; RLS hard-gate satisfied).
- **Full local suite is known-red** (137 pre-existing failures / 16 collection errors from
  DB-dependent + legacy `services.*` import-path tests, AUDIT-A9.3). Out of scope for this
  step; this branch adds no new failures.

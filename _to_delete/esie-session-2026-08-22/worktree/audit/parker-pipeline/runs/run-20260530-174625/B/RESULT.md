# Step B RESULT — Benefit-mix portfolio optimizer (Markowitz-style)

_Run: run-20260530-174625 | Branch: audit/parker-step-B-benefit-optimizer_

## Summary

Shipped a backend benefit-mix optimizer: given an HR company's relocation budget and
a set of candidate benefits, it returns the binary mix that maximizes a Markowitz-style
utility (`Σ expected_satisfaction − λ·Σ variance`) subject to budget, mandatory-benefit,
per-category-cap, and minimum-coverage constraints. The selection is a small
mixed-integer linear program solved with PuLP's bundled CBC backend; the solver is
imported lazily so the rest of the backend never requires it. Beyond the optimum, the
engine returns **shadow prices** ("each extra €1000 of budget / category cap yields +X
satisfaction") computed by finite-difference sensitivity — the commercial artefact HR
buyers want. A canary-free, company-scoped route
(`POST /api/hr/{company_id}/optimize-benefit-mix`) serves it behind HR/admin auth, and a
new `benefit_priors` table (admin-seeded, RLS company-scoped) supplies satisfaction /
variance priors when a request omits them.

## Files changed

```
 backend/app/main.py                                |   3 +
 backend/app/routers/benefit_optimizer.py           | 125 ++++++++
 backend/app/services/benefit_optimizer.py          | 318 +++++++++++++++++++++
 backend/app/services/benefit_priors_repo.py        |  37 +++
 backend/requirements.txt                           |   6 +
 backend/tests/test_benefit_optimizer.py            | 138 +++++++++
 backend/tests/test_benefit_optimizer_router.py     |  79 +++++
 supabase/migrations/20260601030000_benefit_optimizer.sql |  72 +++++
 8 files changed, 778 insertions(+)
```
(diff vs pipeline base SHA `81d98bc8`, not `main` — see "Branch base" below.)

## Tests added

- `backend/tests/test_benefit_optimizer.py` — guarded by `pytest.importorskip("pulp")`:
  - `test_hand_solved_three_benefit_optimum` — 3-benefit toy (λ=0.1); asserts exact
    selected set `["a","b"]`, utility `20.7`, cost `7000` (hand-computed).
  - `test_default_variance_prior` — `default_variance(e) == 0.25·e²`; candidate with no
    variance uses the prior.
  - `test_mandatory_exceeds_budget` — mandatory set over budget → `feasible=False`,
    `infeasibility_reason="mandatory_exceeds_budget"`.
  - `test_category_cap_forces_second_best` — a binding housing cap forbids the best item
    so the solver returns the second-best in that category.
  - `test_budget_shadow_price_monotonic` — budget shadow price is non-increasing as
    budget grows (diminishing returns), and strictly decreasing on the fixture.
  - `test_deterministic_output` — same request solved twice → identical serialized JSON.
  - `test_lambda_out_of_bounds_raises`, `test_unknown_mandatory_id_raises` — input
    validation → `OptimizationError`.
- `backend/tests/test_benefit_optimizer_router.py` — `importorskip("pulp")`; minimal
  FastAPI app mounting only the router, auth deps overridden:
  - `test_optimize_happy_path_200` — HR admin of the path company → 200 with portfolio +
    shadow prices.
  - `test_non_hr_admin_caller_403` — employee role rejected by `require_admin_or_hr`.
  - `test_wrong_company_403` — HR admin of another company → 403.
  - `test_malformed_body_422` — missing `budget` → 422.

## Test result

- New suites: **12 passed in ~2s** (`.venv` with PuLP installed).
- CI deterministic subset (`test_admin_form_templates_router`, `test_trigger_engine`,
  `test_case_dossier_forms`) + the two new suites: **67 passed**.
- Import-safety: the service and router import cleanly **without** PuLP (verified against
  `backend/.venv`, which lacks it); the test suites **skip cleanly** there
  (`2 skipped`). So the bare-`pytest` verify step won't error on a solver-less machine.
- Route-auth audit (`scripts/check_route_auth.py`): **passed** (12 GET routes scanned;
  the new route is POST, so not in scope, and adds no unguarded GET).
- `tsc --noEmit`: **passed (exit 0)** — no frontend changes.
- Pre-existing full-suite collection errors (the 10 `services.<x>` `ModuleNotFoundError`
  from the in-progress `backend/services/` → `backend/app/services/` migration,
  AUDIT-A9.3) are unrelated; this step adds **zero** new collection errors.

> Note: PuLP 3.x emits a `DeprecationWarning` about `LpVariable(...)` construction (API
> changes in PuLP 4.0). Harmless for now; the requirement is pinned `pulp>=2.7,<4` so the
> 4.0 break can't reach production until the call site is updated.

## Migration applied?

- File: `supabase/migrations/20260601030000_benefit_optimizer.sql`
- **Not yet applied** to remote (left for review → merge → apply via MCP
  `apply_migration`; per repo memory `supabase db push` is blocked by history drift).
- RLS posture — table `benefit_priors`:
  - RLS enabled: **yes** (`enable row level security`).
  - Policies: `benefit_priors_company_scoped` (ALL, `authenticated`, USING/WITH CHECK
    `company_id::text in (select public.hr_company_ids()) or public.is_admin()`);
    `benefit_priors_service_all` (ALL, `service_role`).
  - `REVOKE ALL ON public.benefit_priors FROM anon`: **yes**.
  - Idempotent guards (`if not exists`, `drop policy if exists`) + rollback block.

## New routes

| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| POST | /api/hr/{company_id}/optimize-benefit-mix | `require_admin_or_hr` (HR or admin) + path `company_id` must equal the caller's company (admins bypass) → 403 otherwise | `backend/app/routers/benefit_optimizer.py` |

Request: `budget`, `candidates[]` (`id, category, cost_per_employee,
expected_satisfaction?, variance?, mandatory?`), `mandatory_ids[]`, `category_caps{}`,
`lambda_risk` (default 0.3, bounds [0,5]), `min_coverage` (default 0). Response:
`feasible`, `infeasibility_reason?`, `selected[]`, `achieved_utility`, `total_cost`,
`shadow_prices{budget_per_1000, category_caps{}, min_coverage}`, `lambda_risk`.

## New tables / schema changes

- `public.benefit_priors` — `id uuid pk default gen_random_uuid()`,
  `company_id uuid not null → companies(id) on delete cascade`, `category text`,
  `attr_key text`, `expected_satisfaction numeric not null`, `variance numeric`,
  `source text default 'admin_seed'`, `updated_at timestamptz default now()`,
  `updated_by uuid → profiles(id) on delete set null`. Unique
  `(company_id, category, attr_key)`; index on `(company_id)`.

## Configuration / env vars added

- None. (No feature flag — the route is auth-gated, read-style, and has no destructive
  side effects; nothing to dark-ship.)

## UI changes summary

- New routes added: none (backend + API only).
- New components added: none.
- Existing antigravity components reused: n/a.
- UI-PROPOSAL.md status: not required (UI impact: None — HR optimizer panel is a later
  task).

## Deviations from the original audit prompt

1. **Solver = PuLP+CBC, not cvxpy.** The benefit selection is a small MILP; PuLP bundles
   CBC (one small native binary) and is far lighter at container build time than cvxpy's
   scs/osqp/ecos chain. CLAUDE.md flags build weight because Render auto-deploys `main`.
2. **Shadow prices via finite-difference sensitivity, not literal LP duals.** A MILP has
   no well-defined LP dual (and neither solver returns meaningful duals for integer
   programs). Re-solving at a relaxed bound gives the economically correct marginal
   utility the "+X per €1000" framing describes, and it is deterministic and directly
   testable (monotonic in budget).
3. **No `v_benefit_candidates_per_company` view.** The task-body concrete deliverables
   list only the `benefit_priors` table (the view was in the older section-4 sketch).
   Candidates arrive in the request; missing satisfaction/variance are filled from
   `benefit_priors`, then from the default-variance prior. View deferred to a follow-up.
4. **`min_coverage` constraint + shadow price added** — present in the task-body
   `optimize(...)` signature though not in the section-4 sketch.
5. **Step A duration weighting not wired** — kept B independent of the PREDICTIONS_ENABLED
   canary (optional per the prompt). Listed as a follow-up.

## Branch base (important for the PR)

This branch was cut from the pipeline base SHA `81d98bc8` (tip of
`feature/sec-004-rate-limit-coverage`), **not** from step A's branch — step B is
independent of A, so it does not stack on A's commits. The PR targets
**`feature/sec-004-rate-limit-coverage`** so its diff shows only the Parker-B changes.

## What downstream steps will need from this step

- **Optimizer entry point:** `backend.app.services.benefit_optimizer.optimize(budget,
  candidates, mandatory_ids, category_caps, lambda_risk, min_coverage) ->
  OptimizationResult`. `candidates` are `BenefitCandidate(id, category,
  cost_per_employee, expected_satisfaction, variance?, mandatory?, hard_constraints?)`.
  Pure function, no DB — reusable directly by any later step (e.g. step H conjoint can
  feed learned satisfaction priors straight in).
- **Priors table:** `public.benefit_priors(company_id, category, attr_key,
  expected_satisfaction, variance, source, updated_at, updated_by)` is the standard place
  for admin-seeded / learned benefit priors. Step H (conjoint) should write its learned
  utilities here with `source='conjoint'`, keyed by `(company_id, category, attr_key)`.
  Read them via `benefit_priors_repo.load_company_priors(session, company_id)`.
- **Default-variance prior:** when no variance is known, use
  `benefit_optimizer.default_variance(expected) = 0.25·expected²` (CV 0.5).
- **Route + auth pattern:** company-scoped HR routes reuse `require_admin_or_hr` +
  `get_org_id_for_hr_user` and an explicit path-vs-caller company check (admin bypass);
  RLS reuses `public.hr_company_ids()` + `public.is_admin()`.

## Known gaps / follow-ups

- **`benefit_priors` is not seeded** and the migration is not applied — no admin UI/route
  to CRUD priors yet. Requests must currently pass `expected_satisfaction` inline, or the
  table must be seeded out-of-band, until a seeding route exists. (Maps to a future AI
  Work Queue task.)
- **`v_benefit_candidates_per_company` aggregation view** (NPS/engagement-derived
  satisfaction) deferred — candidates and priors are admin-supplied for now.
- **`<BenefitOptimizerPanel>` HR-facing builder UI** is intentionally out of scope
  (separate later prompt).
- **Step A duration-weighting** of benefit relevance not wired (optional dependency).
- **`hard_constraints` on `BenefitCandidate`** is carried but not yet interpreted by the
  solver (placeholder for per-benefit eligibility rules from `hr_policy_resolver`).

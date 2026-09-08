# Step B PLAN — Benefit-mix portfolio optimizer (Markowitz-style)

_Run: run-20260530-174625 | Branch: audit/parker-step-B-benefit-optimizer_

## Task understanding

Build a backend optimization engine that, given an HR company's relocation budget and
a set of candidate benefits (each with a per-employee cost, an expected-satisfaction
prior, and a variance prior), returns the benefit mix that maximizes a Markowitz-style
utility `Σ expected_satisfaction − λ·Σ variance` subject to: a total budget cap, a
mandatory-benefit set that must be included, per-category spend caps, and a minimum
number of selected benefits (coverage). The selection is binary (a benefit is either in
the mix or not), so this is a small mixed-integer linear program. Beyond the optimum,
the engine returns **shadow prices** — the marginal utility gained per extra €1000 of
budget and per relaxed category-cap / coverage constraint — which is the commercial
"where should I spend the next euro" artefact HR buyers want. Determinism is a hard
requirement: same request → identical response bytes.

## Upstream alignment

PREREQUISITES.md: **none — step B is independent.** Step A (`predict_remaining_duration`)
is an optional "nice to have" for weighting benefit relevance by case duration; I am
**not** wiring it in this step (keeps B self-contained and avoids a soft dep on the
PREDICTIONS_ENABLED canary). Noted as a follow-up in RESULT.md.

Grounding against the actual codebase (not the section-4 sketch):
- **Auth:** `backend/app/auth_deps.py` provides `require_admin_or_hr` (admin or HR) and
  `get_org_id_for_hr_user` (resolves the caller's `company_id`). The route reuses these
  and adds an explicit path-vs-caller company check so an HR admin of company X cannot
  optimize for company Y; platform admins bypass the check.
- **Company-scoped RLS:** `supabase/migrations/20260531010000_rls_policy_hr_domain.sql`
  established `public.hr_company_ids()` (SECURITY DEFINER, returns the set of company_ids
  as text the caller is an HR member of) and the canonical company-scoped policy shape
  (`company_id::text in (select public.hr_company_ids()) or public.is_admin()`) plus a
  `service_role` ALL policy and `REVOKE ALL ... FROM anon`. `benefit_priors` reuses this
  exactly.
- **DB session in routers:** app-layer routers open `with SessionLocal() as session:`
  (see `backend/app/routers/predictions.py`). Same pattern here.
- **FK targets (verified in migrations):** `public.companies(id)`, `public.profiles(id)`.

## Solver choice — PuLP + CBC (not cvxpy)

**Decision: `pulp>=2.7` with the bundled CBC backend.** Rationale:
- The problem is a small **MILP** (binary selection per candidate). PuLP wraps the
  bundled CBC binary — pure-python + one small native binary — and is far lighter at
  container build time than cvxpy (which drags in scs/osqp/ecos/numpy build chains).
  CLAUDE.md flags build weight because Render auto-deploys `main`.
- CBC with `threads=1` and a deterministic variable ordering is reproducible.
- **Shadow prices via finite differences, not LP duals.** A MILP has no well-defined LP
  dual, and neither cvxpy nor PuLP returns meaningful duals for integer programs. The
  economically correct shadow price for an integer program is the *sensitivity* of the
  achieved optimum to a one-unit relaxation of the constraint — exactly the
  "+X satisfaction per extra €1000" framing the prompt asks for. I re-solve at
  `budget ± step` (and at category-cap+1 / min_coverage−1) and report the finite
  difference. This is deterministic and directly testable (monotonic-in-budget).

This deviation (finite-difference sensitivity vs literal "dual variables") is recorded
in RESULT.md.

## File-by-file change list

- `backend/requirements.txt` — add `pulp>=2.7` (with a comment explaining the cvxpy
  trade-off).
- `backend/app/services/benefit_optimizer.py` — **new.** Dataclasses
  `BenefitCandidate` and `OptimizationResult`; `optimize(...)`; finite-difference
  shadow-price helper; a `default_variance(expected)` prior helper
  (`0.25·expected²`). No DB access — pure function over inputs (testable in isolation).
- `backend/app/services/benefit_priors_repo.py` — **new, small.** Read priors for a
  company from `benefit_priors` (`load_company_priors(session, company_id)`), used by
  the router to enrich candidates that omit satisfaction/variance. Kept separate from
  the pure optimizer so the optimizer stays DB-free and unit-testable.
- `backend/app/routers/benefit_optimizer.py` — **new.** `POST
  /api/hr/{company_id}/optimize-benefit-mix`; Pydantic request/response models;
  `require_admin_or_hr` + path-company check; builds `BenefitCandidate`s from the body
  (filling missing satisfaction/variance from priors, then the default-variance prior),
  calls `optimize(...)`, returns portfolio + utility + shadow prices.
- `backend/app/main.py` — register the new router via `include_router`.
- `supabase/migrations/20260601030000_benefit_optimizer.sql` — **new.** `benefit_priors`
  table + RLS.
- `backend/tests/test_benefit_optimizer.py` — **new.** Pure-service tests.
- `backend/tests/test_benefit_optimizer_router.py` — **new.** Route tests via FastAPI
  `TestClient` with dependency overrides.

## New tables and migration plan

`public.benefit_priors`:

| column | type | notes |
|--------|------|-------|
| id | uuid pk default gen_random_uuid() | |
| company_id | uuid not null | FK → public.companies(id) on delete cascade |
| category | text not null | |
| attr_key | text not null | benefit identifier within the category |
| expected_satisfaction | numeric not null | prior mean satisfaction |
| variance | numeric not null | prior variance (noise on satisfaction) |
| source | text | provenance: 'admin_seed' / 'nps' / 'engagement' |
| updated_at | timestamptz default now() | |
| updated_by | uuid | FK → public.profiles(id) on delete set null |

- Unique `(company_id, category, attr_key)`.
- Index on `(company_id)` for the per-company prior fetch.
- **RLS strategy:** `ENABLE ROW LEVEL SECURITY`. Policy `benefit_priors_company_scoped`
  (`FOR ALL TO authenticated USING (company_id::text in (select public.hr_company_ids())
  or public.is_admin()) WITH CHECK (same)`) — HR members read/write only their own
  company's priors; admins carve-out. Policy `benefit_priors_service_all`
  (`FOR ALL TO service_role`). `REVOKE ALL ON public.benefit_priors FROM anon`.
- Idempotent guards (`if not exists`, `drop policy if exists`) and a rollback block at
  the bottom, matching the in-repo migration style.

## New routes

| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| POST | /api/hr/{company_id}/optimize-benefit-mix | `require_admin_or_hr` + path company_id must equal caller's company (admins bypass) → 403 otherwise | backend/app/routers/benefit_optimizer.py |

Request body: `budget`, `candidates[]` (`id, category, cost_per_employee,
expected_satisfaction?, variance?, mandatory?`), `mandatory_ids[]`, `category_caps{}`,
`lambda_risk` (default 0.3, bounds [0,5]), `min_coverage` (default 0). Response:
`feasible`, `infeasibility_reason?`, `selected[]`, `achieved_utility`, `total_cost`,
`shadow_prices{ budget_per_1000, category_caps{}, min_coverage }`, `lambda_risk`.

## Tests

`backend/tests/test_benefit_optimizer.py` (pure service):
- **Happy / hand-solved 3-benefit toy** — fixed costs/satisfaction/variance + budget;
  assert the exact selected set, utility, and total cost (hand-computed).
- **Edge: mandatory exceeds budget** → `feasible=False`,
  `infeasibility_reason="mandatory_exceeds_budget"`.
- **Failure mode: category cap binds** → with a cap that forces dropping the best item
  in a category, the solver returns the second-best in that category.
- **Shadow prices monotonic in budget** — budget shadow price is non-increasing as
  budget grows (diminishing returns), and the fixture is built so it holds cleanly.
- **Determinism** — same request solved twice → byte-identical serialized result.
- **Default-variance prior** — `default_variance(e) == 0.25*e*e`.

`backend/tests/test_benefit_optimizer_router.py` (route):
- **200 happy path** with mocked candidates (priors repo overridden) → portfolio +
  shadow prices in body.
- **403** for a non-HR-admin caller (employee role) and for an HR admin whose company ≠
  path company.
- **422** for a malformed body (missing `budget`).

## Risks and unknowns

- **CBC determinism** — mitigated by `threads=1`, fixed candidate ordering (sort by id),
  and rounding numeric outputs to fixed precision before serialization.
- **PuLP/CBC availability in CI** — PuLP ships CBC as a wheel dependency, so it installs
  with `requirements.txt`. To keep the bare-`pytest` verify step green on machines that
  haven't installed it, the test module uses `pytest.importorskip("pulp")` and the
  service imports PuLP lazily inside `optimize()` (module import never requires it),
  mirroring step A's lifelines pattern.
- **Infeasibility vs unboundedness** — explicit feasibility checks (mandatory cost ≤
  budget, caps ≥ mandatory spend per category) before/after the solve, returning a
  structured `feasible=False` rather than raising.
- **Float comparison in the hand-solved test** — assert utility with `pytest.approx`.

## Deviations from the original audit prompt

1. **Solver = PuLP+CBC, not cvxpy** — lighter container build for a small MILP (above).
2. **Shadow prices via finite-difference sensitivity, not literal LP duals** — MILPs
   have no meaningful LP dual; finite differences give the economically correct,
   deterministic marginal utility the prompt's "+X per €1000" framing describes.
3. **No `v_benefit_candidates_per_company` view** — the task-body concrete deliverables
   list only the `benefit_priors` table (the view was in the older section-4 sketch).
   Candidates arrive in the request; missing satisfaction/variance are filled from
   `benefit_priors`, then from the default-variance prior. View deferred to a follow-up.
4. **`min_coverage` constraint added** — present in the task-body signature
   (`optimize(..., min_coverage)`) though not in the section-4 sketch. Implemented as a
   "≥ N benefits selected" constraint with its own shadow price.
5. **Step A duration weighting not wired** — kept B independent (optional per prompt).

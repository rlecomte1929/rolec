## Task body — step B

**UI impact:** None. Backend + API only. The HR-facing optimizer panel is a separate,
later task and not in scope here.

Build a constrained-optimization engine that, given an HR company's relocation
budget and a set of candidate benefits, returns the benefit mix that maximizes a
Markowitz-style utility (expected satisfaction − λ × variance) subject to budget,
mandatory-benefit, per-category-cap, and minimum-coverage constraints. This is the
commercial artefact HR buyers want most.

### Prerequisites from prior steps
_None — B is independent of A._

If step A's RESULT.md exists you may optionally use its `predict_remaining_duration`
to weight benefit relevance by case duration. Treat this as a "nice to have", not a
hard dependency. Read `audit/parker-pipeline/runs/<RUN_ID>/A/RESULT.md` if present.

### Source material
- `backend/app/services/hr_policy_resolver.py` — current benefit eligibility logic.
- `backend/app/services/requirement_evaluation_service.py` — current requirement
  evaluation pipeline.
- `backend/app/recommendations/engine.py` — existing scoring pattern.
- `audit/parker-framework-audit.md` section 4, Prompt B.

### Concrete deliverables

1. Add `cvxpy>=1.4` to `backend/requirements.txt`. If `cvxpy` is too heavy at
   container build time, fall back to `pulp>=2.7`. Document the choice in
   `audit/parker-pipeline/runs/<RUN_ID>/B/PLAN.md`.
2. Create `backend/app/services/benefit_optimizer.py`:
   - Dataclass `BenefitCandidate(id, category, cost_per_employee, expected_satisfaction,
     variance, mandatory, hard_constraints)`.
   - `optimize(budget, candidates, mandatory_ids, category_caps, lambda_risk, min_coverage)
     -> OptimizationResult` returning the selected set, the achieved utility, and
     **shadow prices** (dual variables — "each extra €1000 of budget yields +X
     satisfaction").
   - Deterministic: same input → same output (seeded solver, no randomness).
3. Create migration `supabase/migrations/<timestamp>_benefit_optimizer.sql`:
   - Table `benefit_priors(id uuid pk, company_id uuid fk, category text, attr_key
     text, expected_satisfaction numeric, variance numeric, source text,
     updated_at timestamptz, updated_by uuid)`.
   - Unique on `(company_id, category, attr_key)`.
   - **RLS enabled**. Policy `benefit_priors_company_scoped` — users may read/write
     only for their own `company_id` (resolve via the existing `hr_company_membership`
     pattern). `REVOKE ALL ... FROM anon`.
4. Create `backend/app/routers/benefit_optimizer.py`:
   - `POST /api/hr/{company_id}/optimize-benefit-mix` — body is the optimization
     request (budget, candidate ids, category caps, lambda_risk, min_coverage).
     Response includes the selected portfolio, achieved utility, and shadow prices.
     Auth: HR-admin of the company or platform admin.
   - Register in `backend/app/main.py` via `include_router`.
5. Tests in `backend/tests/test_benefit_optimizer.py`:
   - 3-benefit toy case with hand-solved answer.
   - Budget too small to satisfy mandatory set → returns
     `OptimizationResult(feasible=False, infeasibility_reason="mandatory_exceeds_budget")`.
   - Category cap binds → solver returns the second-best in that category.
   - Shadow prices monotonic in budget.
6. Tests in `backend/tests/test_benefit_optimizer_router.py`:
   - 200 happy path with mocked candidates.
   - 403 for a non-HR-admin caller.
   - 422 for a malformed body.

### Design notes
- The optimization is a small mixed-integer program (binary selection per
  candidate). cvxpy with the CBC backend handles this trivially. Do not over-engineer.
- λ (risk aversion) is a tuning knob; default 0.3 with sensible bounds [0, 5].
- "Variance" of expected satisfaction is the prior on noise. If no priors exist for
  a (company, category, attr_key), use a default of `var = 0.25 * expected^2`
  (coefficient-of-variation 0.5).
- Shadow prices must be returned for: total budget constraint, each category cap,
  and min_coverage constraint. These are how the HR buyer learns where to spend
  the next marginal euro.

### Out of scope
- Frontend builder UI. A later prompt can add `<BenefitOptimizerPanel>`.
- Real employee-preference data. Step H (conjoint) will produce that; for now,
  priors are admin-seeded.

### Acceptance criteria
- pytest passes, tsc passes.
- Migration applies cleanly and `supabase db reset` still works.
- POST with the toy 3-benefit case returns the hand-solved optimum (assert exactly
  in the test).
- The deterministic-seed contract holds: same request → identical response bytes.

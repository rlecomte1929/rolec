# Step B: Benefit-mix portfolio optimizer (Markowitz-style)

You are executing **step B of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `benefit-optimizer`
**Your branch (create it if not yet on it):** `audit/parker-step-B-benefit-optimizer`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **B** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `B` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/B/PREREQUISITES.md` — auto-generated;
   lists upstream RESULT.md files you must consult.
4. For **each upstream step** named in PREREQUISITES.md, read:
   - `audit/parker-pipeline/runs/run-20260530-174625/<dep>/RESULT.md`
   - `audit/parker-pipeline/runs/run-20260530-174625/<dep>/VERIFICATION.md`
   Your implementation MUST align with what those steps **actually shipped** — table
   names, column names, route paths, type definitions — not with what the original
   audit prompt sketched. Sketches drift; ground-truth is the prior RESULT.md.
5. Read `CLAUDE.md` at the repo root. Pay particular attention to:
   - The **dual-layer architecture** (`backend/main.py` legacy vs `backend/app/` modular).
     New routes go in `backend/app/routers/`. Do not add routes to `backend/main.py`.
   - The **migration security rules** (hard gate): every new public table must
     `ENABLE ROW LEVEL SECURITY`, have at least one tenant-scoping policy, and
     `REVOKE ALL ... FROM anon`. Non-negotiable. Migrations that miss any of these
     fail review.
   - The **pre-push hook** and CI workflow. Frontend type-check must pass.

## STAGE 1.5 — UI reuse doctrine (read carefully)

Romain has explicitly asked that this pipeline **maximize reuse of existing
UI/UX patterns**. The backend may move fast; the frontend may not.

**Before creating any new component, page, or route — non-negotiable:**

1. `ls frontend/src/components/antigravity/` — these are the in-house primitives.
   Always reach for these first. No new third-party UI libraries.
2. `ls frontend/src/features/` — find the most similar existing feature and model
   your file structure, hook patterns, and component composition on it.
3. If you need a chart, use Recharts as it's already wired up. No new charting libs.
4. Lazy-load routes in `frontend/src/App.tsx` per the existing pattern.
5. Auth/role guards: reuse `frontend/src/navigation/` guards. No new role-check
   primitives.

**If the planned UI change is "significant"** — defined below — STOP before
writing any frontend code and write
`audit/parker-pipeline/runs/run-20260530-174625/B/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/B/BLOCKED.md` with the
single line "Waiting on UI-PROPOSAL approval. See UI-PROPOSAL.md." and STOP.
Romain will review and either greenlight (rerun the prompt) or move the UI work
to a follow-up prompt.

**What counts as "significant"**: a new top-level route, more than one new
component file, a new chart type not already in use, a new modal pattern, a
new form pattern, an employee-facing flow.

**What is NOT significant** (proceed normally): adding a field to an existing
form, a new badge/chip inside an existing page, a column on an existing table,
a small wrapper component around existing markup.

If the per-step UI impact line at the top of the task body says "Backend only"
or "In-place updates only", you can skip this whole stage — there's nothing
significant to propose.

## STAGE 2 — Write a plan BEFORE editing any file

Write `audit/parker-pipeline/runs/run-20260530-174625/B/PLAN.md` containing:

- **Task understanding** (3–5 sentences). Restate the goal in your own words.
- **Upstream alignment** — for each dependency listed in PREREQUISITES.md, summarise
  the actual schema / API / table you found in the prior RESULT.md and how your work
  attaches to it.
- **File-by-file change list** — every file you intend to create or edit, with a
  one-line description of the change.
- **New tables and migration plan** — table name, columns, RLS strategy (which roles
  read/write/insert/update), and the file path you'll add under `supabase/migrations/`.
- **New routes** — method, path, auth gate (`is_admin()`, session-token, public),
  and the router file under `backend/app/routers/` they'll register in.
- **Tests** — file paths and the assertions you'll write. Aim for ≥1 happy path,
  ≥1 edge case, ≥1 failure mode per non-trivial function.
- **Risks and unknowns** — what could go wrong, how you'll de-risk.
- **Deviations from the original audit prompt** — only if necessary, with reasons.

## STAGE 3 — Detect blockers and stop if found

If your reading in STAGE 1 reveals a blocker — a prerequisite step's RESULT.md is
missing, an expected table doesn't exist, a test is failing in main, a contradiction
between the audit prompt and the actual codebase — **do not push code**. Instead:

1. Write `audit/parker-pipeline/runs/run-20260530-174625/B/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-B-benefit-optimizer
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-B): benefit-optimizer: <one-line summary>

<optional body explaining the rationale>
```

---

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

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-B-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-B-tsc.log
```

Both must pass. If a test fails, fix it before continuing. If type-check fails, fix it.
"Fix it" means address the root cause — do not suppress with `// @ts-ignore` or
`pytest.skip` unless you document why in RESULT.md.

### 5.2 Diff hygiene

```bash
git diff main...HEAD --stat
```

Scan for accidental changes (debug prints, commented-out blocks, unrelated edits).
Remove them.

### 5.3 Write `RESULT.md`

Write `audit/parker-pipeline/runs/run-20260530-174625/B/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step B RESULT — Benefit-mix portfolio optimizer (Markowitz-style)

_Run: run-20260530-174625 | Branch: audit/parker-step-B-benefit-optimizer_

## Summary
<3–5 sentences. What shipped, why it matters.>

## Files changed
```
<paste `git diff main...HEAD --stat` output>
```

## Tests added
- `<test file path>` — <what it asserts>
- ...

## Test result
- pytest: <pass/fail summary, e.g. "412 passed, 3 skipped, 0 failed">
- tsc: <pass/fail>
- <paste last ~10 lines of each log if there's anything noteworthy>

## Migration applied?
- File: `supabase/migrations/<timestamp>_<name>.sql` (or "no migration")
- RLS posture (per new table):
  - Table `<name>`: RLS enabled? Policies? `REVOKE ALL ... FROM anon`?

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET    | /... | is_admin  | backend/app/routers/...py |

## New tables / schema changes
- `<table_name>` — columns, indexes, FKs.

## Configuration / env vars added
- `<VAR_NAME>` — what it controls, default, where read.

## UI changes summary
- New routes added: <list, or "none">
- New components added: <file paths, or "none">
- Existing antigravity components reused: <list — Romain will scan this>
- UI-PROPOSAL.md status: <"not required" / "approved" / "deferred to follow-up prompt">

## Deviations from the original audit prompt
<List any places where your implementation differs from section 4 of
audit/parker-framework-audit.md, and why. Often necessary; that's fine — record it.>

## What downstream steps will need from this step
<Be specific. Example: "Step E will fetch prompts via
`prompt_registry.get_active_prompt(task_key)` where `task_key` is the canonical task
identifier from the `prompt_versions.task_key` column. The canonical set as of this
commit is: ['policy_classification', 'mrz_extraction', 'eligibility_reasoning'].
New task_keys must be inserted via the admin route POST /api/admin/prompts.">

## Known gaps / follow-ups
<Things you didn't do, things that need attention but were out of scope. Each item
should ideally map to a Notion AI Work Queue task id.>
```

### 5.4 Push and open a PR

```bash
git push -u origin audit/parker-step-B-benefit-optimizer
gh pr create \
  --title "audit(parker-B): benefit-optimizer" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/B/RESULT.md \
  --label parker-audit
```

If the `parker-audit` label doesn't exist, create it first:
```bash
gh label create parker-audit --color "0E8A16" --description "Parker framework audit pipeline" || true
```

**Do not merge the PR.** Romain reviews each PR before merge. Render auto-deploys
`main`, so an unreviewed merge is a user-visible deploy.

### 5.5 Stop

You are done. Do not start the next step. Romain will:
1. Read `audit/parker-pipeline/runs/run-20260530-174625/B/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

# Step A: Cox survival model for case timelines

You are executing **step A of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `cox-survival`
**Your branch (create it if not yet on it):** `audit/parker-step-A-cox-survival`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **A** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `A` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/A/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/A/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/A/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/A/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/A/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-A-cox-survival
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-A): cox-survival: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step A

**UI impact:** None. Backend only. The frontend display badge is a separate, later
task and not in scope here.

Build a Cox proportional-hazards survival model that predicts time-to-completion for
relocation cases. This is the first quantitative prediction in ReloPass and the
foundation for any "we know when your case will close" claim to HR buyers.

### Prerequisites from prior steps
_None — A is the first step._

### Source material
- `backend/app/models.py` — case + milestone ORM models.
- `backend/app/services/case_milestones.py` — milestone events and timing.
- `backend/app/services/employee_assignments.py` (if present) — case covariates.
- `audit/parker-framework-audit.md` section 4, Prompt A.

### Concrete deliverables

1. Add `lifelines>=0.27` and `scikit-learn>=1.3` to `backend/requirements.txt`. If
   `scipy>=1.11` and `pandas>=2.0` are not present, add those too.
2. Create `backend/app/services/case_duration_model.py` with these functions:
   - `build_survival_frame(session) -> pd.DataFrame` — joins cases + milestones +
     assignments into a frame with columns: `case_id`, `duration_days`,
     `event_observed` (1 if case closed, 0 if right-censored), and covariates
     (`destination_country`, `origin_country`, `band`, `dependents_count`,
     `service_count`, `seasonality_quarter`).
   - `fit_cox_model(df) -> CoxPHFitter` — fits with L2 penalizer 0.1, returns the
     fitted lifelines `CoxPHFitter`.
   - `cross_validated_concordance(df, k=5) -> float` — k-fold C-index.
   - `predict_remaining_duration(model, case_id, session) -> dict` — returns
     `{"median_days": int, "p20_days": int, "p80_days": int, "model_version": str,
     "n_training_cases": int}`.
3. Create migration `supabase/migrations/<timestamp>_ml_models.sql`:
   - Table `ml_models(id uuid pk, model_key text, version text, pickled_blob bytea,
     trained_at timestamptz, n_training_rows int, concordance numeric, metadata jsonb)`.
   - Index on `(model_key, version)` and on `(model_key, trained_at desc)`.
   - **RLS enabled**. Policy `ml_models_admin_read` allows SELECT for users in
     `admin_allowlist`. No INSERT/UPDATE/DELETE policies — only the backend service
     role writes. `REVOKE ALL ON public.ml_models FROM anon;`.
4. Create `backend/app/routers/predictions.py`:
   - `GET /api/cases/{case_id}/predicted-duration` — returns the dict from
     `predict_remaining_duration`, gated on session-token auth + ownership check
     (caller must be the case owner, the case's HR contact, or an admin).
   - Register in `backend/app/main.py` via `include_router` per the dual-layer
     convention.
5. Tests in `backend/tests/test_case_duration_model.py`:
   - Happy path: synthetic frame of 200 cases → concordance ≥ 0.65.
   - Edge: all-censored frame should not crash; return a sentinel.
   - Failure: missing covariates → raises a typed `InsufficientDataError`.
6. Add an env flag `PREDICTIONS_ENABLED` (default `false`). The router returns 404
   when disabled. This is the canary kill-switch.
7. Add a CLI: `python -m backend.scripts.train_case_duration_model` that fits and
   persists the model (writes the pickled blob into `ml_models`).

### Design notes
- Use lifelines `CoxPHFitter`. Do not roll your own.
- The pickled blob must be deserialisable on the production Render container, which
  runs Python 3.11. Pin lifelines exactly to avoid pickle-version drift.
- `n_training_rows < 50` should refuse to fit and emit a structured warning to the
  ai_trace_logger (use the existing logger; do not create a new one).
- Do not block the request path on model training. Training runs in the CLI only.
- Concordance < 0.55 should mark the model as `status='unsafe_to_serve'` and the
  route should fall back to a deterministic estimate (mean duration by destination
  country, computed from the training frame).

### Out of scope
- Real Cox regression with time-varying covariates. Stay with the standard PH model.
- Frontend display. A separate task can build a `<CasePredictionBadge>` component
  later.

### Acceptance criteria
- `cd backend && pytest backend/tests/test_case_duration_model.py` passes.
- `cd backend && pytest -q` overall suite still passes (no regression).
- `cd frontend && npx tsc --noEmit` still passes (no frontend changes expected).
- The migration applies cleanly to a fresh local Supabase, and `supabase db reset`
  still works.
- `python -m backend.scripts.train_case_duration_model` against a synthetic seed
  produces an `ml_models` row and emits a structured log line.

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-A-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-A-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/A/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step A RESULT — Cox survival model for case timelines

_Run: run-20260530-174625 | Branch: audit/parker-step-A-cox-survival_

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
git push -u origin audit/parker-step-A-cox-survival
gh pr create \
  --title "audit(parker-A): cox-survival" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/A/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/A/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

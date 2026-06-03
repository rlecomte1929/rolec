# Step H: Conjoint analysis on benefit preferences

You are executing **step H of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `conjoint`
**Your branch (create it if not yet on it):** `audit/parker-step-H-conjoint`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **H** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `H` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/H/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/H/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/H/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/H/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/H/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-H-conjoint
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-H): conjoint: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step H

**UI impact:** None in this step. The employee choice flow AND the HR results
page are significant UI surfaces — they are deferred to
`prompts/followups/H-frontend.md`, which Romain runs separately once he's
approved the UI proposal. Build only the backend + service + API endpoints +
choice-set generation here.

Build a conjoint-analysis micro-service that, given a set of stated-preference
responses (employees ranking benefit bundles), estimates per-attribute part-worths
and simulates market share for proposed bundles. This is the single highest-value
commercial artefact for an HR-tech sales motion: it lets the buyer say "our
employees prefer bundle X over Y by Z%".

### Prerequisites from prior steps
_None required, but B is a natural fit._

If step B (benefit optimizer) has shipped, this step's part-worth output feeds B's
`benefit_priors` table. Read `audit/parker-pipeline/runs/<RUN_ID>/B/RESULT.md` if
present and align the priors-update path with B's schema.

### Source material
- `backend/app/services/employee_recommendations_filter.py` — benefit attribute model.
- `backend/app/services/hr_policy_resolver.py` — benefit categories and attributes.
- `audit/parker-framework-audit.md` section 2 (W7) and section 4, Prompt H.

### Concrete deliverables

1. Add `statsmodels>=0.14` to `backend/requirements.txt`.
2. Migration `supabase/migrations/<timestamp>_conjoint.sql`:
   - Table `conjoint_studies(
       id uuid pk, company_id uuid fk, name text, status text default 'draft',
       attributes_json jsonb,                  -- attribute → levels
       n_responses_target int default 100,
       opened_at timestamptz, closed_at timestamptz,
       created_at timestamptz default now()
     )`.
   - Table `conjoint_responses(
       id uuid pk, study_id uuid fk, respondent_user_id uuid,
       choice_set_json jsonb,                  -- bundles shown
       chosen_index int,                       -- which bundle they picked
       responded_at timestamptz default now()
     )`.
   - Table `conjoint_results(
       id uuid pk, study_id uuid fk,
       part_worths_json jsonb,                 -- attribute level → part-worth
       fit_quality_json jsonb,                 -- log-likelihood, McFadden R², n_obs
       computed_at timestamptz default now()
     )`.
   - **RLS enabled** on all three. Company-scoped: a company's HR admins see their
     studies; respondents see only their own response rows. `REVOKE ALL ... FROM anon`
     on all three.
3. Create `backend/app/services/conjoint_service.py`:
   - `design_study(attributes: dict[str, list[str]], n_choice_sets: int)
     -> list[ChoiceSet]` — generates a fractional-factorial design (use
     `statsmodels` or a simple D-efficient heuristic).
   - `fit_conjoint(responses: list[Response]) -> ConjointResults` — multinomial logit
     via `statsmodels.discrete.discrete_model.Logit` or `sklearn`'s logistic
     regression with effects coding; returns part-worths per attribute level.
   - `simulate_market_share(bundles: list[Bundle], part_worths) -> dict[bundle_id, share]`.
   - `recommend_bundle(budget, attribute_costs, part_worths, hard_constraints)
     -> Bundle` — picks the bundle maximising utility within budget.
4. Backend routes in `backend/app/routers/conjoint.py`:
   - `POST /api/hr/{company_id}/conjoint/studies` — create a study (HR admin).
   - `GET /api/hr/{company_id}/conjoint/studies/{study_id}/next-choice-set` —
     returns the next choice set for the calling respondent.
   - `POST /api/hr/{company_id}/conjoint/studies/{study_id}/responses` — submit a
     choice.
   - `POST /api/hr/{company_id}/conjoint/studies/{study_id}/fit` — fit (HR admin).
   - `GET /api/hr/{company_id}/conjoint/studies/{study_id}/results` — read part-worths.
   - Register in `backend/app/main.py`.
5. Frontend: **DEFERRED.** Do not build the employee choice flow or the HR
   results page in this step. Both are significant UI surfaces and ship via
   `prompts/followups/H-frontend.md` when Romain approves the UI proposal.
   Surface this clearly in RESULT.md under "Known gaps / follow-ups".
6. If B's `benefit_priors` table exists, add a service call
   `push_to_benefit_priors(study_id, company_id)` that maps part-worths into the
   `(company_id, category, attr_key)` rows B reads from. Otherwise log a TODO and
   surface it in the UI.
7. Tests:
   - `backend/tests/test_conjoint_service.py` — fits the standard Sawtooth-style
     synthetic dataset (well-known, no licence issue); McFadden R² ≥ 0.25 on the
     synthetic set.
   - `backend/tests/test_conjoint_router.py` — auth gates, response idempotency,
     fit endpoint persists results.

### Design notes
- The choice set design is the trickiest part. Don't optimise it perfectly —
  a D-optimal design via balanced randomisation over 8–12 sets per respondent is
  more than sufficient for the early-stage product claim.
- Respondent anonymity: store `respondent_user_id` for de-duplication but never
  expose it in HR-facing results. Aggregations only.
- Use effects coding (not dummy coding) so part-worths are interpretable as
  deviations from the grand mean — this is what HR readers expect.

### Out of scope
- Latent-class conjoint (segment-level part-worths). Aggregate fit only.
- Hierarchical Bayes conjoint. Aggregate MNL is sufficient for v1.
- Mobile-optimised UI. Desktop is enough for first pilot.

### Acceptance criteria
- pytest + tsc both pass.
- Migrations apply; RLS enforces company scoping (test with two seeded companies).
- Fit on the synthetic Sawtooth dataset reaches the McFadden R² target.
- RESULT.md states clearly that the employee + HR UI is deferred to
  `prompts/followups/H-frontend.md` per Romain's UI-reuse mandate.

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-H-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-H-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/H/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step H RESULT — Conjoint analysis on benefit preferences

_Run: run-20260530-174625 | Branch: audit/parker-step-H-conjoint_

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
git push -u origin audit/parker-step-H-conjoint
gh pr create \
  --title "audit(parker-H): conjoint" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/H/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/H/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

# Step G: Carbon + per-customer AI unit economics

You are executing **step G of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `carbon-tco`
**Your branch (create it if not yet on it):** `audit/parker-step-G-carbon-tco`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **G** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `G` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/G/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/G/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/G/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/G/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/G/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-G-carbon-tco
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-G): carbon-tco: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step G

**UI impact:** None in this step. The admin panel for AI unit economics is
deferred to `prompts/followups/G-frontend.md`, which Romain runs separately
once he's approved the UI proposal. Build only the backend + JSON endpoint here.

Extend `ai_trace_logger.py` so every LLM call records (a) an estimated CO₂e value
and (b) a customer attribution, then produce a rollup view exposing cost-per-customer
and carbon-per-customer per feature. This is the unit-economics layer that
defends the YC pitch and the Series-A pitch.

### Prerequisites from prior steps
_None — G is independent._

If step F has shipped, G can also ingest F's documented cost model for the OSS
passport pipeline. Read `audit/parker-pipeline/runs/<RUN_ID>/F/RESULT.md` if present.

### Source material
- `backend/app/services/ai_trace_logger.py` — current trace structure.
- `backend/relopass/llm/router.py` — model registry and cost YAML.
- `audit/parker-framework-audit.md` section 2 (W14) and section 4, Prompt G.

### Concrete deliverables

1. Migration `supabase/migrations/<timestamp>_ai_unit_economics.sql`:
   - Table `ai_model_energy_profiles(
       model_name text pk,
       joules_per_input_token numeric not null,
       joules_per_output_token numeric not null,
       region_gco2_per_kwh numeric not null,        -- region grid carbon intensity
       source_url text,                              -- cite where the estimate comes from
       updated_at timestamptz not null default now()
     )`.
   - Seed rows for the models in the existing router: claude-sonnet-4-6,
     claude-haiku-4-5, gpt-4o, gpt-4o-mini, text-embedding-3-small. Cite public
     estimates (e.g., Anthropic / OpenAI sustainability reports, Patterson et al.,
     ML CO2 Impact paper). The numbers are rough; that's fine, the framework
     matters more than the precision today.
   - Add columns to existing `policy_assistant_traces` (or whatever the active
     traces table is called — read D's RESULT.md if D added new columns):
     `co2e_grams_estimated numeric`, `customer_id uuid`, `feature_key text`.
   - Materialized view `mv_ai_unit_economics` aggregating
     `(week, customer_id, feature_key)` → `total_cost_usd, total_tokens_in,
     total_tokens_out, total_co2e_grams, n_calls`.
   - **RLS** on `ai_model_energy_profiles`: SELECT for authenticated; UPDATE for
     admins. `REVOKE ALL ... FROM anon`.
   - **RLS** on `mv_ai_unit_economics`: SELECT for admins of the rolled-up customer,
     plus platform admins. `REVOKE ALL ... FROM anon`.
2. Create `backend/app/services/ai_carbon_estimator.py`:
   - `estimate_co2e_grams(model_name, tokens_in, tokens_out) -> float` —
     `(tokens_in * J_in + tokens_out * J_out) / 3_600_000 (J→kWh) * gCO2_per_kWh`.
   - Reads from `ai_model_energy_profiles`. Caches the profile in-process.
   - Falls back to a global default if the model is unknown, and logs a warning.
3. Extend `TraceSession.flush()` in `ai_trace_logger.py` to:
   - Compute `co2e_grams_estimated` via the estimator.
   - Resolve `customer_id` and `feature_key` from the call context. Every call
     site must now pass these via the TraceSession constructor or context manager.
   - Persist the new columns.
4. Update every existing call site to pass `feature_key`:
   - `policy_assistant_rag_engine.py` → `feature_key='policy_assistant'`.
   - `llm_policy_extractor.py` → `feature_key='policy_extraction'`.
   - `ocr_passport_extractor.py` → `feature_key='passport_ocr'`.
   - Any other LLM-using service module.
   Use a constant module `backend/app/services/ai_feature_keys.py` with all keys
   as `Literal` types for type safety.
5. Admin route in `backend/app/routers/admin_ai_unit_economics.py`:
   - `GET /api/admin/ai-unit-economics?customer_id=...&from=...&to=...&feature_key=...`
     → returns the rollup from `mv_ai_unit_economics`.
   - Auth: `is_admin()` allowlist.
   - Register in `backend/app/main.py`.
6. Frontend panel: **DEFERRED.** Do not build the admin panel here. Surface a
   note in RESULT.md under "Known gaps / follow-ups" stating that the admin
   panel ships via `prompts/followups/G-frontend.md` when Romain approves the
   UI proposal.
7. Refresh schedule:
   - Add to `audit/parker-pipeline/runs/<RUN_ID>/G/RESULT.md` a suggested
     pg_cron entry to refresh `mv_ai_unit_economics` nightly at 02:00 UTC.
8. Tests:
   - `backend/tests/test_ai_carbon_estimator.py` — known inputs, expected gCO₂e.
   - `backend/tests/test_trace_logger_carbon.py` — TraceSession persists the new
     columns; missing model_name falls back to default and warns.
   - `backend/tests/test_admin_ai_unit_economics_router.py` — auth, schema, date
     filtering.
   - Frontend snapshot test for the panel.

### Design notes
- The carbon estimate is approximate. State this in the panel UI ("≈ estimated;
  vendor energy intensity is not public").
- `feature_key` is the master attribution dimension. Use `Literal` types
  end-to-end (TypeScript on frontend, Pydantic + Literal on backend) so unknown
  keys fail at edit time, not runtime.
- The materialized view should be cheap to refresh (group-by on a trace table
  with a timestamptz index). If the trace table is large, add an index on
  `(customer_id, feature_key, created_at)`.
- Surface the panel link in the existing AIPanel.tsx component.

### Out of scope
- Per-employee attribution (one level deeper). Customer-level is sufficient for now.
- Scope 2 vs Scope 3 distinctions. We report a single CO₂e number.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies cleanly; mv refreshes without error.
- Every existing LLM call site now passes `feature_key` — verify with a grep
  assertion in CI (no bare TraceSession() construction).
- Admin endpoint returns realistic numbers for a seeded fixture.
- Note in RESULT.md that the frontend panel ships via the follow-up prompt
  `prompts/followups/G-frontend.md` (deferred per Romain's UI-reuse mandate).

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-G-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-G-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/G/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step G RESULT — Carbon + per-customer AI unit economics

_Run: run-20260530-174625 | Branch: audit/parker-step-G-carbon-tco_

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
git push -u origin audit/parker-step-G-carbon-tco
gh pr create \
  --title "audit(parker-G): carbon-tco" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/G/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/G/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

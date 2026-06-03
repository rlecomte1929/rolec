# Step C: Cluster-relative supplier tiering

You are executing **step C of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `cluster-tiering`
**Your branch (create it if not yet on it):** `audit/parker-step-C-cluster-tiering`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **C** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `C` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/C/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/C/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/C/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/C/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/C/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-C-cluster-tiering
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-C): cluster-tiering: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step C

**UI impact:** None. The tier label values (BEST_MATCH/GOOD_FIT/OK/WEAK) are
unchanged, so frontend is unaffected.

Re-engineer the recommendation engine so BEST_MATCH / GOOD_FIT / OK / WEAK tiers are
derived from per-cluster percentiles instead of absolute thresholds (currently
85/70/50). Today, a strong supplier in a thin market gets unfairly demoted — this
is mis-calibrated tiering and HR buyers in small markets notice.

### Prerequisites from prior steps
_None — C is independent._

### Source material
- `backend/app/recommendations/engine.py` — the current scoring + tiering function.
- `backend/app/services/supplier_registry.py` — how suppliers are loaded.
- `backend/app/recommendations/plugins/banks.py` — a representative plugin to read
  the scoring contract.
- `audit/parker-framework-audit.md` section 2 (W15) and section 4, Prompt C.

### Concrete deliverables

1. Add `scikit-learn>=1.3` and `scipy>=1.11` to `backend/requirements.txt` if not
   already there.
2. Create `backend/app/recommendations/tiering.py`:
   - `cluster_suppliers(suppliers, category, country_iso2) -> ClusterAssignment` —
     KMeans with K∈[2,6] selected by silhouette score; returns cluster id per
     supplier plus the silhouette.
   - `tier_with_cluster_context(score, cluster_id, thresholds_per_cluster) -> Tier`
     — returns BEST_MATCH/GOOD_FIT/OK/WEAK based on the per-cluster empirical
     quantiles of the heuristic score (top 15% = BEST_MATCH, next 35% = GOOD_FIT,
     next 35% = OK, bottom 15% = WEAK).
   - `compute_cluster_cache(category, country_iso2) -> dict` — runs the clustering,
     computes per-cluster thresholds, returns the cache payload.
3. Create migration `supabase/migrations/<timestamp>_supplier_cluster_cache.sql`:
   - Table `supplier_cluster_cache(id uuid pk, service_category text, country_iso2
     char(2), cluster_id int, cluster_size int, k_selected int, silhouette numeric,
     thresholds_json jsonb, supplier_ids_json jsonb, computed_at timestamptz)`.
   - Unique on `(service_category, country_iso2, computed_at desc)`.
   - **RLS enabled**. SELECT for authenticated; INSERT/UPDATE for admins only.
     `REVOKE ALL ... FROM anon`.
4. Modify `backend/app/recommendations/engine.py`:
   - `tier(score)` → `tier(score, *, category=None, country_iso2=None)`.
   - When `category` and `country_iso2` are present **and** the cell has ≥ 8
     suppliers in cache, dispatch to `tiering.tier_with_cluster_context`.
   - Otherwise, keep the existing 85/70/50 fallback.
5. Add a scheduled refresh:
   - CLI: `python -m backend.scripts.refresh_supplier_clusters [--category X] [--country Y]`.
   - Suggest a cron entry in `audit/parker-pipeline/runs/<RUN_ID>/C/RESULT.md` for
     Romain to wire up (do not auto-create cron — that's a deploy decision).
6. Observability:
   - Log per-(category, country) cluster K, silhouette score, and supplier count to
     `ai_trace_logger.py` under `feature_key='cluster_tiering_refresh'`.
   - Add metric `cluster_tiering_fallback_total` (Prometheus-style counter) for
     cells that fell back to absolute thresholds because n < 8.
7. Tests in `backend/tests/test_cluster_tiering.py`:
   - Deterministic seed: same suppliers → same clusters → same thresholds.
   - <8 suppliers: falls back to absolute thresholds.
   - Known top-3 supplier in a fixture cluster is tiered BEST_MATCH.
   - Tier monotonicity: higher score within a cluster → no worse tier.

### Design notes
- Use `StandardScaler` before KMeans. Suppliers with NaN features are excluded from
  clustering and tiered with the fallback path.
- Plugin scoring contracts MUST NOT change. The only thing that changes is the
  `engine.tier()` signature, with backward-compatible defaults.
- Cache TTL: do not expire automatically. Refresh is explicit (CLI). The
  `computed_at` column lets readers detect staleness.

### Out of scope
- Re-tiering historical recommendations. New requests use the new tiering; past
  recommendations stay as written.
- Frontend tier badges. The label values are unchanged so frontend is unaffected.

### Acceptance criteria
- pytest passes; tsc passes (no frontend changes).
- Migration applies cleanly.
- For a fixture with 30 suppliers in (banks, BE), at least one supplier moves from
  GOOD_FIT (absolute) to BEST_MATCH (cluster-relative) — assert this in a test.
- `refresh_supplier_clusters` CLI completes for a synthetic seed in < 5 seconds.

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-C-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-C-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/C/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step C RESULT — Cluster-relative supplier tiering

_Run: run-20260530-174625 | Branch: audit/parker-step-C-cluster-tiering_

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
git push -u origin audit/parker-step-C-cluster-tiering
gh pr create \
  --title "audit(parker-C): cluster-tiering" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/C/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/C/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

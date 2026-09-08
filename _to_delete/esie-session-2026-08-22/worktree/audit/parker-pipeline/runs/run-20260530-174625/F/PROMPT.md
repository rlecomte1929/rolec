# Step F: Open-source fallback for passport OCR

You are executing **step F of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `passport-ocr-oss`
**Your branch (create it if not yet on it):** `audit/parker-step-F-passport-ocr-oss`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **F** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `F` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/F/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/F/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/F/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/F/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/F/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-F-passport-ocr-oss
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-F): passport-ocr-oss: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step F

**UI impact:** None. Backend + a single admin JSON endpoint
(`GET /api/admin/ocr-shadow-comparison`). The shadow-comparison dashboard UI is
a deferred follow-up (see `prompts/followups/F-shadow-dashboard-ui.md` —
created later if Romain wants it).

Add a self-hosted open-source fallback for passport OCR so the high-volume vision
task can be served without GPT-4o. Goal: shadow-compare against the existing
GPT-4o pipeline, then ramp traffic if accuracy is comparable. This is a margin
play and a vendor-lock-in mitigation.

### Prerequisites from prior steps

**Soft dependency on step D.** If D is complete, route via `prompt_registry` for the
prompt that drives the structured extraction. Read:
- `audit/parker-pipeline/runs/<RUN_ID>/D/RESULT.md`

If D is not yet complete, use the existing static-prompt pattern in
`backend/relopass/llm/router.py`. Note this clearly in PLAN.md under "Deviations".

### Source material
- `backend/app/services/ocr_passport_extractor.py` — current GPT-4o-vision extractor.
- `backend/relopass/llm/router.py` — routing pattern + ESCALATION_CONFIDENCE_THRESHOLDS.
- `audit/parker-framework-audit.md` section 2 (W9, W13) and section 4, Prompt F.

### Concrete deliverables

1. ADR at `audit/adr/adr-001-self-hosted-passport-ocr.md` documenting the model
   choice and tradeoffs:
   - **Text/MRZ extraction:** PaddleOCR (server CPU OK for low-volume; GPU for high).
   - **Structured fields (name, DOB, nationality, dates):** Florence-2-base (small VLM,
     0.23B params, runs on a single T4).
   - Alternatives considered: Qwen2-VL-2B, MiniGPT-v2, LLaVA. Document why Florence-2
     was chosen (size + open weights + permissive licence).
2. Create `backend/app/services/passport_ocr_oss.py` exposing the same interface as
   `ocr_passport_extractor.py`:
   - `extract_passport_fields(image_bytes: bytes) -> PassportExtraction` returning
     the same dataclass shape as the GPT-4o extractor.
   - MRZ validation via ICAO 9303 — reuse the existing util, do not duplicate.
   - Confidence scores per field (0.0–1.0). Use Florence-2's logprobs where
     available; otherwise fallback to a calibrated heuristic (e.g. 0.95 if both
     MRZ and visual zone agree; 0.6 if only one source produced the field).
3. Wire into `backend/relopass/llm/router.py`:
   - Add to ROUTING_TABLE under `task_class='mrz_extraction'` a split controlled by
     env var `PASSPORT_OCR_OSS_SHARE` (default `0.0`).
   - Add `SHADOW_COMPARE=true` mode: runs BOTH extractors, returns the GPT-4o result
     to the caller, logs per-field disagreement to the trace logger under
     `feature_key='passport_ocr_shadow'`.
4. Shadow comparison dashboard:
   - Materialized view `mv_ocr_shadow_comparison` aggregating per-field agreement
     rate, MRZ-pass rate, cost-per-extraction for both pipelines.
   - Migration: only the view; no new base table.
   - **RLS enabled** on the view (admin-only).
   - `GET /api/admin/ocr-shadow-comparison?from=...&to=...` returning the rollup.
5. Tests:
   - `backend/tests/test_passport_ocr_oss.py` against a small fixture set of
     synthetic passport images. Use the existing fixtures if any; otherwise
     generate via a passport-image-mock library and commit a small (<200 KB)
     fixture set under `backend/tests/fixtures/passport_synthetic/`.
   - Shadow-comparison test: with `SHADOW_COMPARE=true`, both extractors run and
     the trace logger receives a `passport_ocr_shadow` row with the diff.
   - Disagreement metric: a hand-crafted "disagreement should be 2 fields" fixture.

### Design notes
- **Do not enable in production traffic** until shadow comparison shows ≥99% field
  agreement on a 200+ image eval set. State this clearly in RESULT.md.
- Florence-2 weights are ~450MB. Document in the ADR: where they're hosted
  (Hugging Face hub), how the production container pulls them (cache at build time
  via a Dockerfile RUN step), and the GPU requirement (T4 or better).
- Confidence calibration is the trickiest part. Don't over-engineer — a simple
  rule ("MRZ+visual agree → high; only one source → medium; neither → low") is
  good enough for shadow comparison. Real calibration comes later when we have
  feedback data from step E.
- Document the cost model: USD per 1000 extractions for GPT-4o vs OSS (compute
  cost only). This belongs in RESULT.md so step G can ingest it.

### Out of scope
- Diploma extraction OSS (step F is passport-only).
- Replacing the GPT-4o extractor. This step adds a parallel path; ramp decision
  is a follow-up.

### Acceptance criteria
- pytest passes.
- ADR exists at `audit/adr/adr-001-self-hosted-passport-ocr.md`.
- `PASSPORT_OCR_OSS_SHARE=0.0` is the default — production traffic unchanged.
- `SHADOW_COMPARE=true` produces shadow-comparison trace rows.
- `GET /api/admin/ocr-shadow-comparison` returns a well-formed rollup.
- RESULT.md states explicitly: "OSS path is NOT routed to production users at any %.
  Romain must set `PASSPORT_OCR_OSS_SHARE > 0` after reviewing shadow comparison."

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-F-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-F-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/F/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step F RESULT — Open-source fallback for passport OCR

_Run: run-20260530-174625 | Branch: audit/parker-step-F-passport-ocr-oss_

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
git push -u origin audit/parker-step-F-passport-ocr-oss
gh pr create \
  --title "audit(parker-F): passport-ocr-oss" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/F/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/F/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

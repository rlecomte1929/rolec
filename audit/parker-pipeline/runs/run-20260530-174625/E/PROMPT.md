# Step E: RLHF-lite preference dataset from Notion Human Review

You are executing **step E of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `rlhf-lite`
**Your branch (create it if not yet on it):** `audit/parker-step-E-rlhf-lite`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **E** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `E` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/E/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/E/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/E/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/E/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/E/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-E-rlhf-lite
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-E): rlhf-lite: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step E

**UI impact:** Adds a single win-rate column to D's existing `/admin/prompts`
page. No new pages, no new components. Reuses the table primitive from D.

Close the loop between Notion's Human Review queue and model quality by emitting a
preference dataset suitable for DPO-style fine-tuning or for re-ranking prompt-registry
canaries. This is the cheap version of RLHF: log human verdicts, build pairs, surface
win rates.

### Prerequisites from prior steps — REQUIRED READING

**You depend on step D.** Before writing any code, read:
- `audit/parker-pipeline/runs/<RUN_ID>/D/RESULT.md`

Pay attention to:
- The exact `prompt_versions` schema D shipped (column names, types).
- The canonical task_key set D documented.
- The `ActivePrompt` dataclass shape — your feedback must reference `prompt_version_id`.
- The TraceSession columns D extended (`prompt_version_id`, `canary_arm`).

Your code MUST use D's actual schema, not what the original audit doc sketched.

If D's RESULT.md is missing or D's status in STATE.json is not `completed`, **stop and
write BLOCKED.md**.

### Source material
- `backend/app/services/ai_trace_logger.py` — TraceSession model.
- The `notion-review-validator` skill at
  `/var/folders/.../anthropic-skills/notion-review-validator/SKILL.md` — defines the
  review payload shape (approved/rejected/edited).
- `audit/parker-framework-audit.md` section 2 (W10) and section 4, Prompt E.

### Concrete deliverables

1. Migration `supabase/migrations/<timestamp>_ai_human_feedback.sql`:
   - Table `ai_human_feedback(
       id uuid pk,
       trace_session_id uuid not null fk → policy_assistant_traces.id,
       reviewer_user_id uuid not null,
       verdict text not null,                  -- approved|rejected|edited
       edited_output_json jsonb,
       comment text,
       prompt_version_id uuid fk → prompt_versions.id,  -- from D
       canary_arm text,                        -- 'prod' or 'canary', for attribution
       created_at timestamptz not null default now()
     )`.
   - Unique on `(trace_session_id, reviewer_user_id)` — idempotency.
   - Index on `(prompt_version_id, verdict)` for win-rate aggregation.
   - **RLS enabled**. SELECT for admins; INSERT for the service role only.
     `REVOKE ALL ... FROM anon`.
2. Backend route in `backend/app/routers/ai_feedback.py`:
   - `POST /api/ai/feedback` — body `{trace_session_id, verdict, edited_output_json?,
     comment?}`. Idempotent on `(trace_session_id, reviewer_user_id)`. Derives
     `prompt_version_id` and `canary_arm` by joining to the trace.
   - Auth: session-token (any authenticated user who is a reviewer).
   - Register in `backend/app/main.py`.
3. Create `backend/app/services/preference_dataset_builder.py`:
   - `build_dpo_pairs(task_key: str, min_pairs: int = 50) -> list[DPOPair]` —
     returns chosen/rejected pairs in the canonical `{prompt, chosen, rejected}`
     JSONL shape. Pairs are formed by matching trace_sessions on the same
     `(prompt_template_hash, input_hash)` where the canary arm was approved and
     the prod arm was rejected (or vice-versa).
   - `compute_win_rates(task_key) -> dict[version_id, WinRate]` — per-version
     win rate (approvals / total verdicts) plus 95% CI.
4. CLI: `python -m backend.scripts.export_preference_dataset \
     --task-key policy_classification \
     --out preferences/policy_classification_$(date +%Y%m%d).jsonl`.
   Writes a newline-delimited JSON file. Creates the `preferences/` directory if
   missing. Adds `preferences/` to `.gitignore` (do not commit datasets).
5. Surface win rates in the admin prompts page from D:
   - Extend `frontend/src/features/admin/prompts/PromptsPage.tsx` (modifying D's
     file) to show per-version win rate next to the version.
   - Use the new endpoint `GET /api/admin/prompts/{task_key}/win-rates`.
6. Tests:
   - `backend/tests/test_ai_feedback_router.py` — idempotency, auth, schema.
   - `backend/tests/test_preference_dataset_builder.py` — pair construction
     correctness; empty trace → empty pairs without error.
   - Snapshot test for the JSONL writer.

### Design notes
- **Do not auto-fine-tune anything** in this step. The deliverable is the dataset
  and the loop, not the training run.
- A Notion review may produce verdicts in three shapes (approved, rejected,
  edited). Treat `edited` as "rejected for the original output, approved for the
  edited output" — both rows go into the feedback table with appropriate verdict.
- Pair construction: only pair where the two trace_sessions answered the same
  underlying question (same input hash) AND received different arms. That is the
  only honest A/B signal you can extract from organic traffic.
- Win-rate CI: use Wilson interval — Romain will read these numbers in product
  meetings, naive ±√(p(1-p)/n) is misleading for small n.

### Out of scope
- DPO training itself.
- A self-serve labelling UI inside ReloPass. Notion is the review surface.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies; FK to `prompt_versions` is enforced (test it).
- The Notion skill can POST to /api/ai/feedback and the row lands with the right
  `prompt_version_id` and `canary_arm` (test with a mocked trace).
- CLI produces a well-formed JSONL with ≥1 pair on a fixture seed.
- Admin page shows win rates per version.

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-E-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-E-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/E/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step E RESULT — RLHF-lite preference dataset from Notion Human Review

_Run: run-20260530-174625 | Branch: audit/parker-step-E-rlhf-lite_

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
git push -u origin audit/parker-step-E-rlhf-lite
gh pr create \
  --title "audit(parker-E): rlhf-lite" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/E/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/E/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

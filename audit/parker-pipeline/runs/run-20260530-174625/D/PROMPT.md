# Step D: Prompt registry + canary A/B

You are executing **step D of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `prompt-registry`
**Your branch (create it if not yet on it):** `audit/parker-step-D-prompt-registry`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **D** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `D` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/D/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/D/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/D/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/D/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/D/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-D-prompt-registry
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-D): prompt-registry: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step D

**UI impact:** ONE small admin table page at `/admin/prompts`. Reuses
`frontend/src/components/antigravity/` primitives (Card, Table, Button, Badge)
and follows the closest existing admin page as its visual model (e.g. the
suppliers admin page — find it via `ls frontend/src/features/admin/`). Does NOT
require UI-PROPOSAL.md because it's a single utilitarian admin table inside an
existing admin area, no new chart types, no new modal patterns.

Build a prompt registry so system prompts and few-shot examples are versioned,
A/B-testable, and rollback-able. Today prompts live as string literals in Python
modules — invisible to product, untraceable in `git log`, impossible to A/B-test.
This step is a **platform unlock**: steps E, F, and I all depend on it.

### Prerequisites from prior steps
_None — D is independent. But three downstream steps (E, F, I) depend on D, so the
schema and API you ship here are contractual. Be deliberate._

### Source material
- `backend/relopass/llm/router.py` — the existing deterministic LLM router.
- `backend/app/services/ai_trace_logger.py` — TraceSession schema you will extend.
- `backend/app/services/llm_policy_extractor.py` and
  `backend/app/services/policy_assistant_rag_engine.py` — current consumers with
  hardcoded prompts.
- `audit/parker-framework-audit.md` section 2 (W12) and section 4, Prompt D.

### Concrete deliverables

1. Migration `supabase/migrations/<timestamp>_prompt_registry.sql`:
   - Table `prompt_versions(
       id uuid pk,
       task_key text not null,                   -- e.g. 'policy_classification'
       version int not null,                     -- monotonically increasing per task_key
       system_prompt text not null,
       user_template text,                       -- jinja2-like {{var}} placeholders
       model_name text not null,                 -- e.g. 'claude-sonnet-4-6'
       temperature numeric not null default 0.0,
       max_tokens int not null default 1024,
       status text not null default 'draft',     -- draft|canary|prod|archived
       created_at timestamptz not null default now(),
       created_by uuid,
       notes text
     )`.
   - Unique on `(task_key, version)`.
   - Partial unique index: at most one `status='prod'` per `task_key`.
   - Table `prompt_routing(
       task_key text pk,
       canary_share numeric not null default 0.0  -- 0.0–1.0
     )`.
   - **RLS enabled** on both. SELECT for authenticated; INSERT/UPDATE for admins
     only. `REVOKE ALL ... FROM anon` on both.
2. Create `backend/app/services/prompt_registry.py`:
   - `get_active_prompt(task_key: str) -> ActivePrompt` — returns a typed dataclass
     `ActivePrompt(id, version, system_prompt, user_template, model_name,
     temperature, max_tokens, canary_arm)`. Performs the canary split using
     `random.random() < canary_share`; the chosen `canary_arm` is `'prod'` or
     `'canary'` and is logged for downstream attribution.
   - `render_user_message(template, variables) -> str` — simple `{{name}}`
     substitution (no jinja runtime — keep it dependency-free).
   - `list_versions(task_key)`, `promote(version_id, target_status)`,
     `set_canary_share(task_key, share)`.
3. **Refactor** the two existing consumers to use the registry:
   - `backend/app/services/llm_policy_extractor.py` — replace string literals with
     `prompt_registry.get_active_prompt('policy_extraction')`.
   - `backend/app/services/policy_assistant_rag_engine.py` — likewise for
     `policy_assistant_answer`.
   - Seed the registry with the current prompts as `version=1, status='prod'` in
     the migration (or a follow-up data migration).
4. Extend `TraceSession` in `ai_trace_logger.py` to record
   `prompt_version_id` and `canary_arm`. Confirm the policy_assistant_traces table
   supports these columns (add a migration step if not).
5. Admin routes in a new `backend/app/routers/admin_prompts.py`:
   - `GET /api/admin/prompts` — list task_keys and the active prod + canary version.
   - `GET /api/admin/prompts/{task_key}` — list all versions.
   - `POST /api/admin/prompts` — create a new draft version.
   - `POST /api/admin/prompts/{version_id}/promote` — body `{status: 'canary'|'prod'}`.
   - `POST /api/admin/prompts/{task_key}/canary-share` — body `{share: 0..1}`.
   - Auth: `is_admin()` allowlist for all routes.
   - Register in `backend/app/main.py`.
6. Minimal frontend at `frontend/src/features/admin/prompts/PromptsPage.tsx`:
   - Table listing task_key, prod version, canary version, canary share.
   - Per task: list of versions with promote / archive buttons.
   - Route: `/admin/prompts`, gated by admin role guard.
   - Use the `frontend/src/components/antigravity/` design system per CLAUDE.md.
7. Tests:
   - `backend/tests/test_prompt_registry.py` — canary split is ~10% over 10k draws
     (chi-square within tolerance); promote demotes prior prod; partial unique
     index prevents two prod rows.
   - `backend/tests/test_admin_prompts_router.py` — auth gates, 200 happy path.
   - `frontend/src/features/admin/prompts/__tests__/PromptsPage.test.tsx` —
     renders table, promote button calls the right endpoint (mocked).

### Design notes
- This is the **contract** for downstream steps. Document the schema and the
  `ActivePrompt` shape exactly in RESULT.md. Downstream steps will read RESULT.md
  to know the canonical task_key values.
- Canary attribution: every TraceSession row must record which arm served the
  response so eval pipelines can compute per-arm win rates.
- Keep dependency-free: no jinja2. The `{{var}}` substitution is intentionally
  trivial.
- Do not break the existing two consumers. The seeded `version=1, status='prod'`
  must reproduce today's prompts byte-for-byte.

### Out of scope
- The actual A/B win-rate dashboard (next sprint).
- Few-shot example management beyond a single `notes` field.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies; partial unique index prevents two prod rows for the same
  task_key (test it).
- The two refactored consumers produce identical outputs against a fixture set
  before and after the refactor (snapshot test).
- The admin page renders and the promote button works against a mocked API.
- RESULT.md documents the canonical task_key set and the `ActivePrompt` shape —
  downstream steps E, F, I will rely on this.

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-D-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-D-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/D/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step D RESULT — Prompt registry + canary A/B

_Run: run-20260530-174625 | Branch: audit/parker-step-D-prompt-registry_

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
git push -u origin audit/parker-step-D-prompt-registry
gh pr create \
  --title "audit(parker-D): prompt-registry" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/D/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/D/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

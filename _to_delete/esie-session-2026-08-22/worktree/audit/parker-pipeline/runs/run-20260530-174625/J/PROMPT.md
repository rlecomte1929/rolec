# Step J: NLG variety (data-to-text, frame-based, extractive)

You are executing **step J of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `nlg-variety`
**Your branch (create it if not yet on it):** `audit/parker-step-J-nlg-variety`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **J** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `J` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/J/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/J/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/J/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/J/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/J/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-J-nlg-variety
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-J): nlg-variety: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step J

**UI impact:** In-place updates only. Modifies the existing HR command center
exec summary card and adds a TL;DR panel inside the existing policy viewer. No
new pages, no new top-level routes, no new components — only swapping the
content source on existing surfaces. Does NOT require UI-PROPOSAL.md.

Diversify NLG. Today ReloPass produces markdown templates only; Parker enumerates
14 NLG approaches. Add three high-leverage ones: (1) **data-to-text** for executive
HR dashboards, (2) **frame-based NLG** for incident / case reports, (3) **extractive
summarisation** for long policy documents. Each serves a distinct buyer artefact
the LLM-only path cannot match for cost, auditability, or determinism.

### Prerequisites from prior steps
_None required._

If step I (translation) has shipped, the NLG outputs here should optionally route
through translation when the recipient's preferred_language ≠ source language.
Read `audit/parker-pipeline/runs/<RUN_ID>/I/RESULT.md` if present.

### Source material
- `backend/app/services/guidance_markdown.py` — current template-based NLG.
- `backend/app/services/policy_session_pdf.py` — PDF rendering path.
- `audit/parker-framework-audit.md` section 2 (W11) and section 4, Prompt J.

### Concrete deliverables

1. New package `backend/app/services/nlg/`:
   - `__init__.py` exports `data_to_text`, `frame_based`, `extractive_summarizer`.
   - `nlg/data_to_text.py`:
     - `summarise_kpis(kpis: KPISet, *, audience: Literal['exec', 'hr-ops']) -> str`
       — takes a structured dict of KPIs (current value, prior value, delta,
       target, anomaly flag) and produces a 3–5 sentence summary using
       deterministic templates plus sentence ordering by salience (largest
       absolute delta first; anomalies always lead).
     - No LLM call. No randomness. Same input → same output (assert with snapshot).
   - `nlg/frame_based.py`:
     - `Frame(event_type, slots)` dataclass.
     - Registered frames for: `passport_expiry_at_risk`, `assignment_milestone_missed`,
       `policy_change_required`, `supplier_unresponsive`.
     - `render(frame: Frame) -> str` fills slots into a pre-vetted template,
       respecting locale and number/date formatting (use `babel` if present;
       otherwise stdlib `datetime`+`locale`).
     - Localisation hooks: each frame has a translation key; if step I shipped,
       optionally route through translation_service.
   - `nlg/extractive_summarizer.py`:
     - `summarise(text: str, *, max_sentences: int = 5) -> str` — TextRank-style
       extractive summariser; **no LLM call**; pure Python with `networkx` for
       the graph + a simple TF-IDF sentence similarity.
     - Add `networkx>=3.0` to `backend/requirements.txt` (likely already a
       transitive dep; check before adding).
2. Wire into product surfaces:
   - HR command center exec summary card → use `data_to_text.summarise_kpis`
     with `audience='exec'`.
   - Case alerts feed → emit frame-based reports for the four registered event
     types.
   - Policy viewer → "TL;DR" panel using `extractive_summarizer.summarise` on the
     active policy document.
3. Frontend:
   - Update `frontend/src/features/hr/command-center/` to read the new NLG
     endpoints.
   - New endpoint: `GET /api/hr/{company_id}/exec-summary` returning the
     data-to-text output.
   - New endpoint: `GET /api/policies/{policy_id}/tldr` returning the extractive
     summary.
   - Register both in a new router `backend/app/routers/nlg.py`.
4. Tests:
   - `backend/tests/test_nlg_data_to_text.py` — snapshot test on a 6-KPI fixture
     for each audience; anomaly-leads-first ordering verified.
   - `backend/tests/test_nlg_frame_based.py` — each registered frame renders
     correctly; missing slot raises typed error; locale variants render.
   - `backend/tests/test_nlg_extractive.py` — known input/output on a small
     corpus; sentence ordering is preserved relative to source where ties.
   - `backend/tests/test_nlg_router.py` — endpoint auth + payload.
   - Determinism test: each function called twice on identical input returns
     identical bytes.

### Design notes
- **Three NLG approaches, three distinct guarantees:**
  - Data-to-text: deterministic, auditable, no model fees.
  - Frame-based: deterministic, schema-validated, ideal for incident reports
    where wording precision matters for legal / compliance reasons.
  - Extractive: deterministic, runs on CPU, no PII leak risk.
- All three are LLM-free by design. That is Parker's whole point on Page 2:
  classical NLG is often sufficient and is always cheaper.
- The exec summary today (if it exists at all) is likely either hardcoded or
  Claude-generated. The Claude-generated version is fine for now — gate the
  swap behind an env flag `NLG_EXEC_SUMMARY_PROVIDER=data_to_text|llm` so the
  rollback is one env change.

### Out of scope
- The other 11 NLG approaches Parker lists (template, rule, hybrid, grammar,
  decision-tree, abstractive, graph-based, ontology, chunk-and-merge,
  lexicon-driven, narrative-planning). They can be added later under the same
  `nlg/` package.

### Acceptance criteria
- pytest + tsc both pass.
- All three NLG functions are LLM-free (assert in tests: no openai/anthropic
  call is made during these unit tests, even with mocking).
- Snapshot tests pass and lock down the deterministic outputs.
- Frontend exec summary renders the data-to-text output behind the env flag.
- Policy TL;DR renders the extractive summary on a 40-page fixture policy.

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-J-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-J-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/J/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step J RESULT — NLG variety (data-to-text, frame-based, extractive)

_Run: run-20260530-174625 | Branch: audit/parker-step-J-nlg-variety_

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
git push -u origin audit/parker-step-J-nlg-variety
gh pr create \
  --title "audit(parker-J): nlg-variety" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/J/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/J/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

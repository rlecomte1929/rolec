# Step I: Neural translation layer (DeepL Pro + NLLB-200)

You are executing **step I of 10** in the automated Parker-framework audit pipeline
for ReloPass. This pipeline implements the strategic recommendations from
`audit/parker-framework-audit.md` (root of the `rolec` repo).

**Pipeline run id:** `run-20260530-174625`
**Pipeline base SHA (main at run start):** `81d98bc8eb65e8f794d0a6f2c517cb81a5762a6e`
**Your slug:** `translation`
**Your branch (create it if not yet on it):** `audit/parker-step-I-translation`

---

## STAGE 1 — Read context (non-negotiable, do not skip)

1. Read `audit/parker-framework-audit.md` — section 2 (gap analysis) for the strategic
   intent, and section 4 prompt **I** for the original sketch of this task.
2. Read `audit/parker-pipeline/STATE.json` — confirm current_step is `I` and that
   prior step statuses are what you expect.
3. Read `audit/parker-pipeline/runs/run-20260530-174625/I/PREREQUISITES.md` — auto-generated;
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
`audit/parker-pipeline/runs/run-20260530-174625/I/UI-PROPOSAL.md` containing:

- **Purpose**: 2-sentence description of the user job to be done.
- **Info architecture**: route placement, who can access, what's hierarchically
  above/below.
- **Reused components**: list with file paths.
- **New components**: list with rationale per item.
- **Closest existing analogue**: file path to a current page this new surface
  mimics. This is the single most important field.
- **Open questions**: anything Romain needs to weigh in on.

Then write `audit/parker-pipeline/runs/run-20260530-174625/I/BLOCKED.md` with the
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

Write `audit/parker-pipeline/runs/run-20260530-174625/I/PLAN.md` containing:

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

1. Write `audit/parker-pipeline/runs/run-20260530-174625/I/BLOCKED.md` explaining:
   - What blocks the step.
   - Which upstream step (if any) is responsible.
   - What Romain (the human) needs to do before this step can resume.
2. Stop. Do not create a branch, do not commit.

## STAGE 4 — Create the branch

If STAGE 3 cleared and you're still on `main`:

```bash
git checkout -b audit/parker-step-I-translation
```

Commit work in logical chunks. Use commit messages of the form:

```
audit(parker-I): translation: <one-line summary>

<optional body explaining the rationale>
```

---

## Task body — step I

**UI impact:** Minimal. One small wrapper component `<TranslatedText>` that
inlines into existing markup, plus a single `preferred_language` field added to
the existing employee settings page. No new pages, no new top-level routes.
Reuses antigravity primitives and the existing settings page layout. Does NOT
require UI-PROPOSAL.md.

Add a neural translation layer so policy summaries, supplier briefings, and case
communications can be served in the employee's preferred language. Route between
DeepL Pro (subscription, high quality, low volume) and NLLB-200 (self-hosted, high
volume, cost-sensitive). Relocation is intrinsically multilingual — this closes a
strategic coverage gap.

### Prerequisites from prior steps

**Soft dependency on step D** (for prompt-routed translation prompts).
**Soft dependency on step G** (for cost/CO₂ accounting per translation).

Read these if present:
- `audit/parker-pipeline/runs/<RUN_ID>/D/RESULT.md` — to register translation in the
  prompt registry under the canonical task_key.
- `audit/parker-pipeline/runs/<RUN_ID>/G/RESULT.md` — to ensure translation calls
  flow `feature_key='translation'` through the trace logger.

If either is absent, fall back to direct router integration and static prompts.
Note this clearly in PLAN.md.

### Source material
- `backend/relopass/llm/router.py` — routing pattern.
- `backend/app/services/policy_assistant_rag_engine.py` — RAG pipeline pattern.
- `frontend/src/features/journey/` — employee journey wizard where translated
  outputs surface.
- `audit/parker-framework-audit.md` section 2 (W8, table in 2.4) and section 4,
  Prompt I.

### Concrete deliverables

1. Add `deepl>=1.18` to `backend/requirements.txt` (DeepL official SDK). Document
   the NLLB-200 deployment path in the ADR — likely Hugging Face Inference
   Endpoints for the open-source side, with a Modal or Replicate fallback. Do not
   add a heavy local-inference dependency to backend/requirements.txt.
2. ADR at `audit/adr/adr-002-translation-routing.md` documenting:
   - Quality vs cost tradeoff for DeepL Pro vs NLLB-200.
   - Language pair coverage and fallback rules.
   - Privacy posture: which strings may leave the EU (relevant for GDPR).
3. Migration `supabase/migrations/<timestamp>_translation_cache.sql`:
   - Table `translation_cache(
       id uuid pk,
       source_hash text not null,                  -- sha256 of (text, src, tgt, domain)
       source_text text not null,
       source_lang char(5) not null,               -- BCP-47, e.g. 'en-US'
       target_lang char(5) not null,
       domain text,                                -- 'policy'|'comm'|'supplier'|'ui'
       provider text not null,                     -- 'deepl'|'nllb'
       model_version text,
       translated_text text not null,
       quality_score numeric,
       cost_usd numeric,
       translated_at timestamptz default now()
     )`.
   - Unique on `source_hash`.
   - Index on `(target_lang, domain, translated_at desc)`.
   - **RLS enabled**: SELECT for authenticated; INSERT for the service role only.
     `REVOKE ALL ... FROM anon`.
4. Create `backend/app/services/translation_service.py`:
   - `translate(text: str, src: str, tgt: str, *, domain: str,
     quality_tier: Literal['fast', 'premium']) -> Translation` — returns
     `Translation(text, provider, model_version, cost_usd, cache_hit)`.
   - Router decision: `quality_tier='premium' OR len(text) < 500` → DeepL Pro;
     otherwise NLLB-200. Override with env var `TRANSLATION_FORCE_PROVIDER` for
     emergencies.
   - DeepL adapter (`backend/app/services/translation_deepl.py`) — wraps the
     official SDK, respects rate limits, handles glossaries (none initially).
   - NLLB adapter (`backend/app/services/translation_nllb.py`) — calls the
     hosted endpoint via HTTP. If env var `TRANSLATION_NLLB_ENDPOINT` is unset,
     return a structured error so the router can fall back to DeepL.
   - Trace every call through `ai_trace_logger` with `feature_key='translation'`
     and the cost/cost_usd field (so G's rollups work).
5. Wire into the journey flow:
   - Add `preferred_language` column to `employee_assignments` (or read from an
     existing field — check the schema first).
   - In the journey wizard, surface translated content for keys: case summary,
     next-steps, supplier briefing. Translation is opt-in via a toggle in
     employee settings.
6. Backend route `backend/app/routers/translation.py`:
   - `POST /api/translate` — body `{text, src, tgt, domain, quality_tier}`.
     Auth: session-token. Rate limit: 60/minute/user via slowapi.
   - Register in `backend/app/main.py`.
7. Frontend hook `frontend/src/api/translation.ts` and a `<TranslatedText>`
   component that fetches and renders translations with a small "translated" badge.
8. Tests:
   - `backend/tests/test_translation_service.py` — router decision rules, cache
     hit/miss, env var override.
   - `backend/tests/test_translation_deepl.py` and `test_translation_nllb.py` —
     adapter contracts with mocked HTTP responses.
   - `backend/tests/test_translation_router.py` — auth, rate limit (set
     `RELOPASS_DISABLE_RATE_LIMITS=1` per CLAUDE.md for the rest of the suite).
   - Round-trip preservation test: EN → DE → EN preserves entity names (company
     names, person names, addresses). This is the standard quality smoke test for
     translation pipelines.
   - Frontend snapshot test for `<TranslatedText>`.

### Design notes
- Translation cache is critical for cost. The same policy summary will be
  translated by hundreds of employees in a company; cache on the canonical hash.
- DeepL has stronger quality for European pairs; NLLB has wider coverage. Encode
  this in the routing decision: short strings → DeepL, long strings or rare
  pairs → NLLB.
- For NLLB hosting: do not vendor weights into the repo. Use HF Inference
  Endpoints; document the endpoint URL via env var and surface its health on the
  admin dashboard.
- Translation strings inside the product UI itself (i18n bundles) are NOT in
  scope here — they're a separate i18n task. This step is for **document content**
  translation (policies, summaries, communications).

### Out of scope
- Real-time chat translation.
- Speech translation.
- Glossaries for company-specific terminology.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies; cache table enforces uniqueness on `source_hash`.
- ADR exists and links to D's and G's RESULT.md if relevant.
- `POST /api/translate` returns a Translation with cache_hit=false the first time
  and cache_hit=true the second time (verify with a fixture).
- Round-trip EN→DE→EN preserves entity names (test it on a known fixture).

---

## STAGE 5 — Closeout (required artifacts before you stop)

When you believe the work is done, do every item below. The pipeline orchestrator
will refuse to mark this step complete if any are missing.

### 5.1 Run the full validation locally

```bash
cd backend && pytest -q 2>&1 | tee /tmp/parker-I-pytest.log
cd ../frontend && npx tsc --noEmit 2>&1 | tee /tmp/parker-I-tsc.log
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

Write `audit/parker-pipeline/runs/run-20260530-174625/I/RESULT.md` with **every** section
below. Downstream steps will read this — be exact and unambiguous.

```markdown
# Step I RESULT — Neural translation layer (DeepL Pro + NLLB-200)

_Run: run-20260530-174625 | Branch: audit/parker-step-I-translation_

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
git push -u origin audit/parker-step-I-translation
gh pr create \
  --title "audit(parker-I): translation" \
  --body-file audit/parker-pipeline/runs/run-20260530-174625/I/RESULT.md \
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
1. Read `audit/parker-pipeline/runs/run-20260530-174625/I/RESULT.md`.
2. Review the PR.
3. Either merge or request changes.
4. Run `./audit/parker-pipeline/pipeline.sh next` to advance.

If something prevented you from completing — even partially — write what's missing
into RESULT.md under "Known gaps / follow-ups", do **not** mark the step done
yourself, and stop.

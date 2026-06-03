# Step D PLAN — Prompt registry + canary A/B

_Run: run-20260530-174625 | Branch: audit/parker-step-D-prompt-registry | Base SHA: 81d98bc8_

## Task understanding

System prompts live as Python string literals (`llm_policy_extractor.SYSTEM_PROMPT`,
`policy_assistant_rag_engine.SYSTEM_PROMPT`) — invisible to product, untraceable, not
A/B-testable. Step D ships a **prompt registry**: versioned prompts in a DB table, a typed
`get_active_prompt(task_key)` that performs a canary split, an admin API + page to
promote/canary/archive versions, and a refactor of the two existing consumers to read from
the registry. It is a **platform contract** — steps E/F/I depend on the schema and the
`ActivePrompt` shape, so they're documented exactly in RESULT.md. The seeded `version=1,
status='prod'` rows reproduce today's prompts byte-for-byte, and consumers **fall back to
their literal constants** whenever the registry is absent/empty, so nothing breaks before
the migration is applied.

## Upstream alignment

PREREQUISITES.md: **none** — D is independent. But it is contractual for E/F/I.

## Ground-truth reconciliation (audit sketch vs. actual code)

- **Consumers & task_keys.** Two real consumers exist:
  `llm_policy_extractor.extract_policy_with_llm` (task_key **`policy_extraction`**; model
  default `claude-sonnet-4-6`, `max_tokens=4096`, no temperature passed today) and
  `policy_assistant_rag_engine.answer_policy_question` (task_key
  **`policy_assistant_answer`**; `DEFAULT_MODEL=claude-sonnet-4-6`, `LlmRequest` defaults
  `temperature=0.0`, `max_tokens=500`). The audit's example task_keys
  (`policy_classification`, `mrz_extraction`, …) are **illustrative only** — the canonical
  set this step ships is `{policy_extraction, policy_assistant_answer}`.
- **`policy_assistant_answer` user message is assembled in code** from chunks/turns/context
  (`_build_user_message`) — not a flat `{{var}}` template. So its registry row has
  `user_template = NULL`; only `system_prompt`/`model`/`temperature`/`max_tokens` come from
  the registry. (`policy_extraction` does get a `{{truncated}}`/`{{document_text}}`
  template.)
- **`TraceSession` is not yet wired into the live assistant flow** (only the docstring +
  tests instantiate it; the rag engine uses `_write_audit`). `policy_assistant_traces` is a
  **legacy bootstrap table** created in `backend/database.py` (`CREATE TABLE IF NOT
  EXISTS`, TEXT columns) — NOT a Supabase migration table. So adding `prompt_version_id` /
  `canary_arm` is a legacy-DDL + insert change, not a `supabase/migrations` RLS table.
- **Frontend admin pages live in `frontend/src/pages/admin/`** (e.g. `AdminSuppliers.tsx`
  with `AdminLayout` + `RequireAdminRoute` + `ROUTE_DEFS`), **not** `features/admin/`. No
  antigravity `Table` primitive exists (only Alert/Badge/Button/Card/Container/Input/
  LoadingButton/ProgressBar/Select) — tables are plain styled markup. → **Deviation:** page
  goes at `frontend/src/pages/admin/AdminPrompts.tsx`, styled table, not
  `features/admin/prompts/PromptsPage.tsx`.

## File-by-file change list

**Backend**
- `supabase/migrations/20260601050000_prompt_registry.sql` (new) — `prompt_versions` +
  `prompt_routing` tables, RLS, indexes, seed v1 prod rows for both task_keys.
- `backend/app/services/prompt_registry.py` (new) — `ActivePrompt` dataclass;
  `get_active_prompt`, `render_user_message`, `list_versions`, `create_version`, `promote`,
  `set_canary_share`; pure `_pick_arm(canary_share, rng)`. Uses app `SessionLocal` raw SQL;
  returns `None` when the table is absent/empty (→ consumers fall back).
- `backend/app/services/llm_policy_extractor.py` (edit) — source system prompt + model +
  max_tokens from `get_active_prompt('policy_extraction')`, render user message via the
  template; fall back to the existing literals when registry returns `None`. Record
  `prompt_version_id`/`canary_arm` in the returned dict for attribution.
- `backend/app/services/policy_assistant_rag_engine.py` (edit) — source system prompt +
  model from `get_active_prompt('policy_assistant_answer')`; fall back to `SYSTEM_PROMPT`/
  `DEFAULT_MODEL`. Thread `prompt_version_id`/`canary_arm` into the result dict.
- `backend/app/services/ai_trace_logger.py` (edit) — `TraceSession` gains optional
  `prompt_version_id`/`canary_arm` (constructor defaults `None`) + a
  `set_prompt_attribution()` helper; both flow into the flush payload and `_write_to_db`.
- `backend/database.py` (edit) — add `prompt_version_id TEXT` / `canary_arm TEXT` to the
  `policy_assistant_traces` `CREATE TABLE` + idempotent `ALTER TABLE ADD COLUMN`;
  `insert_policy_assistant_trace` gains the two optional params.
- `backend/app/routers/admin_prompts.py` (new) — admin CRUD/promote routes.
- `backend/app/main.py` (edit) — import + `include_router(admin_prompts.router,
  prefix="/api/admin")`.

**Frontend**
- `frontend/src/pages/admin/AdminPrompts.tsx` (new) — admin table page.
- `frontend/src/App.tsx` (edit) — lazy import + `/admin/prompts` route under
  `RequireAdminRoute`.
- `frontend/src/navigation/routes.ts` (edit) — add `adminPrompts` route def (mirror
  `adminSuppliers`).
- `frontend/src/api/client.ts` (edit) — `promptsAPI` wrapper.

**Tests**
- `backend/tests/test_prompt_registry.py`, `backend/tests/test_admin_prompts_router.py`,
  `frontend/src/pages/admin/__tests__/AdminPrompts.test.tsx`.

## New tables and migration plan

`supabase/migrations/20260601050000_prompt_registry.sql`:
- `public.prompt_versions(id uuid pk default gen_random_uuid(), task_key text not null,
  version int not null, system_prompt text not null, user_template text, model_name text
  not null, temperature numeric not null default 0.0, max_tokens int not null default 1024,
  status text not null default 'draft', created_at timestamptz not null default now(),
  created_by uuid, notes text)`. `unique (task_key, version)`; **partial unique**
  `create unique index ... on prompt_versions(task_key) where status='prod'` (one prod per
  task — works on PG and SQLite).
- `public.prompt_routing(task_key text primary key, canary_share numeric not null default
  0.0)`.
- **RLS (hard gate)** on both: `enable row level security`; SELECT `authenticated`
  (`using(true)` — prompts are operational metadata, no PII); ALL `authenticated` write
  gated `public.is_admin()`; `service_role` ALL; `revoke all ... from anon`.
- **Seed**: `prompt_versions` v1 `status='prod'` for `policy_extraction` (system =
  extractor `SYSTEM_PROMPT`, template = the extractor user prompt with `{{truncated}}` /
  `{{document_text}}`, model `claude-sonnet-4-6`, max_tokens 4096, temperature 0.0) and
  `policy_assistant_answer` (system = rag `SYSTEM_PROMPT`, template NULL, model
  `claude-sonnet-4-6`, max_tokens 500, temperature 0.0). `prompt_routing` rows with
  `canary_share=0.0`. Idempotent guards + rollback. **Not applied** (review → MCP).

## New routes (all `is_admin` via `require_admin`, router prefix `/prompts` under `/api/admin`)

| Method | Path | Auth | Router |
|---|---|---|---|
| GET  | /api/admin/prompts | require_admin | admin_prompts.py |
| GET  | /api/admin/prompts/{task_key} | require_admin | admin_prompts.py |
| POST | /api/admin/prompts | require_admin | admin_prompts.py |
| POST | /api/admin/prompts/{version_id}/promote | require_admin | admin_prompts.py |
| POST | /api/admin/prompts/{task_key}/canary-share | require_admin | admin_prompts.py |

## ActivePrompt shape (contract for E/F/I)

`ActivePrompt(id: str, version: int, system_prompt: str, user_template: str|None,
model_name: str, temperature: float, max_tokens: int, canary_arm: 'prod'|'canary')`.
`get_active_prompt(task_key)` picks the prod row; with probability `canary_share` and a
`status='canary'` row present, serves the canary arm and sets `canary_arm='canary'`.
Returns `None` when no prod row / table absent.

## Tests

- `test_prompt_registry.py` — `_pick_arm` ~10% over 10k draws (chi-square within
  tolerance, seeded); `promote(v_new,'prod')` demotes prior prod to 'archived'; the partial
  unique index rejects a 2nd prod insert; `render_user_message` substitutes `{{x}}`;
  `get_active_prompt` returns `None` when table missing (consumer-fallback contract).
  Schema created via a SQLite-compatible fixture.
- `test_admin_prompts_router.py` — non-admin → 403; admin GET list 200; POST create draft
  201/200; promote happy path. Minimal FastAPI app mounting only the router, `require_admin`
  overridden.
- `AdminPrompts.test.tsx` — renders the table from a mocked API; clicking Promote calls the
  right endpoint.

## Risks and unknowns

- **Breaking the two consumers.** Mitigated: registry read is best-effort; `None` →
  literal-constant fallback; seed reproduces literals byte-for-byte. Snapshot test asserts
  identical parsed output before/after.
- **PG vs SQLite in tests.** Migration is PG-flavored; tests build a minimal SQLite schema.
  Partial unique index syntax is shared.
- **Legacy DDL edit (`database.py`).** Additive columns only (`ADD COLUMN IF NOT EXISTS` +
  optional insert params); no behavior change for existing callers.
- **Registry DB vs legacy DB.** `prompt_versions` lives in the app DB (`app/db.py`
  SessionLocal); consumers are in `app/services` and already use app infra — consistent.

## Deviations from the original audit prompt (carried to RESULT)

1. Canonical task_keys are `policy_extraction` + `policy_assistant_answer` (the real
   consumers), not the sketch's illustrative names.
2. Frontend page at `pages/admin/AdminPrompts.tsx` (codebase convention) with a styled
   table (no antigravity `Table` primitive), not `features/admin/prompts/PromptsPage.tsx`.
3. `policy_assistant_answer` has `user_template=NULL` (message assembled in code).
4. `TraceSession`/`policy_assistant_traces` extension is a **legacy** DDL+insert change, not
   a Supabase RLS migration (the table is bootstrap-created in `database.py`).
5. Consumers **fall back to literals** when the registry is empty/absent (the migration is
   intentionally not applied yet) — required to not break prod pre-application.

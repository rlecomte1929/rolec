# Step D RESULT — Prompt registry + canary A/B

_Run: run-20260530-174625 | Branch: audit/parker-step-D-prompt-registry | Base SHA: 81d98bc8_

## What shipped

A versioned **prompt registry** so system prompts are no longer invisible Python
literals: they live in DB tables, are A/B-testable via a canary split, and are
managed through an admin API + page. The two real LLM consumers now read from the
registry, **falling back to their literal constants** when the registry is
absent/empty — so prod is unchanged until the migration is applied.

### Backend
- `supabase/migrations/20260601050000_prompt_registry.sql` — `prompt_versions` +
  `prompt_routing` with full RLS (SELECT `authenticated`, write gated to
  `public.is_admin()`, `service_role` ALL, `REVOKE ALL … FROM anon`), a partial
  unique index `(task_key) WHERE status='prod'` (one prod per task; PG+SQLite),
  and idempotent seed of v1 `prod` rows that reproduce today's literals
  **byte-for-byte** (asserted by tests). **Not applied** — left for human review →
  MCP `apply_migration` (history drift blocks `supabase db push`).
- `backend/app/services/prompt_registry.py` — `ActivePrompt` dataclass;
  `get_active_prompt` (canary split; `None` when table absent → consumer
  fallback); pure `_pick_arm`; `render_user_message` (`{{var}}`, no Jinja);
  admin helpers `list_versions` / `create_version` / `promote` / `set_canary_share`.
- `backend/app/services/llm_policy_extractor.py` — sources system prompt / model /
  max_tokens / user-template from `get_active_prompt('policy_extraction')`; env
  `RELOPASS_LLM_POLICY_MODEL` still wins; records `prompt_version_id` / `canary_arm`
  in the result dict.
- `backend/app/services/policy_assistant_rag_engine.py` — sources system prompt /
  model from `get_active_prompt('policy_assistant_answer')`; `model` param now
  `Optional[str]=None` (caller > registry > `DEFAULT_MODEL`); threads
  `prompt_version_id` / `canary_arm` into the result dict.
- `backend/app/services/ai_trace_logger.py` — `TraceSession` gains optional
  `prompt_version_id` / `canary_arm` + `set_prompt_attribution()`; both flow into
  the flush payload and the DB write.
- `backend/database.py` — additive `prompt_version_id` / `canary_arm` columns on
  the legacy `policy_assistant_traces` table (CREATE + idempotent SQLite/PG
  ADD COLUMN); `insert_policy_assistant_trace` gains the two optional params.
- `backend/app/routers/admin_prompts.py` + `backend/app/main.py` — 5 admin routes
  under `/api/admin/prompts`, all `require_admin`.

### Frontend
- `frontend/src/pages/admin/AdminPrompts.tsx` — per-task version table (status
  badges, Promote/Archive, canary-share control). Styled table (no antigravity
  `Table` primitive). `/admin/prompts` route under `RequireAdminRoute` in
  `App.tsx`; `adminPrompts` route def in `navigation/routes.ts`; `promptsAPI` in
  `api/client.ts`.

### Tests
- `backend/tests/test_prompt_registry.py` (14) — `_pick_arm` distribution,
  `render_user_message`, get/promote/partial-unique/None-fallback, **byte-for-byte
  seed guards** vs the two Python `SYSTEM_PROMPT` literals.
- `backend/tests/test_admin_prompts_router.py` (5) — 403 / list / create / promote /
  canary-share via TestClient with `require_admin` overridden + SQLite-patched
  registry.
- `frontend/src/pages/admin/__tests__/AdminPrompts.test.tsx` (2) — renders table,
  Promote calls the endpoint.

## Contract for downstream steps (E/F/I)

```
ActivePrompt(id: str, version: int, system_prompt: str, user_template: str|None,
             model_name: str, temperature: float, max_tokens: int,
             canary_arm: 'prod'|'canary')

get_active_prompt(task_key) -> ActivePrompt | None
```
- Canonical task_keys: **`policy_extraction`**, **`policy_assistant_answer`**.
- `get_active_prompt` returns the `prod` row; with probability
  `prompt_routing.canary_share` and a `status='canary'` row present, it serves the
  canary arm (`canary_arm='canary'`). Returns `None` when there's no prod row /
  the table is absent — **consumers MUST fall back to their literal constants.**
- `policy_assistant_answer` has `user_template = NULL` (user message assembled in
  code by `_build_user_message`).

## Verification

- `pytest tests/test_prompt_registry.py tests/test_admin_prompts_router.py
  tests/test_ai_trace_logger.py tests/test_llm_policy_extractor.py
  tests/test_policy_assistant_rag_a.py tests/test_policy_assistant_rag_b.py` →
  **77 passed**.
- `frontend: npx vitest run …/AdminPrompts.test.tsx` → **2 passed**;
  `npx tsc --noEmit` → clean; `npm run build` → built.
- Import-safety: registry + consumers + router import under `backend/.venv`
  (no ML extras).

## Deviations from the audit prompt (as planned)

1. Canonical task_keys are `policy_extraction` + `policy_assistant_answer` (the
   real consumers), not the sketch's illustrative names.
2. Frontend page at `pages/admin/AdminPrompts.tsx` with a styled table (no
   antigravity `Table` primitive), not `features/admin/prompts/PromptsPage.tsx`.
3. `policy_assistant_answer` has `user_template=NULL` (message assembled in code).
4. `TraceSession` / `policy_assistant_traces` extension is a **legacy** DDL+insert
   change (bootstrap table in `database.py`), not a Supabase RLS migration.
5. Consumers fall back to literals when the registry is empty/absent (migration
   intentionally not applied yet) — required to not break prod pre-application.

## Not done (by design)
- Migration **not applied**. Apply via MCP `apply_migration` after review.
- `TraceSession` is still not wired into the live RAG flow (pre-existing); the
  attribution plumbing is ready for whoever wires it.

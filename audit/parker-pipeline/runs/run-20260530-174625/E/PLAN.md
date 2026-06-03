# Plan — step E (RLHF-lite preference dataset from Notion Human Review)

_Branch: `audit/parker-step-E-rlhf-lite` · base SHA `81d98bc8`_

## Task understanding

Close the loop between Notion's Human Review queue and model quality. When Romain
approves / rejects / edits an AI output during a review session, that verdict is
POSTed to a new `POST /api/ai/feedback` endpoint and stored in a new
`ai_human_feedback` table, attributed to the prompt-registry version/arm that
served the original request (via the trace). A `preference_dataset_builder`
service turns those verdicts into DPO-style `{prompt, chosen, rejected}` pairs and
per-version win rates (Wilson 95% CI). A CLI exports the pairs as JSONL for offline
fine-tuning experiments; the admin prompts page (Step D) gains a win-rate column.
**No training run** — the deliverable is the dataset and the loop.

## Upstream alignment (Step D — `D/RESULT.md`)

- **`prompt_versions`** — PK `id uuid` (`gen_random_uuid()`), `task_key text`,
  `version int`, `status` ∈ draft/canary/prod/archived. My `ai_human_feedback.prompt_version_id`
  is `uuid` with a real FK → `prompt_versions(id)` (acceptance wants this enforced).
- **Canonical task_keys**: `policy_extraction`, `policy_assistant_answer`. Win-rate
  aggregation joins feedback → prompt_versions for task_key.
- **`ActivePrompt`** carries `id` (version id) + `canary_arm` ('prod'|'canary'); D's
  consumers thread `prompt_version_id` / `canary_arm` into the trace.
- **`policy_assistant_traces`** — D extended it with `prompt_version_id TEXT` +
  `canary_arm TEXT`. **Ground truth: this is a legacy bootstrap table in
  `backend/database.py`, `id TEXT PRIMARY KEY`** — NOT a uuid, NOT a Supabase
  migration. So `ai_human_feedback.trace_session_id` is `text` (matches the trace
  PK type), and the feedback row's attribution is derived by joining to this trace
  on POST. Traces are deliberately PII-free (only `query_hash`), so pair matching
  keys on `query_hash`, not the sketch's `(prompt_template_hash, input_hash)`.

## File-by-file change list

**Backend**
- `supabase/migrations/20260601060000_ai_human_feedback.sql` *(new)* — `ai_human_feedback`
  table + RLS + indexes (see migration plan).
- `backend/app/services/ai_feedback_service.py` *(new)* — `record_feedback(...)`:
  derive `prompt_version_id`/`canary_arm` from the trace, idempotent upsert on
  `(trace_session_id, reviewer_user_id)`.
- `backend/app/routers/ai_feedback.py` *(new)* — `POST /api/ai/feedback`
  (session-token auth via `get_current_user`).
- `backend/app/main.py` *(edit)* — import + `include_router(ai_feedback.router)`.
- `backend/app/services/preference_dataset_builder.py` *(new)* — `DPOPair`,
  `WinRate` dataclasses; `build_dpo_pairs(task_key, min_pairs=50)`;
  `compute_win_rates(task_key)` (Wilson 95% CI).
- `backend/app/routers/admin_prompts.py` *(edit)* — add
  `GET /api/admin/prompts/{task_key}/win-rates` (admin-only) → `compute_win_rates`.
- `backend/scripts/export_preference_dataset.py` *(new)* — CLI, writes JSONL,
  creates `preferences/` dir.
- `.gitignore` *(edit)* — add `preferences/`.

**Frontend**
- `frontend/src/api/client.ts` *(edit)* — `promptsAPI.winRates(taskKey)` + `WinRate` type.
- `frontend/src/pages/admin/AdminPrompts.tsx` *(edit, D's file)* — add a "Win rate"
  column per version (fetched per task_key). In-place column add — not a
  "significant" UI change per STAGE 1.5, so no UI-PROPOSAL.

**Tests**
- `backend/tests/test_ai_feedback_router.py` *(new)*
- `backend/tests/test_preference_dataset_builder.py` *(new)*
- `frontend/src/pages/admin/__tests__/AdminPrompts.test.tsx` *(edit)* — mock
  `winRates`, assert the column renders.

## New table + migration plan

`supabase/migrations/20260601060000_ai_human_feedback.sql`:

```
ai_human_feedback(
  id                uuid pk default gen_random_uuid(),
  trace_session_id  text not null,                  -- → policy_assistant_traces.id (legacy text PK; logical ref, no hard FK)
  reviewer_user_id  text not null,                  -- legacy users.id (string from session token)
  verdict           text not null check in ('approved','rejected','edited'),
  edited_output_json jsonb,
  comment           text,
  prompt_version_id uuid references public.prompt_versions(id),  -- FK enforced
  canary_arm        text,
  created_at        timestamptz not null default now(),
  unique (trace_session_id, reviewer_user_id)        -- idempotency
)
```
- Index `(prompt_version_id, verdict)` for win-rate aggregation.
- **RLS (hard gate):** `ENABLE ROW LEVEL SECURITY`; SELECT to `authenticated`
  gated `public.is_admin()`; INSERT/UPDATE to `service_role` only; service_role ALL;
  `REVOKE ALL ... FROM anon`. Writes go through the backend (service-role / session
  token), never the anon client.

## New routes

| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| POST | /api/ai/feedback | session-token (`get_current_user`) | `backend/app/routers/ai_feedback.py` |
| GET | /api/admin/prompts/{task_key}/win-rates | `require_admin` | `backend/app/routers/admin_prompts.py` |

## Tests (assertions)

- `test_ai_feedback_router.py` — (1) 401 without auth; (2) happy path: POST lands a
  row with `prompt_version_id`/`canary_arm` derived from a seeded trace; (3)
  idempotency: second POST same (trace, reviewer) updates not duplicates; (4) bad
  verdict → 422; (5) unknown trace → 404.
- `test_preference_dataset_builder.py` — (1) `edited` verdict → ≥1 pair with chosen
  = edited text; (2) cross-arm approved+rejected on same query_hash → 1 pair; (3)
  empty feedback → `[]` (no error); (4) `compute_win_rates` math + Wilson CI bounds
  within [0,1] and low ≤ rate ≤ high; (5) **FK to prompt_versions enforced**
  (SQLite `PRAGMA foreign_keys=ON`, bogus prompt_version_id → IntegrityError); (6)
  JSONL writer snapshot — one well-formed line per pair.

## Risks and unknowns

- **Traces are PII-free** → no stored output text for approved/rejected. DPO pairs
  therefore carry version references + any `edited_output_json` text; raw outputs
  are rehydrated downstream by `query_hash`. Documented as a deviation.
- **`policy_assistant_traces` is a legacy text-PK bootstrap table**, possibly absent
  on a brand-new DB before the backend boots → I use a logical ref (indexed text),
  not a hard FK, so the migration applies independently. The enforced FK is to
  `prompt_versions` (uuid), as the acceptance criteria require.
- **jsonb portability** (PG) vs text (SQLite): bind `edited_output_json` via
  SQLAlchemy `JSON(none_as_null=True)`; read path tolerates str-or-dict.
- Migration **not applied** (history drift; same posture as D) — left for human
  review → MCP `apply_migration`.

## Deviations from the original audit prompt (section 4, Prompt E)

1. `trace_session_id` / `reviewer_user_id` are `text` (legacy trace PK is text, users.id
   is a string), not `uuid`. The enforced FK is to `prompt_versions(id)` only.
2. Pair matching keys on `query_hash` (the existing anonymized trace key), since
   `(prompt_template_hash, input_hash)` columns do not exist and traces are PII-free.
3. Frontend column added to `pages/admin/AdminPrompts.tsx` (D's actual file), not the
   sketch's `features/admin/prompts/PromptsPage.tsx`.
4. Backend route (not a Supabase Edge Function) for `POST /api/ai/feedback`, per the
   dual-layer architecture.
5. Canonical task_keys are D's real ones (`policy_extraction`,
   `policy_assistant_answer`), not the sketch's `policy_classification`.

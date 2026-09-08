# AI Unit-Economics — Live Tracer Wiring

**Date:** 2026-06-03
**Status:** Approved (design)
**Related:** AIQ-754 (schema re-author, Done) and its named "Port the Parker-G admin
rollup endpoint" follow-up (already merged to `main`).

## Problem

Parker Step G shipped the full **read** side of AI unit economics:

- `public.policy_assistant_traces`, `ai_model_energy_profiles` (5 seed rows), and the
  `mv_ai_unit_economics` matview + `refresh_ai_unit_economics()` exist on prod
  (migration `20260605000000_ai_unit_economics_reauthor.sql`).
- The carbon estimator, feature-key set, rollup service, and the
  `GET /api/admin/ai-unit-economics` admin route are merged on `main`, registered in
  both `backend/main.py` and `backend/app/main.py`, with 29 passing tests.

But **nothing writes feature-tagged rows in the live path.** `TraceSession`
(`backend/app/services/ai_trace_logger.py`) is fully capable — it computes tokens, USD
cost, and estimated gCO₂e on `flush()` — yet the only references to it in non-test
backend code are inside its own docstring. The live entry point
`answer_policy_question` (`backend/app/services/policy_assistant_rag_engine.py:183`)
never constructs a tracer.

**Consequence:** `policy_assistant_traces` receives zero rows from production traffic,
so `mv_ai_unit_economics` and `GET /api/admin/ai-unit-economics` always return empty.
The endpoint is structurally correct but behaviorally dead.

## Goal

Wire the live tracer into the two highest-value AI surfaces so that real cost/carbon/
token data flows into `policy_assistant_traces` per `(customer_id, feature_key)`:

- `policy_assistant` — `answer_policy_question`
- `policy_extraction` — `extract_policy_with_llm`

## Key decisions

- **`customer_id = company_id`.** The rollup groups "per customer"; ReloPass's paying
  tenant is the company. `TraceSession` already defaults `customer_id` to `company_id`,
  so passing `company_id` is sufficient. (Not end-user granularity.)
- **Best-effort, never raises.** Tracing must never break the assistant or the
  extractor. All recording + `flush()` is wrapped so a failure is logged at debug and
  swallowed — identical to the existing audit-log and LangSmith sinks.
- **Surgical, no new abstraction.** Instrument each function in place. A shared
  decorator/wrapper is rejected: the two surfaces have different shapes (one uses the
  `LlmClient` abstraction and returns a dict; the other calls the raw Anthropic SDK and
  returns a `Message`), so a generic wrapper would leak both. YAGNI for two sites.

## Prerequisite blocker (must land first)

**Prod `policy_assistant_traces` is missing two columns the merged writer already
inserts.** `db.insert_policy_assistant_trace` (and `TraceSession.flush`) INSERT into a
column list that includes `prompt_version_id` and `canary_arm` (Parker Step D). But:

- The prod table is defined solely by migration `20260605000000_ai_unit_economics_reauthor.sql`,
  whose `CREATE TABLE` has only the 8 base columns + 6 Step G columns — **no Step D
  columns.**
- `backend/database.py` `init_db()` returns early on Postgres (~line 1186), so the
  SQLite-only `ALTER TABLE ... ADD COLUMN prompt_version_id/canary_arm` backfill at
  ~line 2480 **never runs on prod.**
- No other migration adds these columns to this table (`20260601060000_ai_human_feedback.sql`
  puts `prompt_version_id`/`canary_arm` on the *separate* `ai_human_feedback` table).

**Effect:** on prod, every `INSERT` would raise `UndefinedColumn`, get swallowed by the
best-effort `try/except`, and persist **zero rows** — so wiring the tracer would appear
to work in tests (SQLite has the columns) but write nothing in production. This is a
silent failure the existing 29 tests cannot catch because they run on SQLite.

**Fix:** a small additive, idempotent forward migration:

```sql
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS prompt_version_id TEXT;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS canary_arm TEXT;
```

Applied to prod via the Supabase MCP `apply_migration` (per the repo's history-drift
workaround — `supabase db push` is blocked). No new table, so the RLS hard-gates for new
tables don't apply; RLS is already enabled on the table. This migration must land (and be
applied to prod) before — or together with — the wiring, or the feature is dead on prod.

## Design

### 1. `policy_assistant` — `policy_assistant_rag_engine.py`

In `answer_policy_question`:

- Construct at the top (after input validation):
  `TraceSession(session_id=session_id, query=q, company_id=company_id, feature_key="policy_assistant")`.
- After the LLM call resolves, record the work the function already measures:
  - `tracer.record_retrieval(top_scores=..., latency_ms=...)` if scores are readily
    available; otherwise record a generic `retrieval` step with the chunk count. (No
    new retrieval plumbing — use what `policy_chunk_retriever.retrieve` already returns.)
  - `tracer.record_llm_call(model=model_used, input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"], latency_ms=latency_ms)`.
  - `tracer.set_prompt_attribution(prompt_version_id, canary_arm)`.
- `tracer.flush()` in a `finally` so it runs on every exit path (answer, refusal,
  exception).

**Known approximation:** on a validation-retry (`_call_with_retry`), the reported
`usage` reflects only the final attempt, so a retried call slightly under-counts tokens/
cost. Documented, not solved here (candidate follow-up).

### 2. `policy_extraction` — `llm_policy_extractor.py` + signature threading

- Add `company_id: Optional[str] = None` to **both**:
  - `extract_policy_with_diff(file_bytes, file_type, company_id=None)`
    (`policy_extractor.py:353`)
  - `extract_policy_with_llm(lines, company_id=None)`
    (`llm_policy_extractor.py:197`)

  Defaulted so the eval script (`backend/scripts/eval_llm_policy_extraction.py`) and
  existing tests keep working unchanged.
- Pass `company_id=policy.get("company_id")` from the live caller at
  `backend/main.py:13133`, through `extract_policy_with_diff` into
  `extract_policy_with_llm`.
- Inside `extract_policy_with_llm`, after the successful `messages.create`:
  - `tracer = TraceSession(session_id=None, query="<policy extraction>", company_id=company_id or "unknown", feature_key="policy_extraction")`.
  - `tracer.record_llm_call(model=model, input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens, latency_ms=call_latency_ms)`.
  - `tracer.set_prompt_attribution(prompt_version_id, canary_arm)`.
  - `tracer.flush()`.
  - Only on the success path (after a `tool_input` is obtained). Fallback/early-return
    paths (no key, SDK missing, API error) do not emit a trace — consistent with their
    "fell back to regex, no LLM cost incurred" semantics. The API-error path already has
    no usable `usage`.

Because `query` is hashed to `query_hash` and never stored raw, the placeholder query
string carries no document content (PII-safe).

### 3. Data flow

```
HR triggers extract-preview ──► main.py:13133
   policy = db.get_company_policy(policy_id)
   extract_policy_with_diff(data, file_type, company_id=policy["company_id"])
       └► extract_policy_with_llm(lines, company_id=...)
              messages.create(...) ──► message.usage
              TraceSession(feature_key="policy_extraction", company_id=...).flush()
                  └► db.insert_policy_assistant_trace(... feature_key, customer_id,
                       tokens_in, tokens_out, cost_usd_estimated, co2e_grams_estimated)
                          └► policy_assistant_traces  ──► mv_ai_unit_economics
                               ──► GET /api/admin/ai-unit-economics

Employee/HR asks the assistant ──► answer_policy_question(company_id, ...)
   TraceSession(feature_key="policy_assistant", company_id=...).flush() ──► (same sink)
```

### 4. Error handling

- `flush()` already swallows all exceptions internally and logs at debug.
- Wrap the construction + recording calls in each surface in a `try/except` (or rely on
  the `finally`+best-effort `flush`) so a tracer construction error cannot escape into
  the assistant/extractor return path.
- No behavior change to existing audit writes, session memory, LangSmith, or the regex
  fallback.

## Testing

Mirror the existing `backend/tests/test_trace_logger_carbon.py` pattern (fake `db`
capturing `insert_policy_assistant_trace` kwargs; carbon DB read monkeypatched to force
in-code defaults):

1. `test_answer_policy_question_writes_trace` — drives `answer_policy_question` with a
   fake `LlmClient` returning a known model + token usage; asserts one trace row with
   `feature_key="policy_assistant"`, `customer_id == company_id`, the right token counts,
   and `co2e_grams_estimated > 0`.
2. `test_answer_policy_question_trace_failure_is_swallowed` — fake db `insert` raises;
   `answer_policy_question` still returns a normal answer dict.
3. `test_extract_policy_with_llm_writes_trace` — fake Anthropic client returning a
   `Message` with `usage`; assert `feature_key="policy_extraction"`, `customer_id` from
   the threaded `company_id`, token counts, `co2e_grams_estimated > 0`.
4. `test_extract_policy_company_id_threads_through` — `extract_policy_with_diff(...,
   company_id="acme")` reaches the trace row as `customer_id="acme"`.
5. `test_extract_fallback_paths_emit_no_trace` — no API key / API error → regex
   fallback, zero trace rows.

Plus regression: existing `test_ai_trace_logger.py`, `test_trace_logger_carbon.py`,
`test_llm_policy_extractor.py`, `test_policy_assistant_rag_*.py`,
`test_admin_ai_unit_economics_router.py` all stay green.

## Verification

- **Prod schema (blocker):** before/after the migration, confirm via Supabase MCP that
  `public.policy_assistant_traces` has `prompt_version_id` and `canary_arm` columns
  (`select column_name from information_schema.columns where table_name =
  'policy_assistant_traces'`). The writer's full INSERT column list must be a subset of
  the prod columns.
- `cd backend && pytest` (targeted new tests first, then the affected suites). Note:
  SQLite tests pass regardless of the prod-column gap, so they do **not** validate the
  prerequisite — the MCP column check above is the real gate for prod.
- `cd frontend && npx tsc --noEmit` (no frontend change expected — sanity only).
- Manual sanity: after wiring + migration, a local `answer_policy_question` call should
  produce one row queryable via `GET /api/admin/ai-unit-economics`.

## Out of scope (separate follow-ups)

- `passport_ocr` / `passport_ocr_oss` instrumentation (different call structure).
- Nightly `pg_cron` refresh of `mv_ai_unit_economics` (commented snippet exists in the
  migration).
- Validation-retry token under-counting in `answer_policy_question`.
- A frontend admin panel consuming the endpoint (deferred per the router's own docstring).

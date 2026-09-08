# Step G PLAN — Carbon + per-customer AI unit economics

_Run: run-20260530-174625 | Branch: audit/parker-step-G-carbon-tco (from main @ 81d98bc8, independent)_

## Task understanding

Add an ESG + TCO unit-economics layer to the AI trace pipeline. Every LLM call should
carry (a) an estimated CO₂e value (tokens → kWh → gCO₂e) and (b) a customer + feature
attribution, so we can roll up **cost-per-customer** and **carbon-per-customer per
feature**. This is the Framework-4 "environmental impact + TCO" defensibility layer for
the YC / Series-A pitch. Backend + JSON endpoint only — the admin panel is explicitly
deferred to a follow-up prompt per Romain's UI-reuse mandate.

## Upstream alignment (ground truth from prior RESULTs / code)

- **No formal prerequisites** (PREREQUISITES.md: independent). But G attaches to D's and
  F's actual artifacts:
- **Step D** (`D/RESULT.md`): the active traces table is **`policy_assistant_traces`**, a
  **legacy bootstrap table in `backend/database.py`** (id `TEXT` pk, `company_id TEXT`,
  `steps_json`, `total_latency_ms`, `fallback_triggered`, `prompt_version_id`,
  `canary_arm`, `created_at TEXT`) — **not** a Supabase RLS migration. D added its
  attribution columns via `database.py` (CREATE + idempotent ADD COLUMN) and extended
  `db.insert_policy_assistant_trace(...)`. **G follows the same dual-write pattern.**
  `TraceSession` (in `ai_trace_logger.py`) is **not yet constructed by any live flow**
  (D RESULT "Not done": unwired plumbing) — confirmed by grep: the only `TraceSession(`
  references are in the module docstring.
- **Step F** (`F/RESULT.md`): documented OSS passport cost model
  (`GPT4O_COST_PER_EXTRACTION_USD=0.00765`, `OSS_COST_PER_EXTRACTION_USD=0.00040`) and the
  reusable pattern I mirror here: **portable PG+SQLite rollup over the base table** (the
  admin route reads the base table, not the matview, so it's SQLite-testable), **matview
  off the request path** with `REVOKE` (matviews can't carry RLS), and **best-effort
  lazy DB writes that never raise**. F's `passport_ocr` becomes a `feature_key` here.
- **Router** (`relopass/llm/router.py`): reuse `usd_cost(model, tokens_in, tokens_out)`
  (reads `costs.yaml`, per-million pricing) for the cost number. It raises
  `LLMRoutingError` for models absent from `costs.yaml`; flush guards that → cost 0.0.

## File-by-file change list

| File | Change |
|------|--------|
| `supabase/migrations/20260601080000_ai_unit_economics.sql` | **new** — `ai_model_energy_profiles` table + seed (RLS hard gate); idempotent `ADD COLUMN` on `policy_assistant_traces`; index; `mv_ai_unit_economics` matview + unique idx + REVOKE + refresh fn. NOT applied. |
| `backend/app/services/ai_feature_keys.py` | **new** — `FeatureKey = Literal[...]` + string constants + `ALL_FEATURE_KEYS`. |
| `backend/app/services/ai_carbon_estimator.py` | **new** — `EnergyProfile`, in-code seed defaults (= migration seed), in-process cache, `estimate_co2e_grams(...)`, DB read best-effort, global-default fallback + warn. |
| `backend/app/services/ai_unit_economics.py` | **new** — `compute_unit_economics_rollup(...)` portable base-table aggregation (mirrors F's `compute_shadow_rollup`). |
| `backend/app/services/ai_trace_logger.py` | edit — `TraceSession` gains required `feature_key` + optional `customer_id`; `flush()` computes co2e/cost/token totals over `llm_call` steps and persists the new columns. |
| `backend/database.py` | edit — add 6 carbon/attribution columns to the `policy_assistant_traces` bootstrap (CREATE + idempotent ADD COLUMN, SQLite+PG); extend `insert_policy_assistant_trace(...)`. |
| `backend/app/routers/admin_ai_unit_economics.py` | **new** — `GET /api/admin/ai-unit-economics`, `require_admin`. |
| `backend/app/main.py` | edit — import + `include_router(admin_ai_unit_economics.router)`. |
| `backend/tests/test_ai_carbon_estimator.py` | **new** |
| `backend/tests/test_trace_logger_carbon.py` | **new** |
| `backend/tests/test_admin_ai_unit_economics_router.py` | **new** |

## New tables and migration plan (`20260601080000_ai_unit_economics.sql`, NOT applied)

1. **`public.ai_model_energy_profiles`** (genuinely new → full RLS hard gate):
   `model_name text pk`, `joules_per_input_token numeric not null`,
   `joules_per_output_token numeric not null`, `region_gco2_per_kwh numeric not null`,
   `source_url text`, `updated_at timestamptz not null default now()`.
   - Seed: `claude-sonnet-4-6`, `claude-haiku-4-5`, `gpt-4o`, `gpt-4o-mini`,
     `text-embedding-3-small` with cited public estimates (ML CO₂ Impact / Patterson et
     al. / vendor sustainability reports — values are rough, framework > precision).
   - RLS: `ENABLE ROW LEVEL SECURITY`; `SELECT TO authenticated`; write (`ALL`) gated to
     `public.is_admin()`; `service_role ALL`; `GRANT SELECT ... authenticated`;
     **`REVOKE ALL ... FROM anon`**.
2. **`policy_assistant_traces`** (exists; ALTER only — no new-table hard gate):
   `ADD COLUMN IF NOT EXISTS` → `co2e_grams_estimated numeric`,
   `cost_usd_estimated numeric`, `tokens_in integer`, `tokens_out integer`,
   `customer_id text`, `feature_key text`. Index `(customer_id, feature_key, created_at)`.
   - Header comment notes the dependency: table is bootstrapped by `database.py init_db()`;
     apply after the backend has booted at least once (prod already has it).
3. **`public.mv_ai_unit_economics`** matview: `GROUP BY (week, customer_id, feature_key)`
   → `total_cost_usd, total_tokens_in, total_tokens_out, total_co2e_grams, n_calls`.
   Unique index on `(week, customer_id, feature_key)` for `REFRESH … CONCURRENTLY`.
   `REVOKE ALL FROM anon` + `REVOKE ALL FROM authenticated` (matviews can't carry RLS;
   admin-only via the route's `is_admin()` gate, F precedent). `refresh_ai_unit_economics()`
   `SECURITY DEFINER` → `service_role`.

## New routes

| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET | `/api/admin/ai-unit-economics?customer_id&from&to&feature_key` | `require_admin` (is_admin allowlist) | `backend/app/routers/admin_ai_unit_economics.py` |

Reads the **base table** (portable PG+SQLite GROUP BY over `customer_id, feature_key`,
date-range filtered), not the matview — so it's testable under SQLite (no matview support).

## Configuration / env vars
- None new. (Energy profiles live in the DB table + in-code seed defaults; cost in `costs.yaml`.)

## Tests
- `test_ai_carbon_estimator.py` — known (model, tokens_in, tokens_out) → expected gCO₂e
  computed by hand from a seed profile (happy); unknown model → global-default fallback +
  warning logged (failure mode); in-process cache returns same object (edge).
- `test_trace_logger_carbon.py` — `TraceSession(feature_key=…, customer_id=…)` +
  `record_llm_call` + `flush()` persists `co2e_grams_estimated/cost_usd_estimated/
  tokens_in/tokens_out/customer_id/feature_key` (happy, via a fake `db` capturing kwargs);
  unknown model still flushes with default-based co2e + warns (failure); `flush()` never
  raises when the db write blows up (edge).
- `test_admin_ai_unit_economics_router.py` — in-memory SQLite seeded with traces;
  `require_admin` override; asserts rollup totals per (customer, feature), date filter,
  `customer_id` filter, empty range zeroed (auth/schema/filter).

## Risks and unknowns
- **Matview depends on a legacy bootstrap table.** Mitigated: ALTER uses
  `IF NOT EXISTS`; migration header documents the apply-order dependency; migration is
  left for human MCP review (not auto-applied), and prod already has the table.
- **`customer_id` typed `text` not `uuid`** (deviation, below) to match the existing
  `company_id text` / `id text` typing and keep the SQLite-tested rollup portable.
- **`usd_cost` raises for models absent from `costs.yaml`** (e.g. the embedding model).
  flush guards it → cost 0.0, debug-logged; carbon still computes from energy profiles.
- **Carbon numbers are approximate** — stated in the seed `source_url` + RESULT; precision
  is intentionally rough, the framework is the deliverable.

## Deviations from the original audit prompt
1. **No live call sites to update.** `TraceSession` is unwired (D left it as plumbing), so
   "update every existing call site to pass `feature_key`" has zero targets today. Instead
   `feature_key` becomes a **required** `TraceSession` constructor arg (enforces "no bare
   `TraceSession()`" forward), and `ai_feature_keys.py` ships the `Literal` keys for when
   the wiring lands.
2. **Trace columns added via `database.py` bootstrap** (+ idempotent ALTER in the Supabase
   migration for the matview's sake), mirroring D's deviation #4 — the traces table is a
   legacy bootstrap table, not a Supabase-migrated one.
3. **6 trace columns, not 3.** The sketch lists `co2e_grams_estimated, customer_id,
   feature_key`. The matview/rollup also needs `cost_usd_estimated, tokens_in, tokens_out`
   materialized as columns so the GROUP BY is cheap and **portable to SQLite** (can't parse
   `steps_json` in portable SQL). Same philosophy as F (materialize aggregatable numerics).
4. **`customer_id text`, not `uuid`** — matches existing `company_id`/`id` TEXT typing.
5. **Admin route reads the base table, not `mv_ai_unit_economics`** — matviews aren't
   supported in SQLite and can't carry RLS; the matview stays a PG BI convenience off the
   request path (F precedent).
6. **Small `ai_unit_economics.py` service** holds the rollup (route stays thin), mirroring
   F's `passport_ocr_oss.compute_shadow_rollup`.
7. **Frontend deferred** — UI impact "None" per task body; panel ships via
   `prompts/followups/G-frontend.md`. No frontend snapshot test here.

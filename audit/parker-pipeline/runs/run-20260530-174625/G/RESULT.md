# Step G RESULT — Carbon + per-customer AI unit economics

_Run: run-20260530-174625 | Branch: audit/parker-step-G-carbon-tco_

## Summary
Adds the Framework-4 ESG + TCO defensibility layer: every AI trace now carries a
required `feature_key` plus `customer_id` attribution and, on flush, an estimated CO₂e
value, USD cost, and token totals summed across its `llm_call` steps. A new pure-Python
carbon estimator (`ai_carbon_estimator`) turns tokens → kWh → gCO₂e using per-model
energy profiles (DB-backed with in-code seed defaults, so it works in CI with no ML
deps and before the migration is applied). An admin-only JSON rollup endpoint
(`GET /api/admin/ai-unit-economics`) aggregates cost + carbon per (customer, feature)
over an optional date range. Backend + endpoint only — the admin panel UI is deferred to
the follow-up prompt `prompts/followups/G-frontend.md`.

## Files changed
```
 backend/app/main.py                                |   2 +
 backend/app/routers/admin_ai_unit_economics.py     |  41 +++++
 backend/app/services/ai_carbon_estimator.py        | 168 +++++++++++++++++++++
 backend/app/services/ai_feature_keys.py            |  31 ++++
 backend/app/services/ai_trace_logger.py            |  70 ++++++++-
 backend/app/services/ai_unit_economics.py          | 121 +++++++++++++++
 backend/database.py                                |  58 ++++++-
 backend/tests/test_admin_ai_unit_economics_router.py | 158 +++++++++++++++++
 backend/tests/test_ai_carbon_estimator.py          |  71 +++++++++
 backend/tests/test_trace_logger_carbon.py          | 109 +++++++++++++
 supabase/migrations/20260601080000_ai_unit_economics.sql | 124 +++++++++++++
 11 files changed, 950 insertions(+), 3 deletions(-)
```
(Diffstat is against the pipeline base `feature/sec-004-rate-limit-coverage`, the branch
all Parker steps fork from — local `main` has diverged and is not the base for this PR.)

## Tests added
- `backend/tests/test_ai_carbon_estimator.py` — pure tokens→kWh→gCO₂e math; known-model
  seed-default path (gpt-4o 1000/500 → 0.088889 g); embedding model has no output cost;
  unknown model → global default + "no energy profile" warning; zero tokens → 0.0 g;
  in-process cache served once (no second DB lookup). DB read is monkeypatched out.
- `backend/tests/test_trace_logger_carbon.py` — `TraceSession.flush()` persists summed
  cost ($0.0075 for gpt-4o 1000/500), carbon (0.088889 g) and token totals via
  `insert_policy_assistant_trace`; `customer_id` defaults to `company_id`; unknown model
  flushes with cost 0.0 + carbon > 0 + warning; flush never raises when the DB write
  blows up; a trace with no `llm_call` yields zeroed economics.
- `backend/tests/test_admin_ai_unit_economics_router.py` — drives the route via
  `TestClient` over an in-memory SQLite traces table; non-admin → 403; rollup groups into
  3 (customer, feature) buckets with correct n_calls/tokens/cost; grand totals; customer
  filter; feature filter; inclusive date-range filter; empty range → zeroed rows/totals.

## Test result
- pytest: **16 passed, 0 failed** for the three Step G files
  (`test_ai_carbon_estimator.py test_trace_logger_carbon.py test_admin_ai_unit_economics_router.py`).
- tsc: **pass** (no frontend changes in this step; `npx tsc --noEmit` clean).
- Note: a full `pytest backend/tests/` collection shows 10 pre-existing collection
  errors in unrelated modules (`test_admin.py`, `test_collaboration.py`, etc.). These are
  `from main import app` relative-import failures that exist on the base branch and are
  independent of Step G — none of the affected modules are touched here.

```
................                                                         [100%]
16 passed in 0.35s
```

## Migration applied?
- File: `supabase/migrations/20260601080000_ai_unit_economics.sql`
- **NOT applied.** Left for human review → MCP `apply_migration` (remote history drift
  blocks `supabase db push`). The Python surfaces do not require it: `database.py`
  bootstraps the trace columns on SQLite/PG and the carbon estimator falls back to in-code
  seed profiles, so all code + tests run without the migration.
- RLS posture (per new table):
  - Table `public.ai_model_energy_profiles`: **RLS enabled** ✅. Policies:
    `ai_energy_authenticated_select` (SELECT TO authenticated), `ai_energy_admin_write`
    (FOR ALL USING/WITH CHECK `public.is_admin()`), `ai_energy_service_all` (service_role).
    `GRANT SELECT ... TO authenticated`; **`REVOKE ALL ... FROM anon`** ✅. Satisfies the
    CLAUDE.md hard gate.
  - `policy_assistant_traces`: pre-existing table — migration only `ADD COLUMN IF NOT
    EXISTS` (co2e/cost/tokens/customer_id/feature_key) + an index. No new RLS surface.
  - `mv_ai_unit_economics` (materialized view): matviews can't carry RLS, so
    **`REVOKE ALL ... FROM anon, authenticated`**; refresh via `refresh_ai_unit_economics()`
    SECURITY DEFINER granted to `service_role` only. The admin route reads the **base
    table** (portable PG+SQLite), not the matview, so no app surface depends on it.

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET    | /api/admin/ai-unit-economics | `require_admin` (is_admin) | backend/app/routers/admin_ai_unit_economics.py |

Query params: `customer_id`, `feature_key`, `from` (alias), `to` (alias). Returns
`{rows: [{customer_id, feature_key, n_calls, total_tokens_in, total_tokens_out,
total_cost_usd, total_co2e_grams}], totals: {...}, filters: {...}}`. Empty range → zeroed.

## New tables / schema changes
- `public.ai_model_energy_profiles` (new) — `model_name TEXT PK`,
  `joules_per_input_token NUMERIC`, `joules_per_output_token NUMERIC`,
  `region_gco2_per_kwh NUMERIC`, `source_url TEXT`, `updated_at TIMESTAMPTZ DEFAULT now()`.
  Seeded: claude-sonnet-4-6 (0.40/0.80/400), claude-haiku-4-5 (0.12/0.24/400),
  gpt-4o (0.40/0.80/400), gpt-4o-mini (0.12/0.24/400), text-embedding-3-small (0.05/0.00/400).
- `policy_assistant_traces` (altered) — added `co2e_grams_estimated NUMERIC/REAL`,
  `cost_usd_estimated NUMERIC/REAL`, `tokens_in INTEGER`, `tokens_out INTEGER`,
  `customer_id TEXT`, `feature_key TEXT` + index `idx_pa_traces_customer_feature_created`.
  Mirrored in `backend/database.py` bootstrap (idempotent additive backfill, SQLite + PG).
- `mv_ai_unit_economics` (new materialized view) — grouped by
  (`date_trunc('week', created_at)`, `customer_id`, `feature_key`) → n_calls,
  total_cost_usd, total_tokens_in/out, total_co2e_grams; unique index; refreshed by
  `refresh_ai_unit_economics()`.

## Configuration / env vars added
- None. Carbon profiles are data rows (DB seed + in-code defaults), not env vars.

## UI changes summary
- New routes added: none.
- New components added: none.
- Existing antigravity components reused: none (no frontend in this step).
- UI-PROPOSAL.md status: **deferred to follow-up prompt** (`prompts/followups/G-frontend.md`).
  The admin panel that consumes `GET /api/admin/ai-unit-economics` ships there.

## Deviations from the original audit prompt
1. **`TraceSession` is unwired** — grep found zero live construction sites (only the
   docstring example). So making `feature_key` a required constructor arg enforces "no
   bare `TraceSession()`" going forward without needing to update any call sites.
2. **Trace columns via `database.py` bootstrap + idempotent migration ALTER**, because the
   traces table is a legacy `database.py`-bootstrapped table (not a Supabase-migrated one).
   The migration's `ADD COLUMN IF NOT EXISTS` keeps prod in sync; the bootstrap keeps SQLite
   and fresh PG in sync without the migration.
3. **6 trace columns, not 3** — added `cost_usd_estimated`, `tokens_in`, `tokens_out`
   alongside `co2e_grams_estimated`/`customer_id`/`feature_key` so the rollup can GROUP BY
   portably (no per-row JSON parsing on the read path).
4. **`customer_id` is TEXT, not uuid** — matches the existing `company_id`/`id` TEXT typing
   on `policy_assistant_traces`; `customer_id` defaults to `company_id`.
5. **Admin route reads the base table, not the matview** — SQLite (CI/tests) has no
   matviews; the portable GROUP BY over the base table gives identical results and keeps
   the endpoint testable. The matview + refresh function remain for prod reporting scale.
6. **Carbon estimator is DB-independent** — in-code `_DEFAULT_PROFILES` + a global default
   mean estimates always resolve (with a warning for unknown models), so the feature works
   in CI and before the migration applies.
7. **Frontend deferred** — per the prompt, the admin panel ships via the follow-up.

## What downstream steps will need from this step
- **Carbon/cost per call**: `ai_carbon_estimator.estimate_co2e_grams(model, tokens_in,
  tokens_out)` returns gCO₂e (full precision; round at persistence). USD cost comes from
  the router's `costs.yaml` via `usd_cost(...)` (0.0 for unpriced models).
- **Feature keys are canonical**: the master cost/carbon dimension is `feature_key`. The
  canonical set as of this commit (`backend/app/services/ai_feature_keys.py`,
  `FeatureKey` Literal) is: `['policy_assistant', 'policy_extraction', 'passport_ocr',
  'passport_ocr_oss']`. Any new feature must add a member here and pass it to
  `TraceSession(..., feature_key=...)` (required arg).
- **Rollup access**: read AI unit economics via
  `ai_unit_economics.compute_unit_economics_rollup(customer_id=, feature_key=, from_ts=,
  to_ts=)` or the admin route `GET /api/admin/ai-unit-economics`.
- **D-column merge note**: this branch forked from the pre-D base, so `ai_trace_logger.py`
  and `database.py` here do NOT contain D's `prompt_version_id`/`canary_arm` columns. When
  D and G both merge, the two additive column sets must be reconciled (no overlap — purely
  additive on both sides).

## Known gaps / follow-ups
- **Frontend admin panel** — deferred to `prompts/followups/G-frontend.md`. It should
  consume `GET /api/admin/ai-unit-economics` and render per-customer cost + carbon per
  feature. (Map to a Notion AI Work Queue task when the follow-up is scheduled.)
- **Suggested pg_cron schedule** for the matview (add after the migration is applied via
  MCP; pg_cron must be enabled on the project):
  ```sql
  -- Refresh the AI unit-economics rollup nightly at 02:00 UTC.
  select cron.schedule(
    'refresh-ai-unit-economics',
    '0 2 * * *',
    $$ select public.refresh_ai_unit_economics(); $$
  );
  ```
- **Migration not applied** — `supabase/migrations/20260601080000_ai_unit_economics.sql`
  awaits human review → MCP `apply_migration` (history drift blocks `db push`).
- **Energy profiles are estimates** — seed J/token and 400 gCO₂e/kWh region intensity are
  defensible defaults, not measured values. Refine `ai_model_energy_profiles` rows as
  better per-model energy data becomes available (`source_url` column is there for it).

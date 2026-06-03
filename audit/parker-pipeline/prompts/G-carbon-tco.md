## Task body — step G

**UI impact:** None in this step. The admin panel for AI unit economics is
deferred to `prompts/followups/G-frontend.md`, which Romain runs separately
once he's approved the UI proposal. Build only the backend + JSON endpoint here.

Extend `ai_trace_logger.py` so every LLM call records (a) an estimated CO₂e value
and (b) a customer attribution, then produce a rollup view exposing cost-per-customer
and carbon-per-customer per feature. This is the unit-economics layer that
defends the YC pitch and the Series-A pitch.

### Prerequisites from prior steps
_None — G is independent._

If step F has shipped, G can also ingest F's documented cost model for the OSS
passport pipeline. Read `audit/parker-pipeline/runs/<RUN_ID>/F/RESULT.md` if present.

### Source material
- `backend/app/services/ai_trace_logger.py` — current trace structure.
- `backend/relopass/llm/router.py` — model registry and cost YAML.
- `audit/parker-framework-audit.md` section 2 (W14) and section 4, Prompt G.

### Concrete deliverables

1. Migration `supabase/migrations/<timestamp>_ai_unit_economics.sql`:
   - Table `ai_model_energy_profiles(
       model_name text pk,
       joules_per_input_token numeric not null,
       joules_per_output_token numeric not null,
       region_gco2_per_kwh numeric not null,        -- region grid carbon intensity
       source_url text,                              -- cite where the estimate comes from
       updated_at timestamptz not null default now()
     )`.
   - Seed rows for the models in the existing router: claude-sonnet-4-6,
     claude-haiku-4-5, gpt-4o, gpt-4o-mini, text-embedding-3-small. Cite public
     estimates (e.g., Anthropic / OpenAI sustainability reports, Patterson et al.,
     ML CO2 Impact paper). The numbers are rough; that's fine, the framework
     matters more than the precision today.
   - Add columns to existing `policy_assistant_traces` (or whatever the active
     traces table is called — read D's RESULT.md if D added new columns):
     `co2e_grams_estimated numeric`, `customer_id uuid`, `feature_key text`.
   - Materialized view `mv_ai_unit_economics` aggregating
     `(week, customer_id, feature_key)` → `total_cost_usd, total_tokens_in,
     total_tokens_out, total_co2e_grams, n_calls`.
   - **RLS** on `ai_model_energy_profiles`: SELECT for authenticated; UPDATE for
     admins. `REVOKE ALL ... FROM anon`.
   - **RLS** on `mv_ai_unit_economics`: SELECT for admins of the rolled-up customer,
     plus platform admins. `REVOKE ALL ... FROM anon`.
2. Create `backend/app/services/ai_carbon_estimator.py`:
   - `estimate_co2e_grams(model_name, tokens_in, tokens_out) -> float` —
     `(tokens_in * J_in + tokens_out * J_out) / 3_600_000 (J→kWh) * gCO2_per_kWh`.
   - Reads from `ai_model_energy_profiles`. Caches the profile in-process.
   - Falls back to a global default if the model is unknown, and logs a warning.
3. Extend `TraceSession.flush()` in `ai_trace_logger.py` to:
   - Compute `co2e_grams_estimated` via the estimator.
   - Resolve `customer_id` and `feature_key` from the call context. Every call
     site must now pass these via the TraceSession constructor or context manager.
   - Persist the new columns.
4. Update every existing call site to pass `feature_key`:
   - `policy_assistant_rag_engine.py` → `feature_key='policy_assistant'`.
   - `llm_policy_extractor.py` → `feature_key='policy_extraction'`.
   - `ocr_passport_extractor.py` → `feature_key='passport_ocr'`.
   - Any other LLM-using service module.
   Use a constant module `backend/app/services/ai_feature_keys.py` with all keys
   as `Literal` types for type safety.
5. Admin route in `backend/app/routers/admin_ai_unit_economics.py`:
   - `GET /api/admin/ai-unit-economics?customer_id=...&from=...&to=...&feature_key=...`
     → returns the rollup from `mv_ai_unit_economics`.
   - Auth: `is_admin()` allowlist.
   - Register in `backend/app/main.py`.
6. Frontend panel: **DEFERRED.** Do not build the admin panel here. Surface a
   note in RESULT.md under "Known gaps / follow-ups" stating that the admin
   panel ships via `prompts/followups/G-frontend.md` when Romain approves the
   UI proposal.
7. Refresh schedule:
   - Add to `audit/parker-pipeline/runs/<RUN_ID>/G/RESULT.md` a suggested
     pg_cron entry to refresh `mv_ai_unit_economics` nightly at 02:00 UTC.
8. Tests:
   - `backend/tests/test_ai_carbon_estimator.py` — known inputs, expected gCO₂e.
   - `backend/tests/test_trace_logger_carbon.py` — TraceSession persists the new
     columns; missing model_name falls back to default and warns.
   - `backend/tests/test_admin_ai_unit_economics_router.py` — auth, schema, date
     filtering.
   - Frontend snapshot test for the panel.

### Design notes
- The carbon estimate is approximate. State this in the panel UI ("≈ estimated;
  vendor energy intensity is not public").
- `feature_key` is the master attribution dimension. Use `Literal` types
  end-to-end (TypeScript on frontend, Pydantic + Literal on backend) so unknown
  keys fail at edit time, not runtime.
- The materialized view should be cheap to refresh (group-by on a trace table
  with a timestamptz index). If the trace table is large, add an index on
  `(customer_id, feature_key, created_at)`.
- Surface the panel link in the existing AIPanel.tsx component.

### Out of scope
- Per-employee attribution (one level deeper). Customer-level is sufficient for now.
- Scope 2 vs Scope 3 distinctions. We report a single CO₂e number.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies cleanly; mv refreshes without error.
- Every existing LLM call site now passes `feature_key` — verify with a grep
  assertion in CI (no bare TraceSession() construction).
- Admin endpoint returns realistic numbers for a seeded fixture.
- Note in RESULT.md that the frontend panel ships via the follow-up prompt
  `prompts/followups/G-frontend.md` (deferred per Romain's UI-reuse mandate).

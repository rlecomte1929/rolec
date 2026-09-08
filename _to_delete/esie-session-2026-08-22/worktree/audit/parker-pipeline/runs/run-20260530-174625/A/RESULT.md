# Step A RESULT — Cox survival model for case timelines

_Run: run-20260530-174625 | Branch: audit/parker-step-A-cox-survival_

## Summary

Shipped the first quantitative prediction in ReloPass: a Cox proportional-hazards
survival model that estimates the days remaining until a relocation case closes,
with an 80% interval. A new `case_duration_model.py` service wraps lifelines
(survival-frame builder, k-fold C-index, training orchestrator, deterministic
fallback, pickle persistence). A new `ml_models` table caches the fitted model
under the CLAUDE.md hard RLS gate. A canary-gated read route
(`GET /api/cases/{case_id}/predicted-duration`) serves predictions behind
`PREDICTIONS_ENABLED` with session-token + ownership auth. A CLI trains and
persists the model. All heavy ML imports are deferred so the change cannot regress
the rest of the backend on machines without the ML extras.

## Files changed

```
 backend/app/main.py                              |   3 +
 backend/app/routers/predictions.py               |  63 +++
 backend/app/services/case_duration_model.py      | 604 +++++++++++++++++++++++
 backend/requirements.txt                         |   7 +
 backend/scripts/__init__.py                      |   0
 backend/scripts/train_case_duration_model.py     |  70 +++
 backend/tests/test_case_duration_model.py        | 203 ++++++++
 supabase/migrations/20260601020000_ml_models.sql |  51 ++
 8 files changed, 1001 insertions(+)
```
(diff vs pipeline base SHA `81d98bc8`, not `main` — see "Branch base" below.)

## Tests added

- `backend/tests/test_case_duration_model.py` — guarded by
  `pytest.importorskip("lifelines"/"sklearn")`:
  - `test_cross_validated_concordance_beats_target` — synthetic 200-case frame,
    5-fold C-index ≥ 0.65 (happy path / acceptance target).
  - `test_fit_cox_model_returns_fitter` — returns a lifelines `CoxPHFitter`.
  - `test_train_orchestrator_marks_servable` — orchestrator yields an `active`,
    servable model with the right row count + concordance.
  - `test_all_censored_returns_unsafe_sentinel` — all-censored frame → no crash,
    `unsafe_to_serve` sentinel with populated fallback priors (edge case).
  - `test_fit_cox_model_zero_events_raises` — zero events → `InsufficientDataError`.
  - `test_missing_covariate_column_raises` — missing covariate → `InsufficientDataError`.
  - `test_too_few_rows_raises` — `< MIN_TRAINING_ROWS` → `InsufficientDataError`.
  - `test_predict_remaining_duration_shape` — dict keys/ordering/int types,
    `p20 ≤ median ≤ p80`.
  - `test_predict_uses_fallback_when_unsafe` — unsafe model falls back deterministically.
  - `test_predict_missing_case_raises` — unknown case → `InsufficientDataError`.

## Test result

- New model suite: **10 passed in ~3.8s** (`.venv` with ML extras installed).
- CI deterministic subset (`test_admin_form_templates_router`, `test_trigger_engine`,
  `test_case_dossier_forms`): **55 passed**.
- Full-suite collection: **2023 tests collected, 10 collection errors** — all 10 are
  **pre-existing** `ModuleNotFoundError: No module named 'services.<x>'` from the
  in-progress `backend/services/` → `backend/app/services/` migration (AUDIT-A9.3),
  unrelated to this change. My new files add **zero** new collection errors and
  import cleanly **without** the ML extras (verified against `backend/.venv`, which
  lacks lifelines).
- Route-auth audit (`scripts/check_route_auth.py`): **passed** — the new GET route is
  guarded by `Depends(get_current_user)`.
- `tsc --noEmit`: **passed (exit 0)** — no frontend changes.

> The pipeline `verify` step runs the full `pytest -q`. It will only exercise the new
> model tests if the ML extras are installed (`pip install -r backend/requirements.txt`);
> otherwise they skip cleanly. The pre-existing 10 collection errors will appear
> regardless and are not caused by this step.

## Migration applied?

- File: `supabase/migrations/20260601020000_ml_models.sql`
- **Not yet applied** to remote (left for review → merge → `supabase db push`, or
  MCP `apply_migration`). Per repo memory, `supabase db push` is blocked by history
  drift; apply via MCP when ready.
- RLS posture — table `ml_models`:
  - RLS enabled: **yes** (`enable row level security`).
  - Policies: `ml_models_admin_read` (SELECT, `authenticated`, `using public.is_admin()`);
    `ml_models_service_all` (ALL, `service_role`). **No** INSERT/UPDATE/DELETE policy
    for `authenticated` — only the backend service role writes.
  - `REVOKE ALL ON public.ml_models FROM anon`: **yes**.

## New routes

| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET | /api/cases/{case_id}/predicted-duration | session-token (`get_current_user`) + `require_case_access` ownership; 404 when `PREDICTIONS_ENABLED` is off or no model exists | `backend/app/routers/predictions.py` |

## New tables / schema changes

- `public.ml_models` — `id uuid pk default gen_random_uuid()`, `model_key text`,
  `version text`, `pickled_blob bytea`, `trained_at timestamptz default now()`,
  `n_training_rows int`, `concordance numeric`, `status text default 'active'`,
  `metadata jsonb default '{}'`. Indexes: `(model_key, version)`,
  `(model_key, trained_at desc)`.

## Configuration / env vars added

- `PREDICTIONS_ENABLED` — canary kill-switch for the prediction route. Default
  `false`; route 404s when off. Read in `backend/app/routers/predictions.py`
  (`_predictions_enabled()`), accepts `1/true/yes/on`.

## UI changes summary

- New routes added: none (backend only).
- New components added: none.
- Existing antigravity components reused: n/a.
- UI-PROPOSAL.md status: not required (UI impact: None).

## Deviations from the original audit prompt

1. **Schema reality vs sketch.** The sketch referenced `employee_assignments` and a
   `case_milestones` *service* module; neither exists. The builder joins the real
   `public.wizard_cases` + `public.case_milestones` + `public.case_assignments`.
   Covariates `band` / `dependents_count` / `service_count` live inside
   `wizard_cases.draft_json` (text), so they are parsed out best-effort.
2. **Admin RLS gate.** Used canonical `public.is_admin()` rather than a direct
   `admin_allowlist` join — that table is email-keyed and `public.is_admin()` is the
   in-DB helper the recent cases / policy-HR RLS migrations use.
3. **Lazy ML imports + `importorskip`.** Required so the change does not break the
   full `pytest -q` collection (which the `verify` command runs with bare `pytest`)
   on machines without the ML extras. The router/service are import-safe; only
   fit/predict need the libs.
4. **Added a `train_case_duration_model` orchestrator and a `CaseDurationModel`
   wrapper** beyond the four named functions, to carry model version / training-row
   count / fallback priors through pickling and to express the all-censored
   "sentinel, don't crash" behavior the prompt asked for.
5. **Migration not auto-applied.** Left for human review per the pipeline's
   "do not merge / Romain reviews" rule and the repo's migration-drift constraint.

## Branch base (important for the PR)

This branch was cut from the pipeline base SHA `81d98bc8`, which is the tip of
`feature/sec-004-rate-limit-coverage` — **7 commits ahead of `main`** and not yet
merged. The PR should target **`feature/sec-004-rate-limit-coverage`** (not `main`)
so its diff shows only the Parker-A changes. Opening against `main` would fold in the
unmerged SEC-004 / SEC-RLS commits.

## What downstream steps will need from this step

- **Migration cache table:** `public.ml_models(model_key, version, pickled_blob,
  trained_at, n_training_rows, concordance, status, metadata)` is now the standard
  place to cache trained model blobs. Steps B (optimizer) and C (clustering) can
  reuse the same table + RLS pattern (admin-read via `public.is_admin()`,
  service-role write, anon revoked) for any persisted artifacts, with a distinct
  `model_key`.
- **Model registry conventions:** `model_key='case_duration_cox'`,
  `version='1.0.0'`. Load the latest via
  `case_duration_model.load_active_model(session, model_key)`; persist via
  `persist_model(session, model)`.
- **Canary pattern:** new predictive routes should follow the `PREDICTIONS_ENABLED`
  default-off env-flag → 404 convention shown here.
- **Auth pattern for case-scoped routes:** reuse `get_current_user` +
  `require_case_access(case_id, user)` from `backend/app/auth_deps.py`.

## Known gaps / follow-ups

- **`build_survival_frame` is exercised by the CLI, not unit-tested against a live
  DB** (the required tests use synthetic frames). It uses Postgres-specific SQL
  (`FILTER`, schema-qualified names), so it cannot run against the local sqlite
  default; validate it against Supabase after the migration is applied.
- **End-to-end CLI run** (`python -m backend.scripts.train_case_duration_model`
  producing an `ml_models` row) requires the migration applied to a reachable
  Postgres; not run locally because no DB/migration was applied in this step.
- **`event_observed` heuristic** (terminal status or all-milestones-done) should be
  revisited once a real case-closure timestamp exists on `wizard_cases`.
- **Frontend `<CasePredictionBadge>`** is intentionally out of scope (separate task).

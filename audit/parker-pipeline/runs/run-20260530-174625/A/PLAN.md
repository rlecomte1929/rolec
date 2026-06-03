# Step A PLAN — Cox survival model for case timelines

_Run: run-20260530-174625 | Branch: audit/parker-step-A-cox-survival_

## Task understanding

Build the first quantitative prediction in ReloPass: a Cox proportional-hazards
survival model that estimates time-to-completion for relocation cases. Deliverables
are backend-only — a service module (`case_duration_model.py`) wrapping lifelines, a
migration adding an `ml_models` table to cache the pickled fitted model under the
hard RLS rules, a session-token + ownership-gated read route behind a
`PREDICTIONS_ENABLED` canary flag, a CLI trainer, and pytest coverage of the model
functions. No frontend work (UI impact: None).

## Upstream alignment

PREREQUISITES.md: none — step A is independent. Therefore I align to the **actual
codebase**, not the audit sketch. Key ground-truth corrections vs the sketch:

- There is **no `employee_assignments` table** and **no `case_milestones` service
  module**. Cases live in `public.wizard_cases` (ORM `Case`, PK `id: text`,
  cols `dest_country`, `origin_country`, `status`, `created_at`, `updated_at`,
  `target_move_date`, `draft_json: text`). Milestones live in
  `public.case_milestones` (migration `20260325000000_case_milestones.sql`:
  `case_id text`, `milestone_type`, `status` ∈ pending/in_progress/done/skipped/overdue,
  `target_date`, `actual_date`, `created_at`). Case→user ownership is via
  `public.case_assignments` (`case_id`, `canonical_case_id`, `employee_user_id`,
  `hr_user_id`).
- Auth: reuse `backend/app/auth_deps.py` — `get_current_user` (session-token) and
  `require_case_access(case_id, user)` (employee-owner / HR-company / admin gate).
- Admin RLS gate: canonical `public.is_admin()` (no args, already in DB). The
  `admin_allowlist` table is keyed by `email`, not `user_id`, so policies must call
  `public.is_admin()` rather than joining `admin_allowlist` directly.
- Service tree: new service files go in `backend/app/services/` (per backend/CLAUDE.md).

## File-by-file change list

- `backend/requirements.txt` — add `lifelines==0.27.8` (pinned to avoid pickle
  drift), `scikit-learn>=1.3`, `scipy>=1.11`, `pandas>=2.0`.
- `backend/app/services/case_duration_model.py` (new) — survival frame builder,
  Cox fit, k-fold concordance, remaining-duration prediction, persistence/load
  helpers, `InsufficientDataError`. Heavy imports (pandas/lifelines/sklearn) are
  done **lazily inside functions** so the module is import-safe when the libs are
  absent (keeps the rest of the pytest suite green on machines without ML deps).
- `backend/app/routers/predictions.py` (new) — `GET /api/cases/{case_id}/predicted-duration`,
  `Depends(get_current_user)` + `require_case_access`, 404 when `PREDICTIONS_ENABLED`
  is false. Service imported lazily inside the handler.
- `backend/app/main.py` — `include_router(predictions.router)` per dual-layer convention.
- `supabase/migrations/20260601020000_ml_models.sql` (new) — `ml_models` table + RLS.
- `backend/scripts/train_case_duration_model.py` (new) + `backend/scripts/__init__.py`
  (new, empty) — CLI: `python -m backend.scripts.train_case_duration_model`.
- `backend/tests/test_case_duration_model.py` (new) — model-function tests, guarded
  by `pytest.importorskip("lifelines")`.

## New tables and migration plan

`supabase/migrations/20260601020000_ml_models.sql`:

- Table `public.ml_models(id uuid pk default gen_random_uuid(), model_key text not
  null, version text not null, pickled_blob bytea, trained_at timestamptz not null
  default now(), n_training_rows int, concordance numeric, status text not null
  default 'active', metadata jsonb not null default '{}'::jsonb)`.
- Indexes: `(model_key, version)` and `(model_key, trained_at desc)`.
- RLS: `enable row level security`. Policy `ml_models_admin_read` —
  `for select to authenticated using (public.is_admin())`. Service policy
  `ml_models_service` — `for all to service_role using (true) with check (true)`
  (mirrors the canonical `case_milestones` pattern; the only writer is the backend
  service role). No INSERT/UPDATE/DELETE policies for `authenticated`.
  `revoke all on public.ml_models from anon;`.

## New routes

| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET | /api/cases/{case_id}/predicted-duration | session-token (`get_current_user`) + `require_case_access` ownership; 404 when `PREDICTIONS_ENABLED` false | `backend/app/routers/predictions.py` |

## Tests

`backend/tests/test_case_duration_model.py` (top: `pytest.importorskip("lifelines")`):
- **Happy path**: synthetic 200-row frame with a real hazard signal → `fit_cox_model`
  fits and `cross_validated_concordance(df, k=5) >= 0.65`.
- **Edge**: all-censored frame (`event_observed` all 0) → does not crash; returns a
  sentinel (model with `status='unsafe_to_serve'` / concordance None), no exception.
- **Failure**: frame missing required covariate columns → raises `InsufficientDataError`.
- **Failure**: `n_training_rows < 50` → refuses to fit, raises `InsufficientDataError`
  and emits a structured warning log.
- **Predict**: `predict_remaining_duration` on a fitted model returns the dict with
  `median_days <= p80_days`, `p20_days <= median_days`, ints, and `model_version`.

## Risks and unknowns

- **ML deps not installed locally / in CI.** The CI deterministic pytest subset does
  NOT include this file, so CI stays green. The full-suite `verify` runs bare
  `pytest`; to avoid breaking *collection*, the service module and router defer all
  heavy imports, and the test file uses `importorskip`. Romain must
  `pip install -r backend/requirements.txt` before the model test will actually run
  (it skips cleanly otherwise).
- **Python 3.9 local vs 3.11 prod.** Pinning `lifelines==0.27.8` keeps pickle format
  stable across both; documented in RESULT.md.
- **`build_survival_frame` fuzziness.** Real covariates (`band`, `dependents_count`,
  `service_count`) live inside `wizard_cases.draft_json`, not as columns. The builder
  parses draft_json best-effort. It is exercised by the CLI, not unit-tested against a
  live DB (the required tests use synthetic frames). Noted as a deviation.
- **`event_observed` definition.** No explicit terminal status on `wizard_cases`. I
  treat a case as an observed event when status ∈ {completed, closed, done} or all of
  its `case_milestones` are `done`; otherwise right-censored at last activity.

## Deviations from the original audit prompt

1. Sketch tables `employee_assignments` / `case_milestones` service don't exist; I
   join the real `wizard_cases` + `case_milestones` + `case_assignments`.
2. Admin RLS uses `public.is_admin()` (canonical) rather than a direct
   `admin_allowlist` join (that table is email-keyed and there is no global join helper).
3. Heavy ML imports are lazy and tests use `importorskip` — required so the change
   does not regress the full pytest suite on ML-dep-less machines (the `verify`
   command runs bare `pytest -q`).

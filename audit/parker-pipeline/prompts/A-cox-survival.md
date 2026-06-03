## Task body — step A

**UI impact:** None. Backend only. The frontend display badge is a separate, later
task and not in scope here.

Build a Cox proportional-hazards survival model that predicts time-to-completion for
relocation cases. This is the first quantitative prediction in ReloPass and the
foundation for any "we know when your case will close" claim to HR buyers.

### Prerequisites from prior steps
_None — A is the first step._

### Source material
- `backend/app/models.py` — case + milestone ORM models.
- `backend/app/services/case_milestones.py` — milestone events and timing.
- `backend/app/services/employee_assignments.py` (if present) — case covariates.
- `audit/parker-framework-audit.md` section 4, Prompt A.

### Concrete deliverables

1. Add `lifelines>=0.27` and `scikit-learn>=1.3` to `backend/requirements.txt`. If
   `scipy>=1.11` and `pandas>=2.0` are not present, add those too.
2. Create `backend/app/services/case_duration_model.py` with these functions:
   - `build_survival_frame(session) -> pd.DataFrame` — joins cases + milestones +
     assignments into a frame with columns: `case_id`, `duration_days`,
     `event_observed` (1 if case closed, 0 if right-censored), and covariates
     (`destination_country`, `origin_country`, `band`, `dependents_count`,
     `service_count`, `seasonality_quarter`).
   - `fit_cox_model(df) -> CoxPHFitter` — fits with L2 penalizer 0.1, returns the
     fitted lifelines `CoxPHFitter`.
   - `cross_validated_concordance(df, k=5) -> float` — k-fold C-index.
   - `predict_remaining_duration(model, case_id, session) -> dict` — returns
     `{"median_days": int, "p20_days": int, "p80_days": int, "model_version": str,
     "n_training_cases": int}`.
3. Create migration `supabase/migrations/<timestamp>_ml_models.sql`:
   - Table `ml_models(id uuid pk, model_key text, version text, pickled_blob bytea,
     trained_at timestamptz, n_training_rows int, concordance numeric, metadata jsonb)`.
   - Index on `(model_key, version)` and on `(model_key, trained_at desc)`.
   - **RLS enabled**. Policy `ml_models_admin_read` allows SELECT for users in
     `admin_allowlist`. No INSERT/UPDATE/DELETE policies — only the backend service
     role writes. `REVOKE ALL ON public.ml_models FROM anon;`.
4. Create `backend/app/routers/predictions.py`:
   - `GET /api/cases/{case_id}/predicted-duration` — returns the dict from
     `predict_remaining_duration`, gated on session-token auth + ownership check
     (caller must be the case owner, the case's HR contact, or an admin).
   - Register in `backend/app/main.py` via `include_router` per the dual-layer
     convention.
5. Tests in `backend/tests/test_case_duration_model.py`:
   - Happy path: synthetic frame of 200 cases → concordance ≥ 0.65.
   - Edge: all-censored frame should not crash; return a sentinel.
   - Failure: missing covariates → raises a typed `InsufficientDataError`.
6. Add an env flag `PREDICTIONS_ENABLED` (default `false`). The router returns 404
   when disabled. This is the canary kill-switch.
7. Add a CLI: `python -m backend.scripts.train_case_duration_model` that fits and
   persists the model (writes the pickled blob into `ml_models`).

### Design notes
- Use lifelines `CoxPHFitter`. Do not roll your own.
- The pickled blob must be deserialisable on the production Render container, which
  runs Python 3.11. Pin lifelines exactly to avoid pickle-version drift.
- `n_training_rows < 50` should refuse to fit and emit a structured warning to the
  ai_trace_logger (use the existing logger; do not create a new one).
- Do not block the request path on model training. Training runs in the CLI only.
- Concordance < 0.55 should mark the model as `status='unsafe_to_serve'` and the
  route should fall back to a deterministic estimate (mean duration by destination
  country, computed from the training frame).

### Out of scope
- Real Cox regression with time-varying covariates. Stay with the standard PH model.
- Frontend display. A separate task can build a `<CasePredictionBadge>` component
  later.

### Acceptance criteria
- `cd backend && pytest backend/tests/test_case_duration_model.py` passes.
- `cd backend && pytest -q` overall suite still passes (no regression).
- `cd frontend && npx tsc --noEmit` still passes (no frontend changes expected).
- The migration applies cleanly to a fresh local Supabase, and `supabase db reset`
  still works.
- `python -m backend.scripts.train_case_duration_model` against a synthetic seed
  produces an `ml_models` row and emits a structured log line.

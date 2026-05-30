# Step H PLAN — Conjoint analysis on benefit preferences

_Run: run-20260530-174625 | Branch: audit/parker-step-H-conjoint | Base: feature/sec-004-rate-limit-coverage (81d98bc8)_

## Task understanding
Build a backend conjoint-analysis micro-service for stated-preference benefit studies.
HR admins create a study (attributes → levels); employees are shown choice sets and pick
their preferred benefit bundle; the service fits an aggregate multinomial (conditional)
logit with **effects coding** to estimate per-attribute-level part-worths, then simulates
market share for proposed bundles and recommends a utility-maximising bundle within
budget. This is the headline commercial artefact ("your employees prefer bundle X over Y
by Z%"). Backend + service + API + choice-set generation only — both UIs (employee choice
flow, HR results page) are deferred to `prompts/followups/H-frontend.md`.

## Upstream alignment
PREREQUISITES.md lists **no hard dependencies** (H is independent). Step **B**
(benefit-optimizer) shipped `public.benefit_priors(company_id uuid, category text,
attr_key text, expected_satisfaction numeric, variance numeric, source text default
'admin_seed', updated_at, updated_by)`, unique `(company_id, category, attr_key)`, read
via `benefit_priors_repo.load_company_priors(session, company_id)`. B explicitly says
Step H should write learned utilities there with `source='conjoint'`, keyed by
`(company_id, category, attr_key)`.

**Reality check:** B's branch is not merged, so `benefit_priors` / `benefit_priors_repo`
do **not** exist in the H working tree (H forks from the pre-B pipeline base — same
situation G had vs D/F). So `push_to_benefit_priors` is implemented **best-effort**:
it writes `(company_id, category=attribute, attr_key=level, expected_satisfaction=
scaled part-worth, source='conjoint')` rows when the table is present, and is a no-op
that logs a TODO when it's absent. Schema/column names match B's RESULT.md exactly so it
"just works" once B + this step are both merged and the migration applies.

Auth pattern reused from B's company-scoped HR routes: `require_admin_or_hr` +
`get_org_id_for_hr_user` (both already in `backend/app/auth_deps.py` on the base) + an
explicit path-`company_id`-vs-caller check (admins bypass) → 403 otherwise. Respondent
endpoints use `get_current_user` (any authenticated employee).

## Numerical approach (why scipy, not statsmodels)
The dev venv has numpy 1.26 / scipy 1.13 / sklearn 1.6 / pandas 2.3 but **not**
statsmodels (and prod `requirements.txt` pins none of them). Choice-based conjoint needs a
**conditional** logit over the alternatives *within each choice set* — not a plain
classification logit — which statsmodels has no first-class CBC helper for anyway. So the
fit is a transparent conditional-logit MLE via `scipy.optimize.minimize` over the
effects-coded design matrix: for choice set s with chosen alternative c,
`LL += xᵀc·β − logsumexp_j(xᵀj·β)`. Per deliverable #1 I still add `statsmodels>=0.14` to
requirements (it transitively guarantees numpy/scipy/pandas in prod); the implementation
deliberately uses scipy. numpy/scipy are lazy-imported inside the fit so the module
imports cleanly without them (B's import-safety precedent); tests `importorskip` them.

## File-by-file change list
- `backend/requirements.txt` — add `statsmodels>=0.14` (numerical stack for the fit).
- `supabase/migrations/20260601090000_conjoint.sql` — 3 tables + RLS (see below). NOT applied.
- `backend/app/services/conjoint_service.py` — pure, DB-free core:
  - dataclasses `Attribute`, `ChoiceSet`, `Response`, `Bundle`, `ConjointResults`.
  - `design_study(attributes, n_choice_sets, n_alts=3, seed=None) -> list[ChoiceSet]` —
    balanced randomised design over the level space.
  - `fit_conjoint(attributes, responses) -> ConjointResults` — effects-coded conditional
    logit MLE via scipy; returns part-worths per (attribute, level) + fit quality
    (log-likelihood, McFadden R², n_obs).
  - `simulate_market_share(bundles, part_worths) -> dict[bundle_id, share]` — softmax of
    bundle utilities.
  - `recommend_bundle(budget, attribute_costs, part_worths, hard_constraints) -> Bundle` —
    enumerates feasible level combos within budget, returns the max-utility bundle.
- `backend/app/services/conjoint_repo.py` — thin portable (PG+SQLite) persistence over the
  3 tables using `app/db.py` SessionLocal + `text()` (mirrors `ai_unit_economics.py`):
  create_study, get_study, next_choice_set_for_respondent, record_response (idempotent per
  respondent+choice_set), save_results, load_results, list responses for fit. Python-
  generated UUID text ids for portability. Plus `push_to_benefit_priors(session,
  study_id, company_id)` (best-effort, no-op + TODO log if `benefit_priors` absent).
- `backend/app/routers/conjoint.py` — 5 endpoints (below) + company path-vs-caller guard.
- `backend/app/main.py` — import + `include_router(conjoint.router)`.
- `backend/tests/test_conjoint_service.py` — fit math on a synthetic Sawtooth-style set.
- `backend/tests/test_conjoint_router.py` — auth gates, response idempotency, fit persists.

## New tables and migration plan
File: `supabase/migrations/20260601090000_conjoint.sql` (NOT applied — left for human MCP
review; `supabase db push` is blocked by history drift per repo memory). All three tables:
`ENABLE ROW LEVEL SECURITY`, company-scoped policies reusing `public.hr_company_ids()` +
`public.is_admin()`, service_role catch-all, and `REVOKE ALL ... FROM anon`.
- `conjoint_studies(id uuid pk default gen_random_uuid(), company_id uuid not null →
  companies(id) on delete cascade, name text, status text default 'draft', attributes_json
  jsonb, n_responses_target int default 100, opened_at timestamptz, closed_at timestamptz,
  created_at timestamptz default now())`. RLS: HR of the company (`company_id IN
  hr_company_ids()`) or admin read/write; index on `(company_id)`.
- `conjoint_responses(id uuid pk default gen_random_uuid(), study_id uuid not null →
  conjoint_studies(id) on delete cascade, respondent_user_id uuid, choice_set_json jsonb,
  chosen_index int, responded_at timestamptz default now())`. RLS: respondent reads/writes
  only own rows (`respondent_user_id = auth.uid()`); company HR/admin may read (for fit)
  but the HR-facing API only ever returns aggregates. Unique `(study_id,
  respondent_user_id, choice_set_hash)` for idempotency; index on `(study_id)`.
- `conjoint_results(id uuid pk default gen_random_uuid(), study_id uuid not null →
  conjoint_studies(id) on delete cascade, part_worths_json jsonb, fit_quality_json jsonb,
  computed_at timestamptz default now())`. RLS: company HR/admin read/write via the parent
  study's company; index on `(study_id)`.

Mirror note: unlike G, these are brand-new modular tables (not a legacy `database.py`
bootstrap). Tests build the schema in in-memory SQLite and monkeypatch the repo's
SessionLocal (G router-test precedent); ids are Python-generated text so no PG-only
`gen_random_uuid()` is needed on the test path.

## New routes (`backend/app/routers/conjoint.py`)
| Method | Path | Auth gate |
|--------|------|-----------|
| POST | /api/hr/{company_id}/conjoint/studies | require_admin_or_hr + company check |
| GET  | /api/hr/{company_id}/conjoint/studies/{study_id}/next-choice-set | get_current_user (respondent) |
| POST | /api/hr/{company_id}/conjoint/studies/{study_id}/responses | get_current_user (respondent) |
| POST | /api/hr/{company_id}/conjoint/studies/{study_id}/fit | require_admin_or_hr + company check |
| GET  | /api/hr/{company_id}/conjoint/studies/{study_id}/results | require_admin_or_hr + company check |

The fit endpoint computes part-worths, persists a `conjoint_results` row, and best-effort
calls `push_to_benefit_priors`. Results never expose `respondent_user_id` — aggregate only.

## Tests
- `backend/tests/test_conjoint_service.py` (`importorskip numpy, scipy`):
  - **happy**: synthetic Sawtooth-style dataset generated from known part-worths via the
    logit model (fixed seed); `fit_conjoint` recovers McFadden R² ≥ 0.25 and the
    part-worth ordering of the dominant attribute matches the ground truth.
  - **effects coding**: per attribute, fitted part-worths sum to ≈ 0 (deviation-from-mean).
  - **market share**: `simulate_market_share` returns shares that sum to 1 and rank the
    higher-utility bundle first.
  - **recommend_bundle**: respects budget (never returns an over-budget bundle) and honours
    a hard constraint; picks the max-utility feasible bundle. Edge: budget too low for any
    bundle → returns None / raises a documented error.
  - **design_study**: returns `n_choice_sets` sets, each with `n_alts` distinct bundles
    covering valid levels; balance sanity (each level appears).
- `backend/tests/test_conjoint_router.py` (in-memory SQLite + monkeypatched SessionLocal,
  auth deps overridden like G's router test):
  - non-HR/non-admin → 403 on create/fit/results; wrong-company HR → 403.
  - create study → 200 + persisted; next-choice-set returns a set; submit response is
    idempotent (same respondent+choice set twice → one row); fit persists a results row and
    GET results returns part-worths without `respondent_user_id`.

## Risks and unknowns
- **scipy convergence** on tiny/degenerate data: guard with a sensible default start (0s),
  bounded iterations, and a fallback that returns zeroed part-worths + `n_obs` so the fit
  endpoint never 500s. Document in the service docstring.
- **CI numerical libs**: if numpy/scipy aren't installed in CI, the service tests
  `importorskip` (skip, not fail); the router tests that don't fit don't need them. The fit
  router test guards with importorskip too.
- **benefit_priors absence**: bridge is best-effort/no-op; verified by a test that the fit
  endpoint succeeds even when the table doesn't exist.
- **RLS untestable on SQLite**: SQLite can't enforce Postgres RLS, so the migration's RLS
  is reviewed by inspection (hard-gate checklist) and the app-layer company path check is
  what the router tests exercise. Noted as a deviation.

## Deviations from the original audit prompt
1. **Fit uses scipy conditional-logit MLE, not statsmodels/sklearn.** CBC needs conditional
   logit over within-set alternatives; statsmodels has no first-class CBC helper and plain
   sklearn LogisticRegression is the wrong model. `statsmodels>=0.14` is still added to
   requirements per deliverable #1 (transitively pins numpy/scipy/pandas for prod).
2. **`push_to_benefit_priors` is best-effort / no-op when `benefit_priors` is absent**,
   because B is unmerged and the table isn't in the H working tree. Column names match B's
   schema exactly so it activates once both merge.
3. **Portable text UUID ids on the test path** (Python-generated) so the repo works on
   SQLite; the migration still uses `uuid`/`gen_random_uuid()` for Postgres.
4. **RLS verified by inspection, not an automated two-company SQLite test** (SQLite has no
   RLS). The app-layer company path-vs-caller check is unit-tested instead.
5. **Frontend deferred** to `prompts/followups/H-frontend.md` per the UI-reuse mandate
   (explicit in the task body).

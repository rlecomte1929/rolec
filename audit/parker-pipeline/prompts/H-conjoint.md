## Task body — step H

**UI impact:** None in this step. The employee choice flow AND the HR results
page are significant UI surfaces — they are deferred to
`prompts/followups/H-frontend.md`, which Romain runs separately once he's
approved the UI proposal. Build only the backend + service + API endpoints +
choice-set generation here.

Build a conjoint-analysis micro-service that, given a set of stated-preference
responses (employees ranking benefit bundles), estimates per-attribute part-worths
and simulates market share for proposed bundles. This is the single highest-value
commercial artefact for an HR-tech sales motion: it lets the buyer say "our
employees prefer bundle X over Y by Z%".

### Prerequisites from prior steps
_None required, but B is a natural fit._

If step B (benefit optimizer) has shipped, this step's part-worth output feeds B's
`benefit_priors` table. Read `audit/parker-pipeline/runs/<RUN_ID>/B/RESULT.md` if
present and align the priors-update path with B's schema.

### Source material
- `backend/app/services/employee_recommendations_filter.py` — benefit attribute model.
- `backend/app/services/hr_policy_resolver.py` — benefit categories and attributes.
- `audit/parker-framework-audit.md` section 2 (W7) and section 4, Prompt H.

### Concrete deliverables

1. Add `statsmodels>=0.14` to `backend/requirements.txt`.
2. Migration `supabase/migrations/<timestamp>_conjoint.sql`:
   - Table `conjoint_studies(
       id uuid pk, company_id uuid fk, name text, status text default 'draft',
       attributes_json jsonb,                  -- attribute → levels
       n_responses_target int default 100,
       opened_at timestamptz, closed_at timestamptz,
       created_at timestamptz default now()
     )`.
   - Table `conjoint_responses(
       id uuid pk, study_id uuid fk, respondent_user_id uuid,
       choice_set_json jsonb,                  -- bundles shown
       chosen_index int,                       -- which bundle they picked
       responded_at timestamptz default now()
     )`.
   - Table `conjoint_results(
       id uuid pk, study_id uuid fk,
       part_worths_json jsonb,                 -- attribute level → part-worth
       fit_quality_json jsonb,                 -- log-likelihood, McFadden R², n_obs
       computed_at timestamptz default now()
     )`.
   - **RLS enabled** on all three. Company-scoped: a company's HR admins see their
     studies; respondents see only their own response rows. `REVOKE ALL ... FROM anon`
     on all three.
3. Create `backend/app/services/conjoint_service.py`:
   - `design_study(attributes: dict[str, list[str]], n_choice_sets: int)
     -> list[ChoiceSet]` — generates a fractional-factorial design (use
     `statsmodels` or a simple D-efficient heuristic).
   - `fit_conjoint(responses: list[Response]) -> ConjointResults` — multinomial logit
     via `statsmodels.discrete.discrete_model.Logit` or `sklearn`'s logistic
     regression with effects coding; returns part-worths per attribute level.
   - `simulate_market_share(bundles: list[Bundle], part_worths) -> dict[bundle_id, share]`.
   - `recommend_bundle(budget, attribute_costs, part_worths, hard_constraints)
     -> Bundle` — picks the bundle maximising utility within budget.
4. Backend routes in `backend/app/routers/conjoint.py`:
   - `POST /api/hr/{company_id}/conjoint/studies` — create a study (HR admin).
   - `GET /api/hr/{company_id}/conjoint/studies/{study_id}/next-choice-set` —
     returns the next choice set for the calling respondent.
   - `POST /api/hr/{company_id}/conjoint/studies/{study_id}/responses` — submit a
     choice.
   - `POST /api/hr/{company_id}/conjoint/studies/{study_id}/fit` — fit (HR admin).
   - `GET /api/hr/{company_id}/conjoint/studies/{study_id}/results` — read part-worths.
   - Register in `backend/app/main.py`.
5. Frontend: **DEFERRED.** Do not build the employee choice flow or the HR
   results page in this step. Both are significant UI surfaces and ship via
   `prompts/followups/H-frontend.md` when Romain approves the UI proposal.
   Surface this clearly in RESULT.md under "Known gaps / follow-ups".
6. If B's `benefit_priors` table exists, add a service call
   `push_to_benefit_priors(study_id, company_id)` that maps part-worths into the
   `(company_id, category, attr_key)` rows B reads from. Otherwise log a TODO and
   surface it in the UI.
7. Tests:
   - `backend/tests/test_conjoint_service.py` — fits the standard Sawtooth-style
     synthetic dataset (well-known, no licence issue); McFadden R² ≥ 0.25 on the
     synthetic set.
   - `backend/tests/test_conjoint_router.py` — auth gates, response idempotency,
     fit endpoint persists results.

### Design notes
- The choice set design is the trickiest part. Don't optimise it perfectly —
  a D-optimal design via balanced randomisation over 8–12 sets per respondent is
  more than sufficient for the early-stage product claim.
- Respondent anonymity: store `respondent_user_id` for de-duplication but never
  expose it in HR-facing results. Aggregations only.
- Use effects coding (not dummy coding) so part-worths are interpretable as
  deviations from the grand mean — this is what HR readers expect.

### Out of scope
- Latent-class conjoint (segment-level part-worths). Aggregate fit only.
- Hierarchical Bayes conjoint. Aggregate MNL is sufficient for v1.
- Mobile-optimised UI. Desktop is enough for first pilot.

### Acceptance criteria
- pytest + tsc both pass.
- Migrations apply; RLS enforces company scoping (test with two seeded companies).
- Fit on the synthetic Sawtooth dataset reaches the McFadden R² target.
- RESULT.md states clearly that the employee + HR UI is deferred to
  `prompts/followups/H-frontend.md` per Romain's UI-reuse mandate.

# Recommendation Quality & Canonical Backend Criteria Builder

## 1. Current Ranking Weaknesses

| Service | Weakness | Details |
|---------|----------|---------|
| **housing** (living_areas) | Policy caps unused | `_policy_cap_monthly` is passed in criteria but plugin ignores it; no "in policy" / "above budget" flags in output |
| **housing** | Limited family context | `bedrooms` and `sqm_min` used; family size / dependents not explicitly in model |
| **schools** | Child ages parsed but weakly | Child ages array used; curriculum/school_type from schema not heavily weighted in scoring |
| **schools** | Policy caps unused | `_policy_cap_annual` passed but not used in ranking |
| **movers** | Acc type/bedrooms used | `current_accommodation` built; packing, temp storage from answers may not map to dataset |
| **movers** | Policy caps unused | `_policy_cap_one_time` passed but not used |
| **banks** | Limited inputs | Preferred languages, fee sensitivity; assignment type / family not in model |
| **insurance** | Coverage types used | Coverage array; family composition not in scoring |
| **electricity** | Green/flex | Basic preference matching; destination context minimal |

**Cross-cutting:**
- No explainability metadata ("why it matched", "budget fit", "policy fit")
- Policy data integrated at criteria level only; plugins do not adjust scores or expose flags

---

## 2. Files Changed

| File | Change |
|------|--------|
| `backend/app/recommendations/criteria_builder.py` | **New** – Canonical criteria builder (single source of truth) |
| `backend/main.py` | Added `POST /api/recommendations/batch`; imports for `build_criteria_for_assignment`, `_flatten_saved_answers`, `recommend_single` |
| `frontend/src/features/recommendations/api.ts` | Added `recommendBatch(assignmentId, selectedServices?)` |
| `frontend/src/pages/services/ServicesQuestions.tsx` | Removed `buildCriteriaForService`; removed `stableInitialAnswers`; `loadRecommendations` now calls `recommendBatch` only |

---

## 3. Backend Canonical Criteria Builder

**Location:** `backend/app/recommendations/criteria_builder.py`

**Function:** `build_criteria_for_assignment(assignment_id, case_id, selected_services, saved_answers, case_context, policy_context)`

**Compiles:**
- `assignment_id`, `case_id` per criteria
- `destination_city`, `destination_country`, `origin_city` from case context
- Saved dynamic answers mapped via `CRITERIA_MAP` (question_key → criteria_key)
- Service-specific shaping via `_apply_service_shaping()`:
  - **housing:** budget_min/max → `budget_monthly`, commute_mins → `commute_work`
  - **schools:** child_ages string → numeric array
  - **banks:** preferred_languages string → array
  - **movers:** acc_type, acc_bedrooms → `current_accommodation`
  - **insurances:** coverage_types string → array
- Policy caps: `_policy_cap_monthly` (housing), `_policy_cap_annual` (schools), `_policy_cap_one_time` (movers)

**Service key mapping (frontend → backend):**
- housing → living_areas
- schools → schools
- movers → movers
- banks → banks
- insurances → insurance
- electricity → electricity

---

## 4. Ranking Improvements by Service

| Service | Current inputs | Missing / weak | Suggested improvements |
|---------|----------------|----------------|------------------------|
| **housing** | budget_monthly, bedrooms, sqm_min, commute_work, lifestyle_priorities | Family size, area preference, policy cap usage | Use `_policy_cap_monthly` to down-rank above-policy options; add `policy_fit` to metadata |
| **schools** | child_ages, destination | curriculum, budget_level, school_type, policy cap | Weight curriculum; use `_policy_cap_annual`; add language/international flag |
| **movers** | current_accommodation, origin_city | packing_service, move_type, temp storage | Map packing and move_type into score; use `_policy_cap_one_time` |
| **banks** | preferred_languages | Assignment type, family, destination | Add destination currency/locale awareness |
| **insurance** | coverage_types | Family composition, assignment duration | Add dependents to coverage weighting |
| **electricity** | green_preference, contract_flexibility | Destination, contract length | Add destination-specific defaults |

---

## 5. Policy / Budget Integration

**Current state:**
- `normalize_policy_caps()` produces `{ currency, caps: { housing, moving, schools }, total_cap }`
- Criteria builder injects `_policy_cap_monthly`, `_policy_cap_annual`, `_policy_cap_one_time` into criteria per service
- Plugins **do not** read these; they are passed but ignored by `validate_and_parse`

**Recommended integration:**
- In each plugin `score()`: read `_policy_cap_*` from raw criteria (before Pydantic parse) or extend CriteriaModel
- Down-rank items above cap (e.g. reduce budget_match) without hard-fail
- Add to `metadata`: `policy_fit: "in_policy" | "above_budget" | "outside_preferred"`

---

## 6. Batch Endpoint Design

**Endpoint:** `POST /api/recommendations/batch`

**Request body:**
```json
{
  "assignment_id": "string (required)",
  "selected_services": ["housing", "schools", "movers"] // optional; defaults to DB selected services
}
```

**Response:**
```json
{
  "results": {
    "living_areas": { "category": "...", "recommendations": [...], "criteria_echo": {...} },
    "schools": { ... }
  }
}
```

**Flow:**
1. Validate assignment access via `_require_assignment_visibility`
2. Resolve case_id, load case draft and context
3. Load selected services from body or `db.list_case_services`
4. Load saved answers via `db.list_case_service_answers`, flatten with `_flatten_saved_answers`
5. Load policy via `policy_engine.load_policy()` and `normalize_policy_caps`
6. Call `build_criteria_for_assignment` for each selected service
7. For each backend_key in criteria_map: call `recommend(backend_key, criteria, top_n=10)`
8. Return `{ results: { backend_key: RecommendationResponse } }`

**Route order:** Batch route is registered before `/{category}` so `/batch` is matched explicitly.

---

## 7. Verification Steps

1. **Frontend no longer shapes criteria**
   - [ ] `buildCriteriaForService` removed from `ServicesQuestions.tsx`
   - [ ] No service-specific criteria building in frontend

2. **Backend is single source of truth**
   - [ ] All recommendation criteria built in `criteria_builder.py`
   - [ ] `build_criteria_for_assignment` used by batch endpoint only (single-category still accepts raw criteria for backwards compat)

3. **Recommendations reflect saved answers**
   - [ ] Save answers on ServicesQuestions, then call batch; verify criteria_echo contains saved values
   - [ ] Change budget/child_ages and confirm ranking changes

4. **Policy/budget in criteria**
   - [ ] With policy configured, `_policy_cap_*` present in criteria (inspect criteria_echo or logs)
   - [ ] Plugins do not yet use for ranking (deferred)

5. **Batch endpoint**
   - [ ] `POST /api/recommendations/batch` with `assignment_id` returns `results` for selected services
   - [ ] Without `selected_services`, uses DB selected services
   - [ ] Returns top 10 per category

6. **Output shape**
   - [ ] `results` keys are backend category keys (living_areas, schools, movers, banks, insurance, electricity)
   - [ ] Each value is full `RecommendationResponse` with `recommendations`, `criteria_echo`, `generated_at`

---

## 8. Deferred Items

- **Plugin policy usage:** Use `_policy_cap_*` in plugin scoring and add `policy_fit` to metadata
- **Explainability:** Add "why it matched", "criteria satisfied", "budget/policy fit" to each recommendation item
- **canonical_case_id:** Include in criteria when available from assignment/case
- **Single-category endpoint:** Consider deprecating or routing through canonical builder for consistency

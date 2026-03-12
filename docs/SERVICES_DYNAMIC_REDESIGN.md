# Services Flow Dynamic Redesign

## 1. Root Causes in Current Implementation

### 1.1 Static Questionnaire
- **Location:** `frontend/src/features/recommendations/ProvidersCriteriaWizard.tsx`
- **Issue:** `WIZARD_QUESTIONS` is a hardcoded array of ~25 questions. Questions are only filtered by `getQuestionsForCategories(categories)` — no conditional logic, no `applies_if`, no prefill from prior answers.
- **Effect:** Same question set appears regardless of household context, prior answers, or destination; redundant questions asked when case already has data.

### 1.2 Autosave Loop Risk
- **Location:** `ServicesQuestions.tsx` — `onAnswersChange` with 500ms debounce triggers `servicesAPI.saveServiceAnswers` on every answer change.
- **Issue:** Autosave fires when user types; combined with `setAnswers` → re-render → potential re-trigger, creates risk of repeated POST storms.
- **Mitigation in place:** `lastSavedPayloadRef`, `saveInFlightRef`, `workflow.state` checks — but user requirement is **explicit Save only**, no autosave.

### 1.3 Selected Services Not Reloaded
- **Location:** `ServicesFlowContext.tsx` uses `localStorage` for `selectedServices`; `ProvidersPage` loads from API but only pushes to context on "Continue".
- **Issue:** If user visits `/services/questions` directly or refreshes, `selectedServices` comes from localStorage (stale) or is empty. API persistence exists but is not the source of truth on load.

### 1.4 Saved Answers Not Loaded
- **Location:** `ServicesQuestions.tsx` — `getCaseDetailsByAssignmentId` provides `initialAnswers` via `caseToInitialAnswers` (case draft only).
- **Issue:** `servicesAPI.getServiceAnswers(caseId)` is **never called**. Previously saved questionnaire answers are never loaded on revisit.

### 1.5 Answers Storage Shape
- **Location:** `case_service_answers` — one row per `(case_id, service_key)` with `answers` as JSONB blob.
- **Issue:** Flat blob per service; no normalized `question_key` / `answer_value`. Hard to support conditional logic, validation, or per-question prefill.

### 1.6 No Explicit Save on Services Page
- **Location:** `ProvidersPage` — `StickyContinueBar` has "Continue to questions"; it calls `handleSave` then navigates.
- **Issue:** No standalone "Save" button. User cannot save selected services without continuing. Requirement: explicit Save with feedback (Saving... / Saved / Save failed).

### 1.7 Recommendation Context
- **Location:** `buildCriteriaFromAnswers` + `effectiveAnswers` from `initialAnswers` (case) + `answers` (form).
- **Issue:** Destination comes from case correctly; but if case has no destination, validation fails (good). Some plugins still have city fallbacks (Singapore) — should fail clearly when missing.

---

## 2. Proposed Target Design

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SERVICES FLOW                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 1: Select services                                                  │
│   - UI: ProvidersPage (unchanged layout, add explicit Save)              │
│   - Persist: POST /api/employee/assignments/{id}/services                │
│   - Load:  GET /api/employee/assignments/{id}/services                   │
│   - Context: Hydrate selectedServices from API on mount                  │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 2: Dynamic questionnaire                                            │
│   - Load: GET /api/services/questions?assignment_id=X                    │
│     → Returns dynamic question list for selected services + context      │
│   - Render: DynamicQuestionnaire (schema-driven, no static pages)        │
│   - Save: POST /api/services/answers (explicit Save button only)         │
│   - Load answers: GET /api/services/answers?case_id=X                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 3: Recommendations                                                  │
│   - Build: Canonical recommendation input (context + answers + services) │
│   - Fetch: POST /api/recommendations/batch                               │
│     → Single call with selected services, returns top 10 per service     │
│   - Validate: Fail if destination missing, no silent fallbacks           │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 4: Review & save                                                    │
│   - Same as today; explicit Save where applicable                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Question Schema (Backend)

```python
# backend/app/services/question_schema.py
class ServiceQuestionSchema(BaseModel):
    question_key: str
    label: str
    type: Literal["text", "number", "select", "multiselect", "checkbox", "date", "range"]
    service_category: str
    required: bool = False
    options: Optional[List[Dict[str, str]]] = None
    applies_if: Optional[Dict[str, Any]] = None  # {"question_key": "value"} or {"!exists": "key"}
    prefill_source: Optional[str] = None  # "case.destCity", "case.dependents[].age", "answers.budget_min"
    default: Optional[Any] = None
```

### 2.3 Question Generation Engine

- Input: `selected_services`, `case_context`, `saved_answers`
- Output: Ordered list of questions (filtered, with defaults/prefill applied)
- Logic: Filter by service; evaluate `applies_if`; skip if prefill source has value; apply defaults

### 2.4 Persistence

- **Selected services:** Already OK — `case_services` table, explicit save via Continue. Add standalone Save button.
- **Answers:** Keep `case_service_answers` (case_id, service_key, answers JSONB) for now. Extend to support idempotent upsert. Add assignment_id to reads for consistency.
- **No autosave:** Remove debounced autosave; only explicit Save.

---

## 3. Files Changed

| File | Change |
|------|--------|
| `backend/app/services/question_schema.py` | **New** — schema + question bank |
| `backend/app/services/question_engine.py` | **New** — dynamic question generation |
| `backend/main.py` | Add GET /api/services/questions, ensure GET /api/services/answers by assignment |
| `frontend/src/features/recommendations/ProvidersCriteriaWizard.tsx` | Remove autosave; use schema from API or keep current structure with explicit Save |
| `frontend/src/pages/services/ServicesQuestions.tsx` | Load answers on mount; remove autosave; explicit Save only |
| `frontend/src/pages/ProvidersPage.tsx` | Add explicit Save button (in addition to Continue) |
| `frontend/src/features/services/ServicesFlowContext.tsx` | Hydrate selectedServices from API when assignmentId available |
| `frontend/src/api/client.ts` | Add getServiceQuestions(assignmentId) |

---

## 4. Backend Changes

1. **Question schema module** — Define `SERVICE_QUESTION_BANK` with `applies_if`, `prefill_source`.
2. **Question generation** — `generate_questions(selected_services, case_context, saved_answers) -> List[Question]`.
3. **GET /api/services/questions** — `?assignment_id=X` → resolve case, selected services, context, saved answers → return dynamic questions.
4. **GET /api/services/answers** — Accept `assignment_id` or `case_id`; return by case.
5. **POST /api/services/answers** — Idempotent; no change to current contract.
6. **Recommendation batch** — Optional: `POST /api/recommendations/batch` with `{ assignment_id, services[] }` to reduce round-trips.

---

## 5. Frontend Changes

1. **ProvidersPage** — Add "Save" button; show Saving/Saved/Failed; Continue still saves before navigating.
2. **ServicesFlowContext** — On assignmentId set, fetch selected services from API and sync to context (replace localStorage as source of truth for selected).
3. **ServicesQuestions** — On mount: fetch `getServiceAnswers(caseId)` and merge into initial state; remove `onAnswersChange` autosave; add explicit "Save" button; disable "Get recommendations" until required questions valid.
4. **ProvidersCriteriaWizard** — Remove debounced autosave; add explicit Save callback; optionally fetch questions from API (Phase 2) or keep current schema + explicit Save (Phase 1).

---

## 6. Data Model Changes

- **case_services:** No change.
- **case_service_answers:** Add `assignment_id` if needed for consistent scoping; currently keyed by case_id which is acceptable.
- **Normalized answers:** Future consideration — `case_service_answer_items (case_id, service_key, question_key, answer_value)` for better querying. Deferred.

---

## 7. Recommendation Ranking Logic

- **Current:** Per-category plugin scores items; filter score_raw > 0; sort by norm_score; take top N.
- **No change** to scoring algorithm.
- **Enforce:** Only recommend for selected services; validate destination before calling; no silent fallback to Singapore.

---

## 8. Verification Steps

1. Select housing only → questionnaire shows only housing questions.
2. Select housing + schools → questionnaire shows both, grouped by service.
3. Save selected services → refresh → selections persist.
4. Answer questionnaire → click Save → refresh → answers persist.
5. Get recommendations → only selected services return results; destination required.
6. No autosave: changing an answer does not trigger POST until Save clicked.
7. Missing destination → clear error, no fallback.

---

## 9. Deferred Follow-up Items

- Normalized answer storage (per-question rows).
- Frontend rendering from `GET /api/services/questions` (Phase 1 keeps static wizard, backend ready).
- `POST /api/recommendations/batch` for single round-trip.
- Policy/budget integration in ranking.
- Immigration, settling-in, temp accommodation services (currently disabled in config).

---

## 10. Implementation Summary (Completed)

### Backend
- **question_schema.py** — Canonical question bank with service_category, criteria_key, options.
- **question_engine.py** — `generate_questions(selected_services, case_context, saved_answers)`.
- **GET /api/services/questions** — Returns dynamic questions for assignment; resolves case, selected services, saved answers.
- **GET /api/services/answers** — Accepts `assignment_id` or `case_id`.
- **POST /api/services/answers** — Unchanged; idempotent upsert.

### Frontend
- **ProvidersPage** — Explicit Save button; syncs selected services to context on load.
- **ServicesQuestions** — Loads saved answers on mount via `getServiceAnswers({ assignmentId })`; no autosave; explicit Save button in wizard.
- **ProvidersCriteriaWizard** — New `onSave`, `isSaving` props; Save button calls `onSave`; sync to parent on change (no API autosave).

### Verification Checklist
1. [ ] Select housing only → questionnaire shows only housing questions.
2. [ ] Save selected services → refresh → selections persist.
3. [ ] Answer questionnaire → click Save → refresh → answers persist.
4. [ ] No autosave: changing an answer does not trigger POST until Save clicked.
5. [ ] Missing destination → clear error when getting recommendations.

# Services Flow Debug — Root Causes, Fixes, Verification

## 1. Root Causes

### Repeated POST /api/services/answers loop
- **Cause 1:** Debounce timeout callback did not re-check `autosaveEnabledRef` or a "get recommendations in progress" flag. A timeout scheduled before the user clicked "Get recommendations" could still fire 500ms later and trigger `onAnswersChange` → save, even while `workflow.isBusy` was true.
- **Cause 2:** No explicit guard during "Get recommendations" to block autosave from firing.
- **Cause 3:** `stableInitialAnswers` depended on `[initialAnswers, answers]`; context `answers` updates could cause repeated sync-effect runs (mitigated by `initialSyncDoneRef`, but the debounce timeout callback was the main gap).

### Recommendation context inconsistency (Singapore fallback)
- **Cause 1:** `caseToInitialAnswers` used `(destCity || destCountry || 'Singapore').trim()` — empty destination fell back to Singapore.
- **Cause 2:** `buildCriteriaFromAnswers` used `criteria.destination_city || 'Singapore'` for housing and schools.
- **Cause 3:** Backend `engine.py` used `dest_city = (criteria.get("destination_city") or "Singapore").strip()`.
- **Cause 4:** Plugins (living_areas, schools) had Pydantic defaults and score logic with `"Singapore"` fallbacks.
- **Cause 5:** No frontend or backend validation requiring a non-empty destination before recommendations.

---

## 2. Files Changed

| File | Changes |
|------|---------|
| `frontend/src/features/recommendations/ProvidersCriteriaWizard.tsx` | `getRecommendationsInProgressRef`, timeout callback checks, destination validation, removed Singapore fallbacks in criteria, `resolved_destination_context` log |
| `frontend/src/pages/services/ServicesQuestions.tsx` | Removed Singapore fallback in `caseToInitialAnswers` |
| `frontend/src/features/services/servicesWorkflowInstrumentation.ts` | Added `save_answers_*`, `recommendations_*`, `resolved_destination_context` events |
| `backend/app/recommendations/router.py` | Destination validation for destination-requiring categories, `dest_city` in logs |
| `backend/app/recommendations/engine.py` | Removed Singapore fallback for `dest_city` |

---

## 3. Loop Fix

- **`getRecommendationsInProgressRef`:** Set to `true` when "Get recommendations" starts, `false` in `finally` and on unmount.
- **Debounce callback:** Before calling `onAnswersChange`, checks `autosaveEnabledRef.current` and `getRecommendationsInProgressRef.current`; skips save if either is true.
- **Unmount cleanup:** `getRecommendationsInProgressRef.current = false` in the cleanup effect.
- **Result:** Autosave does not run while saving or loading recommendations, and any pending debounce timeout is effectively ignored.

---

## 4. Context Consistency Fix

- **Frontend:** Removed all `'Singapore'` fallbacks in `caseToInitialAnswers` and `buildCriteriaFromAnswers`; use empty string when missing.
- **Frontend validation:** Before "Get recommendations", require non-empty destination city when housing/schools/movers are selected.
- **Backend:** `DESTINATION_REQUIRING` check; return 400 with a clear message when `destination_city` is empty.
- **Backend:** `engine.py` no longer substitutes Singapore; use only what is in `criteria`.

---

## 5. Validation Rules Added

| Layer | Rule |
|-------|------|
| Frontend | If housing/schools/movers selected and `dest_city` is empty → show inline error, block "Get recommendations" |
| Backend | If `category in DESTINATION_REQUIRING` and `destination_city` empty → 400 with message: "destination_city is required for this category..." |

---

## 6. Verification Steps

### DevTools Network
1. Open Network → Fetch/XHR → Preserve log.
2. Go to `/services/questions`, edit one field, wait 500ms.
   - **Expect:** At most one `POST /api/services/answers`.
3. Click "Get recommendations".
   - **Expect:** CTA shows "Saving preferences...", then "Loading recommendations...".
   - **Expect:** One `POST /api/services/answers`, then one `POST /api/recommendations/{category}` per selected service.
   - **Expect:** No burst of repeated POSTs.
4. Go to `/services/recommendations`.
   - **Expect:** No `POST /api/services/answers`.

### Destination validation
5. Clear destination city (or use a case with no destination), click "Get recommendations" with housing/schools/movers selected.
   - **Expect:** Inline error: "Please enter a destination city..."
6. Enter destination, click "Get recommendations".
   - **Expect:** Recommendations request payload includes `destination_city` with the entered city.

### Console
7. In console, look for `[services-workflow] resolved_destination_context` and confirm `dest_city` matches the destination.

### Backend logs
8. In server logs, look for `recommendations_load succeeded` and `dest_city=...` (or `rejected_missing_destination` if validation runs).

---

## 7. Deferred Follow-Up

- Pass `case_id` and `assignment_id` into `resolved_destination_context` from parent for full trace.
- Enrich recommendations API to accept `assignment_id` / `case_id` and validate assignment/case on backend.
- Add canonical destination resolution from case when preferences omit destination.

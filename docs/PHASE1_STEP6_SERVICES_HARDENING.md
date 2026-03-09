# Phase 1 Step 6: Services Workflow Hardening — Implementation Summary

## 1. Exact Files Changed

| File | Purpose |
|------|---------|
| `frontend/src/features/services/useServicesWorkflowState.ts` | **NEW** — Workflow state machine |
| `frontend/src/features/services/servicesWorkflowInstrumentation.ts` | **NEW** — Frontend logging |
| `frontend/src/pages/services/ServicesQuestions.tsx` | Workflow orchestration, one-shot save+load, dedupe |
| `frontend/src/features/recommendations/ProvidersCriteriaWizard.tsx` | Autosave lifecycle, unmount cleanup, hydration guard |
| `backend/main.py` | Idempotency for `POST /api/services/answers` |
| `backend/app/recommendations/router.py` | Instrumentation for recommendations |

---

## 2. Workflow State Machine

**Owner:** `useServicesWorkflowState` hook, used in `ServicesQuestions.tsx`

**States:**
- `idle` — initial
- `editing` — user started editing
- `saving_answers` — explicit save in progress
- `answers_saved` — save completed
- `loading_recommendations` — fetching recommendations
- `recommendations_ready` — success, navigates
- `error` — any failure

**Transitions:**
- `idle` → `editing` — `onEditingStart` (first user edit)
- `editing` → `saving_answers` — "Get recommendations" click
- `saving_answers` → `answers_saved` — save success
- `answers_saved` → `loading_recommendations` — before fetch
- `loading_recommendations` → `recommendations_ready` — fetch success, navigate
- `*` → `error` — save or fetch failure
- `error` → `editing` — Retry

---

## 3. Frontend Fixes

| Fix | Implementation |
|-----|----------------|
| **Autosave only on Preferences** | `autosaveEnabled={!workflow.isBusy}`; debounce effect checks `autosaveEnabledRef.current` |
| **Cancel timers on unmount** | Debounce effect returns `() => window.clearTimeout(handle)` |
| **Mounted guard** | `isMountedRef` — timeout callback does nothing if unmounted |
| **Hydration guard** | `isHydratingRef` + `initialSyncDoneRef` — no save during initial sync from `initialAnswers` |
| **One-shot "Get recommendations"** | `saveAnswersBeforeLoad` → fetch → `onComplete`; CTA disabled when `isBusy` |
| **Duplicate save skip** | `lastSavedPayloadRef` compares `JSON.stringify(items)` |
| **Concurrent request guard** | `saveInFlightRef` blocks new autosave while one is in flight |
| **Stable callbacks** | `onAnswersChange` via `useCallback`; debounce uses ref, depends only on `[answers]` |

---

## 4. Backend Idempotency / Dedupe

**File:** `backend/main.py` — `upsert_service_answers`

**Logic:**
1. Fetch existing answers via `list_case_service_answers`
2. Normalize incoming and existing with `_normalize_answers_for_compare` (stable JSON)
3. If payload is identical → `return {"ok": True, "skipped_duplicate": True}` (no writes)
4. Else → upsert as before

**Logging:**
- `saved` — writes performed
- `skipped_duplicate` — no writes
- `failed` — exception

---

## 5. Verification Checklist (Chrome DevTools)

### A. Preferences step

1. Open DevTools → Network → preserve log, filter Fetch/XHR.
2. Go to `/services` → select services → `/services/questions`.
3. **Edit one field.** Expect at most one `POST /api/services/answers` after ~500 ms.
4. **Edit again.** Expect one more POST after debounce.
5. **No storm:** No burst of many POSTs while typing or on rerender.

### B. Get recommendations

6. Click "Get recommendations".
7. Expect:
   - CTA shows "Saving preferences..." then "Loading recommendations..."
   - One `POST /api/services/answers`
   - One `POST /api/recommendations/{category}` per selected service
8. **No repeated POST /api/services/answers** during or after navigation.

### C. Recommendations page

9. Land on `/services/recommendations`.
10. **Confirm:** No `POST /api/services/answers` requests from this page.
11. Page uses only `recommendations` and `shortlist` from context; no save logic.

### D. Duplicate suppression

12. Edit a field, wait for autosave. Click "Get recommendations" without further edits.
13. First save may be skipped (client or backend dedupe).
14. Check backend logs for `skipped_duplicate` when payload is unchanged.

---

## 6. Confirmation: /services/recommendations Does Not Trigger POST /api/services/answers

**Verified:** `ServicesRecommendations.tsx` does not render `ProvidersCriteriaWizard`, does not call `saveServiceAnswers`, and does not import the services answers API. The only callers of `saveServiceAnswers` are in `ServicesQuestions.tsx`, which is unmounted when navigating to `/services/recommendations`.

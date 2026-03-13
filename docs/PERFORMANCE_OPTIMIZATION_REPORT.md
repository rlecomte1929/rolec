# ReloPass Services & Recommendations Performance Optimization

## 1. Hot Path Audit

### Services questions load (ServicesQuestions.tsx)

| Step | Before | After |
|------|--------|-------|
| Assignment + services | `GET /api/employee/assignments/{id}/services` | Combined |
| Case details | `GET /api/case-details-by-assignment?assignment_id=...` | Combined |
| Saved answers | `GET /api/services/answers?assignment_id=...` | Combined |
| Dynamic questions | `GET /api/services/questions?assignment_id=...` | Combined |
| **Total requests** | **4** | **1** |

### Answers save

- Single `POST /api/services/answers` — unchanged. No duplicate or redundant calls identified.

### Recommendations generation (batch)

- `POST /api/recommendations/batch` — previously ran `recommend()` **serially** for each category (housing, schools, movers, etc.). Each category:
  - Opened its own DB session for supplier registry lookups
  - Loaded datasets and scored items independently
- Now runs category recommendations **in parallel** via `ThreadPoolExecutor`.

### Supplier registry reads

- Each `recommend()` previously opened `SessionLocal()` inside `_load_dataset_with_registry()`. With parallel execution, these run concurrently; no shared-session reuse (deferred).

### RFQ preparation

- Not audited in this pass; RFQ flow was out of scope.

---

## 2. Top Bottlenecks Identified

1. **Four separate requests on ServicesQuestions mount** — serialized round-trips, redundant assignment/case visibility checks and DB lookups.
2. **Serial batch recommendations** — 3 categories × ~200–400ms each ≈ 600–1200ms; parallelizable.
3. **Duplicate context resolution** — `get_case_details_by_assignment` and `get_service_questions` both loaded case and derived dest/origin context.
4. **Repeated supplier capability queries** — one `search_by_service_destination` per category; each in its own session (no bulk fetch).

---

## 3. Files Changed

| File | Change |
|------|--------|
| `backend/main.py` | Added `GET /api/services/context` combined endpoint |
| `frontend/src/api/client.ts` | Added `servicesAPI.getServicesContext()` |
| `frontend/src/pages/services/ServicesQuestions.tsx` | Replaced 4 `useEffect`s with single `getServicesContext` call; removed `employeeAPI`, `getCaseDetailsByAssignmentId` imports |
| `backend/app/recommendations/router.py` | Parallelized batch loop with `ThreadPoolExecutor` |

---

## 4. Optimizations Implemented

### 4.1 Combined services context endpoint

- **Endpoint:** `GET /api/services/context?assignment_id=X&fallback_services=housing,schools,movers`
- **Returns:** `assignment_id`, `case_id`, `case_context`, `services`, `answers`, `questions`, `selected_services`
- **Effect:** One visibility check, one case load, one answers load, one question generation per page load.

### 4.2 Frontend consolidation

- Replaced four independent `useEffect` hooks with a single effect that calls `getServicesContext`.
- Removed imports: `employeeAPI`, `getCaseDetailsByAssignmentId`.

### 4.3 Parallel batch recommendations

- Uses `concurrent.futures.ThreadPoolExecutor` with `max_workers=min(6, len(criteria_map))`.
- Each category’s `recommend()` runs in parallel; results merged by `backend_key`.

---

## 5. Before / After Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Services questions page requests** | 4 | 1 | ~75% fewer requests |
| **Duplicate assignment/case lookups** | 4× | 1× | Eliminated |
| **Batch recommendations (3 categories)** | Serial (~600–1200ms) | Parallel (~200–400ms) | ~30–50% latency reduction |
| **Duplicate context resolution** | 2× (case + dest/origin) | 1× | Eliminated |

*Estimates assume typical network latency and similar backend processing per category.*

---

## 6. Verification Steps

1. **Services questions page**
   - Open `/services` → select housing, schools, movers → navigate to `/services/questions`.
   - In DevTools Network tab, confirm **one** request to `/api/services/context` instead of four separate calls.
   - Confirm questions, answers, and case context render correctly.

2. **Recommendations batch**
   - On ServicesQuestions, complete required fields and click "Get recommendations".
   - In Network tab, confirm single `POST /api/recommendations/batch` with lower total duration than before (check backend logs for `dur_ms`).

3. **Regression**
   - Save answers, reload page — saved values should appear.
   - Navigate services flow end-to-end (select services → questions → recommendations).

---

## 7. Deferred Items

| Item | Reason |
|------|--------|
| **Supplier registry session reuse** | Each `recommend()` uses its own session; sharing would require broader refactor. Parallel execution already improves latency. |
| **Frontend memoization of context** | Context includes answers that change on save. Short-TTL cache would risk staleness; 4→1 request reduction is the main gain. |
| **Trim recommendation payloads** | Response size not yet profiled; could add field filtering if payload size becomes an issue. |
| **RFQ preparation audit** | Out of scope for this iteration. |

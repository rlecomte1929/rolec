# Employee case flow — page-entry request audit

This document describes **which network calls fire** when employees open **My Case**, the **intake wizard**, and (briefly) **Services**, and how the employee-case performance pass changed the critical path.

## Routes & owners

| Area | Route / entry | Primary components |
|------|----------------|-------------------|
| My Case | `/employee/case/:caseId` (summary) | `EmployeeCaseSummary` |
| Wizard | `/employee/case/:caseId/wizard/:step` | `CaseWizardPage` + step components |
| Step 5 | wizard step `5` | `Step5ReviewCreate` |
| Services | `/services/*` | `ServicesFlowProvider` (mostly **localStorage**; few API calls on entry unless a page fetches) |

> **Note:** The `:caseId` path segment is the **assignment id** (Option A gating), resolved to a real `case` UUID via `case-details-by-assignment`.

---

## My Case (`EmployeeCaseSummary`)

### Request sequence (after changes)

1. **`GET /api/case-details-by-assignment?assignment_id=…`**  
   - **Owner:** `getCaseDetailsByAssignmentId` (`frontend/src/api/caseDetails.ts`).  
   - **Critical for first meaningful content:** yes (draft + legacy columns).  
   - **Deduped:** in-flight Map merges parallel callers (e.g. if summary and another surface mount together).

2. **`GET /api/employee/assignment-feedback?assignment_id=…`** (best-effort)  
   - **Owner:** `employeeAPI.getFeedback` in `load()`.  
   - **Critical:** no (sidebar / HR notes).  
   - **Parallel** with (1) after it starts; does not block draft render.

3. **`GET /api/assignments/{id}/timeline?include_links=false`**  
   - **Owner:** `RelocationTaskTracker` with **`deferredEnsureWhenEmpty`**.  
   - **Stage 1:** first request **without** `ensure_defaults` (read-only, fast).  
   - **Stage 2 (deferred ~350ms):** if still no milestones and session key not set, **one** request with `ensure_defaults=1`.  
   - **Critical:** no for intake text; yes for “plan” section UX.

### Previous issues

- Timeline used **`ensure_defaults=1` on first paint**, coupling summary load to milestone inserts and heavier DB work.
- Weak **skeleton** feedback while draft loaded.

---

## Wizard (`CaseWizardPage`)

### Request sequence

1. **`GET /api/case-details-by-assignment?assignment_id=…`**  
   - **Owner:** `loadCase` → `getCaseDetailsByAssignmentId`.  
   - **Critical:** yes (hydrate `draft`, set `resolvedCaseId`).  
   - **Deduped** via shared in-flight promise.

2. **`GET /api/relocation/case/{caseUuid}`**  
   - **Owner:** `loadRequirements` → `getRelocationCase`.  
   - **Runs only when `resolvedCaseId` is set** (real case UUID).  
   - **Previous bug:** effect also ran with **assignment id** before case resolved → redundant failing calls / churn.

3. **`GET /api/employee/assignments/current`**  
   - **Owner:** `employeeAPI.getCurrentAssignment` (DEV gating / journey).  
   - **Cached** ~30s in API client.

4. **`GET /api/employee/journey/next-question?assignmentId=…`** (conditional)  
   - When status `awaiting_intake` and no session HR notes.

5. **`GET /api/employee/assignment-feedback?assignment_id=…`**  
   - HR feedback list.

6. **Step 1 `onNext`:** **`POST` research** via `startResearch(caseId)` — **user-driven**, not on mount.

### Critical vs deferred

| Request | Critical for shell / answers | Notes |
|---------|------------------------------|--------|
| case-details-by-assignment | Yes | Single source for saved draft |
| relocation/case | No for field paint | Drives “next actions” / missing fields sidebar |
| current assignment / journey | No | Status + HR notes |
| feedback | No | |

### Wizard UX (after changes)

- **`caseHydrating`:** skeleton + “Restoring your answers…” until `loadCase` completes so steps are not a blank flash.

---

## Step 5 (`Step5ReviewCreate`)

| Request | Trigger | Role |
|---------|---------|------|
| `GET /api/relocation/case/{caseId}` | `caseId` effect | Requirements / missing fields |
| `GET /api/requirements/sufficiency?case_id=…` | `caseId` effect | Approved-policy missing fields for dossier |
| `GET` dossier questions | feature flag + missing fields | Dynamic dossier |

Sufficiency is **non-blocking**: UI shows a **section-level** “Calculating recommendations…” / degraded message; step content still renders.

---

## Services flow

`ServicesFlowProvider` hydrates from **localStorage** (`services_*` keys). Individual pages (e.g. `ServicesQuestions`) may call APIs when mounted; that path is separate from the case assignment gate and was **not** the main source of `sufficiency` / `timeline` 500s.

---

## Duplicate / wasteful calls found & fixes

| Issue | Mitigation |
|-------|------------|
| Duplicate `case-details-by-assignment` | In-flight dedupe in `getCaseDetailsByAssignmentId` |
| `getRelocationCase(assignmentId)` before UUID known | `loadRequirements` only runs with `resolvedCaseId` |
| Timeline `ensure_defaults` every My Case entry | Deferred + session key `rolec_timeline_ensured:{assignmentId}`; HR still uses immediate `ensureDefaults` |

---

## Likely causes of perceived lag (historical)

1. **Chained work:** timeline default creation on the same tick as first summary paint.  
2. **Wrong id** to relocation API → errors + retries + empty UI.  
3. **Sparse loading states** on wizard main column.  
4. **Backend 500s** on sufficiency / timeline (see `employee-case-500-errors.md`).

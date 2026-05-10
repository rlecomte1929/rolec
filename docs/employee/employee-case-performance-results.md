# Employee case performance — results & verification

## Summary of changes

| Theme | What changed |
|-------|----------------|
| Critical path | My Case loads **draft** and **timeline read** in parallel; **default milestone creation** deferred (employee) or explicit (HR). |
| Deduping | **`getCaseDetailsByAssignmentId`** coalesces in-flight requests per assignment id. |
| Wrong API id | Wizard **`getRelocationCase`** only after **`resolvedCaseId`** (real case UUID). |
| Backend safety | Sufficiency: safe JSON parse + structured **`compute_status`**; timeline ensure: wrapped inserts + safe draft parse. |
| UX | Wizard **hydration skeleton**; My Case **skeleton** + section labels; Step 5 **sufficiency** banner; timeline **degraded** copy. |
| Instrumentation | `frontend/src/utils/employeeJourneyPerf.ts` — log with `VITE_EMPLOYEE_PERF_LOG=1` or `import.meta.env.DEV`. |

## Before / after (qualitative)

| Metric | Before | After |
|--------|--------|--------|
| Request count on wizard entry | case-details + **relocation with wrong id** + parallel feedback | case-details once (deduped); relocation **only** after case UUID |
| My Case timeline | `ensure_defaults` on **first** timeline GET | Read-first GET; optional **one** deferred ensure |
| Sufficiency failures | Risk of **500** on bad `draft_json` | **200** + `compute_status` + message |
| First meaningful UI | Often blank step column | **“Restoring your answers…”** + skeleton |

Exact **request counts** and **LCP-style timings** should be re-measured in your environment (network latency, DB size). Use DevTools **Performance** + **Network** filters for `case-details-by-assignment`, `relocation/case`, `timeline`, `sufficiency`.

### Suggested `logEmployeeJourney` hooks (optional follow-up)

- Route entry (`CaseWizardPage`, `EmployeeCaseSummary` `useEffect` on `assignmentId`).  
- After `getCaseDetailsByAssignmentId` resolves (`event: case_details_ready`, `caseId`).  
- After timeline first paint (`event: timeline_read_ready`).  
- On sufficiency response (`event: sufficiency`, `compute_status`).

## Root causes of 500s (short)

1. **Sufficiency:** invalid `draft_json` → `ValueError` not mapped to degraded JSON.  
2. **Sufficiency / access:** `effective["id"]` KeyError.  
3. **Timeline ensure:** unhandled JSON parse or milestone upsert breaking entire handler.

## Requests moved off the critical path

- **Timeline `ensure_defaults`** — deferred on employee My Case (not removed for HR).  
- **Relocation classification data** — not required to paint wizard fields; still loads after case UUID.

## Loading feedback added

- **My Case:** skeleton grid + “Loading your saved case data…”; timeline subsection with its own loading copy.  
- **Wizard:** step column skeleton + “Restoring your answers…”.  
- **Step 5:** “Calculating recommendations…” and degraded sufficiency text.  
- **Timeline error / empty:** copy explaining basics may be needed; Retry / Create default plan.

## What to optimize next

- **React Query** (or similar) with stable keys for case details + timeline to control refetch-on-focus.  
- **Pagination / slimmer** `case-details-by-assignment` if payload grows.  
- **Indexes:** ensure `case_milestones(case_id, canonical_case_id)`, `case_assignments(case_id)`, dossier answer tables — see `backend/sql/render_performance_indexes.sql` / Supabase migrations.  
- **Step 5:** avoid duplicate `getRelocationCase` if parent already has `missing_fields` (pass props from wizard).

---

## Manual verification checklist

- [ ] **My Case** shows loading skeleton / message immediately.  
- [ ] Saved **draft** appears without waiting for timeline ensure.  
- [ ] **Timeline** loads or shows empty/retry without blocking summary.  
- [ ] **Wizard** step column shows restoration state, then fields.  
- [ ] **Step 5** shows sufficiency banner; page usable if API returns `insufficient_data` / error.  
- [ ] **Network:** no `GET /api/relocation/case/{assignmentUuid-looking-wrong}` before case id resolved (UUID should match case row).  
- [ ] **Network:** employee My Case first timeline GET has **no** `ensure_defaults`; optional second call may include it once per session.  
- [ ] **HR case** timeline still creates defaults when empty (`ensureDefaults` on `CaseTimeline`).  
- [ ] **Auth:** employee cannot access other assignments (403/404 unchanged intent).

# HR List Optimization Results

**Date:** 2025-03-19  
**Purpose:** Document before/after performance improvements for HR Assignments list.

---

## Before / After Load Model

### Before

| Aspect | Behavior |
|--------|----------|
| **Initial load** | `GET /api/hr/assignments` — all assignments, no limit |
| **Backend** | N+1: `get_latest_compliance_report` per assignment |
| **Response** | Array of AssignmentSummary with complianceStatus |
| **Frontend** | After list: auto 5× `GET /api/hr/assignments/{id}` for details |
| **Filter** | Client-side only; required details for destination |
| **Pagination** | None |

### After

| Aspect | Behavior |
|--------|----------|
| **Initial load** | `GET /api/hr/assignments?limit=25&offset=0` — first page only |
| **Backend** | No per-row compliance; single query + bulk cases |
| **Response** | `{ assignments, total }` — summary only |
| **Frontend** | No auto detail load; detail on row click (navigate to case) |
| **Filter** | Server-side: search, status, destination (debounced search) |
| **Pagination** | limit/offset; "Load more" appends next page |

---

## Before / After Request Count

| Scenario | Before | After |
|----------|--------|-------|
| Page entry (39 assignments) | 1 list + 5 detail = 6 requests | 1 list request |
| With filters applied | 1 list + 5 detail | 1 list request |
| Load more (25 more) | N/A | 1 list request |

---

## Before / After Payload Size

| Endpoint | Before | After |
|----------|--------|-------|
| List (25 items) | ~39 items + N compliance queries | 25 items, no compliance |
| Per assignment | complianceStatus from N+1 | complianceStatus=null |

---

## Before / After Time to First Visible List

| Metric | Before | After |
|--------|--------|-------|
| List query | ~21 s (39 items + N+1) | ~&lt;2 s (25 items, no N+1) |
| Blocking on details | 5 detail requests before useful display | None |
| First paint | After list + 5 details | After list only |

---

## Filters Added / Moved Server-Side

| Filter | Before | After |
|--------|--------|-------|
| **Search** (name/email) | Client-side | Server-side (ILIKE on identifier, first_name, last_name) |
| **Status** | Client-side | Server-side |
| **Destination** | Client-side (needed details) | Server-side (relocation_cases host_country, home_country) |
| **Departing soon** | Client-side | Removed (required profile data) |

---

## Detail Loading

| Trigger | Before | After |
|---------|--------|-------|
| Page entry | 5 details auto-loaded | None |
| Row click | Navigate to case summary | Same — case summary loads detail |
| "Load remaining details" | Manual, loaded all N | Removed |
| "Load more" | N/A | Fetches next page of summaries |

---

## Remaining Bottlenecks

- **Admin path:** `list_all_assignments` still returns full list; pagination applied in Python
- **HR without company:** `list_assignments_for_hr` — no server-side filters
- **Compliance status:** No longer in list; available only on detail view
- **Departing soon filter:** Removed (would need profile/target date in summary)

---

## Chrome DevTools Verification Checklist

- [ ] Open Assignments tab; Network shows 1 request to `/api/hr/assignments?limit=25&offset=0`
- [ ] Response time &lt; 3 s for 25 items
- [ ] No `GET /api/hr/assignments/{uuid}` on initial load
- [ ] Typing in search: debounced; new request after ~300 ms idle
- [ ] Apply filters: 1 new request with status/destination params
- [ ] Load more: 1 request with offset=25
- [ ] Row click: navigates to case summary; detail loads there
- [ ] Refresh: resets to first page

---

## References

- `backend/main.py`: list_hr_assignments
- `backend/database.py`: list_assignments_for_company_paginated, _list_assignments_for_company_core
- `frontend/src/pages/HrDashboard.tsx`
- `docs/performance/hr-list-loading-audit.md`

# HR List Loading Audit

**Date:** 2025-03-19  
**Purpose:** Document current request patterns, payloads, and bottlenecks for HR list pages to enable summary-first, filter-early, detail-on-demand optimization.

---

## Assignments Page (HrDashboard, `/hr/dashboard`)

### Current Request Pattern on Page Entry

| Order | Endpoint | Trigger | Payload |
|-------|----------|---------|---------|
| 1 | `GET /api/hr/assignments` | `loadAssignments()` on mount | **All** assignments for company (no limit) |
| 2–6 | `GET /api/hr/assignments/{id}` × 5 | `loadAssignmentDetails(data, 5)` after list returns | Full detail per assignment |

### Backend `list_hr_assignments` Behavior

- Fetches **all** assignments via `list_assignments_for_company(company_id)` — no pagination
- Bulk loads `relocation_cases` for case metadata (host_country, home_country, status, stage)
- **N+1:** For each assignment, calls `db.get_latest_compliance_report(assignment["id"])` — one query per row
- Returns `AssignmentSummary[]` with: id, caseId, employeeIdentifier, status, submittedAt, complianceStatus, employeeFirstName, employeeLastName, case (host_country, home_country, etc.)

### Backend `get_hr_assignment` (Detail) Behavior

- Fetches assignment, `get_employee_profile` (large profile_json), `get_latest_compliance_report`, `compute_completion_state`
- Returns full `AssignmentDetail` with profile, completeness, complianceReport

### Frontend Behavior

- **Search/filter:** Client-side only. Search uses `assignmentDetails[id]` for name (falls back to employeeIdentifier). Destination filter uses `detail?.profile?.movePlan?.destination` — requires loaded details
- **Display:** `displayName` can use summary (employeeFirstName, employeeLastName, employeeIdentifier). `displayDestination` uses `detail?.profile?.movePlan?.destination` — shows "—" until detail loaded. `formatRoute`, `formatDeadline` require detail
- **Summary has `case.host_country`** but UI uses profile for destination. Could use `case.host_country` for list display
- **Auto detail load:** After list returns, automatically loads 5 details. "Load remaining details" loads all N
- **No server-side filter, no pagination**

### Issues

1. List endpoint returns **all** assignments — 39+ rows observed, ~21 s
2. N+1 compliance report per assignment in list
3. Client-side filtering requires details for destination — forces detail load for filter to work
4. Auto-loads 5 details on entry; "Load remaining" can load 39
5. No search/filter applied at server

---

## Employees Page (HrEmployees, `/hr/employees`)

### Current Request Pattern

| Order | Endpoint | Trigger |
|-------|----------|---------|
| 1 | `GET /api/hr/employees` | `loadEmployees()` on mount |

### Backend

- `list_employees_with_profiles(company_id)` — single query with LEFT JOIN profiles
- Returns id, company_id, profile_id, band, assignment_type, status, full_name, email
- **No N+1**, single efficient query
- **No pagination**, **no server-side search**

### Frontend

- Loads all employees at once
- Simple list; no search or filter UI
- Click row → navigate to Employee Detail

### Issues

- Loads full list; if company has many employees, could be slow
- No search/filter

---

## Employee Detail (HrEmployeeDetail, `/hr/employees/:id`)

### Current Request Pattern

| Order | Endpoint | Trigger |
|-------|----------|---------|
| 1 | `GET /api/hr/employees/{id}` | On mount |

### Backend

- `get_employee_for_company` or `get_employee_by_profile_for_company` — single row, lightweight

### Status

- Lightweight; not a bottleneck

---

## Other HR List Pages

| Page | Endpoint | Behavior |
|------|----------|----------|
| HrComplianceCheck | `listAssignments()` | Loads full list, then `getAssignment(selectedId)` |
| HrAssignmentReview | `listAssignments()` | Loads full list for dropdown, then `getAssignment(caseId)` for selected |

Same pattern: load all assignments first.

---

## Summary vs Detail Mix

| Data | In Summary | In Detail | Used For List Display |
|------|------------|-----------|------------------------|
| Employee name | employeeFirstName, employeeLastName, employeeIdentifier | profile.primaryApplicant.fullName | Summary sufficient |
| Destination | case.host_country | profile.movePlan.destination | UI uses detail; summary has case |
| Route (origin→dest) | — | profile.movePlan | Detail only |
| Status | status | status | Summary |
| Next deadline | — | profile.movePlan.targetArrivalDate | Detail only |
| Compliance | complianceStatus (from N+1 report) | complianceReport | Both |

---

## Recommended Target Loading Strategy

### Assignments

1. **Summary endpoint:** Return lightweight list with: id, caseId, employeeIdentifier, employeeFirstName, employeeLastName, status, submittedAt, case.host_country, case.home_country (destination/origin). **Remove per-row compliance report from list** (or make optional/async).
2. **Pagination:** Limit 20–25 per page, offset or cursor
3. **Server-side filters:** search (name/email), status, destination, optionally origin
4. **Detail on demand:** Load only when user clicks row or opens detail view
5. **No auto detail load** on page entry

### Employees

1. **Summary endpoint:** Already lightweight; add pagination and search if list grows
2. **Server-side search** by name/email
3. **Pagination** if >50 employees

### General

- Filters applied at query level
- Debounced text search
- Initial load: first page only
- Skeleton/loading state for list
- Detail fetch on row click

---

## References

- `frontend/src/pages/HrDashboard.tsx`
- `frontend/src/pages/HrEmployees.tsx`
- `backend/main.py`: list_hr_assignments, get_hr_assignment
- `backend/database.py`: list_assignments_for_company, get_latest_compliance_report, list_employees_with_profiles

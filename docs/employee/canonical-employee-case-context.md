# Canonical employee case context (Phase 3–5, 7)

## Bootstrap structure (frontend)

Owned by **`EmployeeAssignmentContext`** (`frontend/src/contexts/EmployeeAssignmentContext.tsx`):

| Field | Meaning |
|-------|---------|
| `assignmentId` | Primary linked assignment id (`linked[0].assignment_id` from overview). |
| `primaryAssignmentCompany` | `{ id, name }` from `linked[0].company` (assignment-scoped). |
| `linkedSummaries` / `pendingSummaries` | Full overview rows (`linked` deduped by `assignment_id` in the provider). |
| `isLoading` | Overview in flight (single gate for “bootstrap resolving”). |
| `overviewError` | User-visible failure after overview request fails. |
| `refetch` | Clears `employee:current-assignment` + `employee:assignments-overview` caches and reloads. |

## Source of truth

| Concept | Source |
|---------|--------|
| **Assignment id** (primary) | Overview → deduped `linked[0].assignment_id`, then scoped by `resolveScopedAssignmentId` (`?assignment=`, stored preference, or picker). |
| **Relocation case id** | From `case-details-by-assignment` or wizard case load — canonical **per assignment**, not global. |
| **Company (HR-created)** | Overview row `company.id` / `company.name` (joined from `relocation_cases` + `companies` / HR user company on backend). |

## Precedence (multiple linked assignments)

From `resolveScopedAssignmentId` (`frontend/src/utils/employeeAssignmentScope.ts`), using **deduped** linked rows:

1. **`?assignment=`** — if it matches a linked `assignment_id`, use it (Services also persists this to `relopass_employee_preferred_assignment_*`).
2. **Stored preference** — last focus from `/employee/case/:id/…`, the assignment picker, or a single-assignment overview; kept only while that id is still in linked rows.
3. **0–1 distinct linked** — primary id, no picker.
4. **2+ distinct linked** and no valid query or preference — `needsPicker`.

## When overview loads

`shouldLoadEmployeeAssignmentOverview(pathname)` includes:

`/employee`, `/services`, `/quotes`, `/resources`, `/providers`, `/messages`, `/hr/policy`, `/employee/hr-policy`.

**Important:** fetch runs when `shouldFetch` toggles (e.g. login or entering these areas), **not** on every child path change (e.g. wizard step) — `loadAssignment` no longer depends on `pathname`.

## Caching

- **Overview:** `employee:assignments-overview` — 60s TTL (`frontend/src/api/client.ts`).
- **Current:** `employee:current-assignment` — 30s TTL; invalidated with overview on claim/link and on 401.

## Page consumption

- **Dashboard / journey / services / providers / quotes / resources** — `useEmployeeAssignment()` for assignment id + loading + errors.
- **Wizard** — same context for status row + company name for test fill; case payload still from case-details + patch APIs.
- **Header company** — `CompanyBrand` prefers `primaryAssignmentCompany` when present (see [company-display-linkage.md](./company-display-linkage.md)).

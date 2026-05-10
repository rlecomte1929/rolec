# Employee entry / assignment-ID page — audit

## Login → case entry flow (before change)

1. User authenticates; `useAuth` / post-login navigation sends **EMPLOYEE** users to `/employee/dashboard` (`EmployeeJourney`).
2. `EmployeeAssignmentProvider` wraps the app and calls `employeeAPI.getCurrentAssignment()` inside a `useEffect` (post-paint). The response is deduped via `cachedRequest('employee:current-assignment', 30_000, ...)`.
3. `EmployeeJourney` reads `assignmentId` and `isLoading` (`assignmentLoading`) from `useEmployeeAssignment()`.
4. **Manual assignment-ID UI** is rendered when `!assignmentId` — there was **no** check for `assignmentLoading`.
5. Because `isLoading` in context started as **`false`** until the effect ran, the first paint could show the **“Link your case manually”** card even for users who already had a linked assignment, until the fetch completed.

## Where the assignment-ID page is chosen

- **Route:** `App.tsx` maps `ROUTE_DEFS.employeeDashboard.path` (`/employee/dashboard`) → `EmployeeJourney`.
- **UI condition:** `EmployeeJourney.tsx` rendered the manual claim block when `!assignmentId` (no gate on loading).

## How linked assignment detection works (canonical)

- **API:** `GET /api/employee/assignments/current` via `employeeAPI.getCurrentAssignment()`.
- **Server:** `get_employee_assignment` in `backend/main.py` runs optional `_best_effort_reconcile_employee_assignments`, then `db.get_assignment_for_employee(effective_user_id, ...)`, returning **at most one** assignment (product rule for multiple rows is centralized in the DB layer).
- **Client cache:** Single key `employee:current-assignment` — invalidated on `claimAssignment` and on explicit refetch (cache clear + reload).

There is **no** parallel “shadow” link store; the provider is the single owner of “current assignment id” for the session UI.

## Race / duplicate-request notes

- **Deduping:** Concurrent mounts share the in-flight `cachedRequest` for 30s TTL — acceptable; refetch clears cache first.
- **Risk addressed:** Overlapping `refetch` + effect-driven fetch is handled with a **monotonic fetch generation** ref so only the latest completion clears `isLoading` and writes `assignmentId`.

## What needed to change (summary)

1. Treat **“resolving current assignment”** as loading **before** first paint on employee routes (`shouldFetch` initial state + layout sync when entering employee scope).
2. In `EmployeeJourney`, **do not** render the manual assignment-ID card while `assignmentLoading`.
3. While `assignmentId` is known but case stats are loading, show an explicit **“Assignment found. Loading your case…”** state (spinner + existing skeletons).
4. On case fetch error, keep **linked** users out of the claim flow (existing error path); only **unlinked** users see manual claim after resolution completes with `assignmentId === null`.
5. Add optional **entry instrumentation** (`VITE_EMPLOYEE_ENTRY_LOG`) for timings and skip/claim decisions.

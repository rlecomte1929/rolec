# Skip assignment-ID page — implementation results

## What changed

1. **`EmployeeAssignmentProvider`** (`frontend/src/contexts/EmployeeAssignmentContext.tsx`)
   - `isLoading` initializes to **`shouldFetch`** (employee + token + `/employee/*`) so the first paint does not assume “no assignment” before the network call.
   - **`useLayoutEffect`** sets `isLoading` when entering `shouldFetch`, and clears it when leaving employee scope (or losing auth).
   - **`loadAssignment`** centralizes fetch + cache invalidation, uses a **generation counter** so stale responses cannot flip `assignmentId` / `isLoading` after navigation or overlapping refetches.
   - Early exit (not on employee routes) **bumps** the generation so in-flight requests are ignored.
   - **`refetch()`** returns **`Promise<void>`** and awaits the same `loadAssignment(true)` path (cache clear + GET current).

2. **`EmployeeJourney`** (`frontend/src/pages/EmployeeJourney.tsx`)
   - While **`assignmentLoading`**, shows **`EmployeeAssignmentBootstrapCard`**: spinner + *“Checking for a linked assignment…”* — the manual assignment-ID card is **not** mounted.
   - After a linked assignment exists, while **case stats** load, shows a second bootstrap card: *“Assignment found. Loading your case…”* plus the existing skeleton grid.
   - **Unlinked** users still see the full dashboard (case link status, flowchart, manual claim) **after** resolution completes with `assignmentId === null`.
   - **Linked assignment + case fetch error**: existing error alert remains; user is **not** sent back to manual claim unless `assignmentId` is actually cleared by the server.

3. **Instrumentation** (`frontend/src/utils/employeeJourneyPerf.ts`)
   - **`logEmployeeEntry`** — enable with **`VITE_EMPLOYEE_ENTRY_LOG=1`** (or `true`), or it inherits dev / **`VITE_EMPLOYEE_PERF_LOG`**.
   - Events: `employee_dashboard_entry`, `assignment_resolution_complete` (includes `skippedManualAssignmentIdPage`, `hasLinkedAssignment`, `msSinceEntry`), `case_stats_loading_start`, `case_stats_loading_complete`, `case_stats_loading_failed` (HTTP status when available).

4. **Docs**
   - Audit: `docs/employee/skip-assignment-id-audit.md`
   - This file: `docs/employee/skip-assignment-id-results.md`

## How linked assignment detection works now

- **Single owner:** `EmployeeAssignmentProvider` + `GET /api/employee/assignments/current` via `employeeAPI.getCurrentAssignment()` and cache key `employee:current-assignment`.
- **No extra stores:** Same model as before; gating and loading semantics were fixed so UI matches server truth.

## Route for already-linked users

- **No new redirects.** After resolution, users remain on **`/employee/dashboard`** with the linked-assignment card and case summary widgets (same as before), avoiding auth ↔ assignment-ID ↔ dashboard loops.
- **Multiple assignments:** The API returns **one** “current” row via `get_assignment_for_employee` — no client-side selector was added.

## Loading copy / states

| Phase | UI |
|--------|-----|
| Resolving current assignment | Spinner + “Checking for a linked assignment…” |
| Linked + loading case stats | Spinner + “Assignment found. Loading your case…” + pulse skeletons |

## Unlinked users

- After `assignmentLoading` becomes false and `assignmentId` is null, the **manual claim** card and existing HR copy behave as before.

## Manual verification checklist

1. **Already-linked employee logs in** — No manual assignment-ID card on first paint; checking spinner; then linked card + stats (or case-loading message while slow).
2. **New employee, no assignment** — After checking spinner, manual assignment-ID flow appears.
3. **Previously claimed user returns** — Cached current-assignment; no claim flash; linked UI when applicable.
4. **Slow case fetch** — “Assignment found. Loading your case…” and skeletons visible until data arrives.
5. **Broken/stale linkage** — Server returns no assignment → after resolution, manual claim; if assignment exists but details fail → error message, not a redirect loop.

## Performance / duplicate requests

- One provider-driven fetch per `loadAssignment` invocation; **`cachedRequest`** still dedupes within TTL.
- Refetch clears cache then fetches once; generation guard prevents overlapping completions from clobbering state.

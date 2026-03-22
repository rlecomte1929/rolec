# Employee case flow — results & verification (Phase 10)

## Root causes of 500s (summary)

1. JSON serialization of Postgres-native types in assignment/overview responses.
2. Occasional SQL/join errors on `relocation_cases` ↔ `case_assignments` without degradation.
3. (Previously) missing readiness tables — separate migration track; not part of this change.

## Corrected model

- **Canonical bootstrap:** `EmployeeAssignmentContext` + cached `GET /api/employee/assignments/overview`.
- **Company display:** Overview-linked company for employees in `CompanyBrand`.
- **Wizard:** Fewer PATCH/no-op saves, fewer relocation reads, notify-hr only on step 4 → 5.

## Instrumentation

Existing: `trackAssignmentFlow` / `ASSIGNMENT_FLOW_EVENTS` in `EmployeeAssignmentContext` (overview duration, counts). Optional future work: aggregate counters for wizard PATCH/GET/notify per session in `perf/` module.

## Before / after (qualitative)

| Area | Before | After |
|------|--------|-------|
| Overview requests per wizard flow | ~1 per step + route churn | ~1 per session (same route scope) + 60s cache |
| `current` in wizard | Per mount | Removed in favor of overview row |
| PATCH + relocation + notify per step | Often 3+ calls per Continue | PATCH only on change; relocation refresh on step advance; notify once entering review |

## Manual verification checklist

1. Employee logs in after HR linked assignment — **no 500** on `overview` / `current` in Network tab.
2. Dashboard loads — overview succeeds; **no duplicate** “Could not load assignments” title/body.
3. Header **company** matches HR assignment company (not a stale generic `/api/company` when linked).
4. Wizard steps **1→4** — Network shows **no** repeated `overview` calls per step; assignment `current` not spammed.
5. Completing step 4 → 5 — **one** `notify-hr` (if backend accepts).
6. After intake, **Services** (`/services` or `/providers`) still resolves `assignmentId` from context (overview loaded for those prefixes).
7. No contradictory “no assignment” while overview shows linked rows unless `overviewError` is set.

## Known follow-ups

- Multi-assignment still requires `?assignment=` when `linkedCount > 1`.
- Company **logo** from assignment-scoped source not yet in overview API.

# UI Audit Task Intake

Prepared: 2026-06-13

Notion status: not created. No Notion connector is available in this workspace. The records below are deduplicated against repository text and ready for manual/API intake.

## P0 / Red

### Fix employee services-state ownership resolution

- Layer: Isolation / API
- Autonomy: Red
- Evidence: Employee GET and POST `/api/cases/d2e05b7a-014a-4479-8e6f-ee868ed0eef8/services-state` return 403 while other assignment-scoped employee endpoints return 200.
- Acceptance: sign in as `employee@testingapril.com`, open `/services`, select a service, reload; no 403 appears and the selection persists.
- Execution: inspect assignment-id versus case-id resolution in `backend/app/routers/services_state.py` and `require_case_access`; add legacy seeded employee coverage. Do not weaken tenant checks.

### Fix case vendor endpoint 500

- Layer: API
- Autonomy: Yellow
- Evidence: `GET /api/cases/367d9bbf-b607-faab-263e-7f4e48a805df/vendors` returns 500; HR case detail renders no explicit error.
- Acceptance: open `/hr/cases/d2e05b7a-014a-4479-8e6f-ee868ed0eef8`; vendor request returns 200 with an array and Suppliers & budget exits loading state.
- Execution: trace duplicate vendor handlers in `backend/app/routers/cases_read.py` and `backend/app/routers/cases.py`; preserve tenant authorization and add a seeded-case regression test.

## P1 / Orange

### Align HR case-detail endpoint contract

- Layer: API
- Autonomy: Yellow
- Evidence: automated `HP2` gets 404 from `GET /api/hr/cases/{id}` while the UI uses `/api/hr/assignments/{assignmentId}` successfully.
- Acceptance: the documented canonical route returns 200 for the owning HR, or the runner/UI are updated to one canonical endpoint.

### Reduce authenticated page API latency

- Layer: API
- Autonomy: Yellow
- Evidence: HR assignments 7505 ms; employee assignments overview 7718 ms; policy config 3049 ms; command-center cases 3854 ms.
- Acceptance: p95 under 2000 ms for each endpoint with the Testing April fixture.

### Prevent draft case creation when opening New case

- Layer: UI / API
- Autonomy: Yellow
- Evidence: clicking New case issues `POST /api/hr/cases` before the user submits the inline form.
- Acceptance: open and cancel New case; no POST occurs and no draft is added. Submit a complete form; one case and one assignment are created.

### Reconcile employee Roadmap and Tasks sources

- Layer: UI / API
- Autonomy: Yellow
- Evidence: Roadmap shows overdue employee-owned tasks while `/employee/tasks` says no tasks are assigned.
- Acceptance: the same actionable employee work appears consistently in both surfaces or the UI clearly distinguishes roadmap milestones from HR-assigned tasks.

### Unify admin company metrics

- Layer: UI / API
- Autonomy: Yellow
- Evidence: Admin overview shows 95 HR users and 522 employees; Companies shows zero across all 56 active tenants.
- Acceptance: overview and Companies use the same scoped source and agree for All tenants.

## P2 / Yellow and Green

### Surface services persistence failure in the UI

- Layer: UI
- Autonomy: Yellow
- Evidence: services-state GET/POST 403 errors are swallowed and local state makes the page look saved.
- Acceptance: when persistence fails, show "Your choices are saved on this device only" with Retry; do not claim cross-device persistence.

### Handle absent public routes explicitly

- Layer: UI
- Autonomy: Green
- Evidence: `/pricing` and `/about` silently redirect to `/`.
- Acceptance: each route has intended content or a clear not-found response; no silent homepage redirect.

### Fix logout secondary 403

- Layer: Auth / UI
- Autonomy: Red
- Evidence: backend logout returns 200, then Supabase global logout returns 403 before redirect.
- Acceptance: logout clears the session and redirects without failed auth requests or console errors.

### Correct runner API-only and rate-limit sequencing

- Layer: Test infrastructure
- Autonomy: Green
- Evidence: `--api-only` executes only auth; immediate targeted rerun is contaminated by 429 responses.
- Acceptance: API-only runs all API suites without persona flows, and the rate-limit test runs last with an explicit cooldown note or isolated credentials/IP strategy.

## Completed Locally

### Public operating-layer hero and CTA

- Layer: UI
- Autonomy: Green
- Status: fixed locally, awaiting deployment/review.
- Acceptance: `/` contains "Run every relocation case through one operating layer" and the primary CTA "Structure how you run relocation. Start with one case."

### Policy lifecycle contradiction

- Layer: UI
- Autonomy: Yellow
- Status: fixed locally with regression test.
- Acceptance: a normalized published version never renders the no-policy onboarding state when the policy list is empty.

### Employee and provider empty-state copy

- Layer: UI
- Autonomy: Green
- Status: fixed locally.
- Acceptance: Tasks and Dossier set expectations; Provider status uses the current "Mobility center" navigation name.


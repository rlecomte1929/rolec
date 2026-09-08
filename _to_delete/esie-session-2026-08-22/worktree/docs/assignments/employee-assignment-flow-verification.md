# Employee assignment linking — instrumentation and verification matrix

This document describes how to **instrument** and **prove** the employee assignment-linking experience (post-login overview, hub vs manual assignment ID, pending rows, manual UUID claim, and idempotent re-claims).

Related: [multi-assignment-routing.md](./multi-assignment-routing.md), [linked-vs-pending-model.md](./linked-vs-pending-model.md).

---

## How to enable instrumentation

### Browser (frontend)

Set in the frontend env (e.g. `.env.local`):

```bash
VITE_ASSIGNMENT_FLOW_LOG=1
```

Or rely on a **development build** (`import.meta.env.DEV`), where assignment-flow logs are also emitted.

Open DevTools → **Console**, filter by:

- `[assignment-flow]` — structured objects with `event`, `t`, and `detail`.

Optional programmatic access (e.g. from E2E or a debug snippet):

- `getAssignmentFlowLogBuffer()` / `clearAssignmentFlowLogBuffer()` from `frontend/src/perf/assignmentLinkingInstrumentation.ts` (import in dev-only code).

### Employee dashboard timings (narrower)

`VITE_EMPLOYEE_ENTRY_LOG=1` enables `[employee-entry]` lines from `logEmployeeEntry` (e.g. `assignment_resolution_complete`) without turning on full `[employee-journey]` noise.

### API / server logs

Structured JSON lines prefixed with **`identity_obs`** (see `backend/identity_observability.py`). Useful events:

| Event | When |
|--------|------|
| `identity.assignments.overview` | Every `GET /api/employee/assignments/overview` — includes `linked_count`, `pending_count`, `auth_user_id`, `request_id` |
| `identity.claim.manual` | Manual UUID claim — `outcome`: `attached` or `idempotent_already_linked` |
| `identity.claim.manual.failed` | Manual claim rejected — `failure_code` (e.g. `ASSIGNMENT_NOT_FOUND`, `CLAIM_INVITE_REVOKED`) |
| `identity.claim.pending_explicit` | Hub “link pending” — `outcome`: `attached` or `idempotent_already_linked` |
| `identity.claim.pending_explicit.failed` | Pending link rejected — `failure_code` |

Correlate browser ↔ API using **`request_id`** when your proxy or app forwards `X-Request-ID` (if configured).

---

## Events tracked (client)

| `detail.event` (name) | Purpose |
|------------------------|---------|
| `assignment_flow.overview_lookup_start` | Overview fetch started (`pathname`, `clearCache`) |
| `assignment_flow.overview_lookup_complete` | Fetch finished — `ok`, `durationMs`, `linkedCount`, `pendingCount` |
| `assignment_flow.post_login_route` | After auth — `role`, `targetRouteKey`, `source` (`login` \| `register`) |
| `assignment_flow.hub_resolution` | Hub UI branch resolved — `scenario`, counts, `showPrimaryManualClaimPage`, `skippedManualAssignmentIdPage` |
| `assignment_flow.link_pending_attempt` | User clicked link on a **pending** row |
| `assignment_flow.link_pending_complete` | Result — `ok`, `alreadyLinked`, `errorCode` |
| `assignment_flow.manual_claim_attempt` | User submitted manual UUID claim |
| `assignment_flow.manual_claim_client_validation_failed` | No API call — `reason` (`missing_fields`, `assignment_id_in_login_field`, `email_in_assignment_field`) |
| `assignment_flow.manual_claim_complete` | API result — `ok`, `errorCode` |

**`hub_resolution.scenario`** mirrors the hub state machine:

- `linked` — at least one linked assignment
- `pending_only` — no linked, at least one pending
- `manual_fallback` — no linked, no pending (primary manual assignment ID experience)
- `overview_error` — overview request failed

---

## End-to-end scenario matrix

Use one row per run. Record **build / env**, **date**, and **tester**. Paste or summarize console + server lines in **Actual**.

| # | Scenario | Preconditions | High-level steps | Expected (UI + signals) | Actual | Pass |
|---|----------|---------------|------------------|---------------------------|--------|------|
| 1 | New user, **no** assignments | Fresh EMPLOYEE account; no linked/pending rows for that user | Register or login as employee; land on dashboard | **Manual assignment ID** primary experience (`showPrimaryManualClaimPage`). `[assignment-flow]` hub_resolution: `scenario: manual_fallback`, `linkedCount: 0`, `pendingCount: 0`. Server: `identity.assignments.overview` with `linked_count:0`, `pending_count:0`. | | ☐ |
| 2 | New user, **pending** only | HR created assignment with `pending_claim` + contact matched to user; not linked | Login | **Pending** hub (`scenario: pending_only`); Section B lists pending; **no** standalone “type UUID only” as the sole path (pending cards drive link). `skippedManualAssignmentIdPage: true`. Server: `pending_count ≥ 1`, `linked_count: 0`. | | ☐ |
| 3 | **One** linked, no pending | Single linked assignment | Login | Hub shows **Section A** linked case(s); **no** primary manual-only page. `scenario: linked`, `linkedCount: 1`. Optional: employee nav can deep-link to case summary (see `AppShell`). | | ☐ |
| 4 | One linked **+** new pending | Same as #3 plus an additional pending row for same account | Login | Linked cases in A; **banner** “A new assignment was found…” (until dismissed); pending in B. `scenario: linked`, `pendingCount ≥ 1`. | | ☐ |
| 5 | **Multiple** linked | ≥2 linked assignments | Login | Hub **“My assignments”** with multiple linked rows (Section A); multi-assignment routing uses picker/hub elsewhere per [multi-assignment-routing.md](./multi-assignment-routing.md). `linkedCount ≥ 2`. | | ☐ |
| 6 | Manual UUID claim (no auto pending) | Scenario #1; valid assignment UUID + identifier HR used | Enter login + assignment ID; submit | `manual_claim_attempt` → `manual_claim_complete` `ok: true`. Navigate to case summary. Server: `identity.claim.manual` `outcome: attached` (first time). | | ☐ |
| 7 | **Repeat** claim same assignment | After #6, return to dashboard; submit **same** UUID again | Same manual claim | **No duplicate** link side effects; API returns success. Server: `identity.claim.manual` with `outcome: idempotent_already_linked`. Client: `manual_claim_complete` `ok: true`. | | ☐ |
| 8 | (Optional) Repeat **pending** link | Pending row already linked | Click link again on same row | Server: `identity.claim.pending_explicit` `outcome: idempotent_already_linked`. Client: `link_pending_complete` `ok: true`, `alreadyLinked: true`. | | ☐ |

---

## Order-of-operations checklist (typical employee login)

1. `[assignment-flow] post_login_route` — `targetRouteKey: employeeDashboard`
2. `GET /api/employee/assignments/overview` (may run reconciliation server-side first)
3. `identity.assignments.overview` — counts
4. `overview_lookup_complete` — same counts client-side
5. `hub_resolution` — which UI branch rendered

---

## Known limitations

- **Client logs are not sent to analytics** by default; they are console/session-buffer only unless you wire `getAssignmentFlowLogBuffer()` into your E2E harness.
- **Assignment UUIDs** appear in client logs when claiming (for QA). Do not enable `VITE_ASSIGNMENT_FLOW_LOG` on shared machines with untrusted observers.
- **`post_login_route`** is emitted for **HR** and **EMPLOYEE** roles; filter on `role === 'EMPLOYEE'` for assignment-only verification.
- **Overview** is fetched when the app is on routes covered by `shouldLoadEmployeeAssignmentOverview` (e.g. `/employee`, `/services`, `/quotes`, `/resources`), not only the dashboard — expect multiple `overview_lookup_*` events when navigating.
- **Correlation**: if `request_id` is not propagated to the browser, match overview events by **time proximity** and **`auth_user_id`** in server logs vs session.
- **Impersonation / admin-as-employee**: confirm whether overview and claim endpoints behave as the impersonated principal in your environment before trusting counts in admin tests.

---

## Maintenance

When adding new assignment entry points, either:

- Reuse `trackAssignmentFlow` with a new `event` string and document it here, or
- Extend `ASSIGNMENT_FLOW_EVENTS` in `assignmentLinkingInstrumentation.ts` and update this matrix.

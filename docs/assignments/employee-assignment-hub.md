# Employee assignment hub

The **assignment hub** is the employee landing experience on **`/employee/dashboard`**, implemented in `frontend/src/pages/EmployeeJourney.tsx`. It is the single place to see **all linked** and **all pending** assignments in two clear sections, using only the lightweight overview API until the user chooses an action.

---

## Data source (performance)

| Concern | Approach |
|--------|----------|
| List data | `GET /api/employee/assignments/overview` via `employeeAPI.getAssignmentsOverview()` (see [employee-assignment-overview-endpoint.md](./employee-assignment-overview-endpoint.md)). |
| Full case payloads | **Not** loaded for every row on the hub. Case summary, services, wizard state, etc. load when the user navigates to `/employee/case/:assignmentId/...` or after a successful **Link assignment** (then navigate to case summary). |
| React state | `EmployeeAssignmentProvider` holds `linkedSummaries`, `pendingSummaries`, and a primary `assignmentId` (`linked[0]`) for global nav (e.g. header **My case**). |

---

## Page structure (top to bottom)

1. **Post-auth reconciliation alerts** (if present) — one-off messages after signup / claim flows.
2. **Loading** — while overview is in flight: *Checking your assignments…*
3. **Overview error** — retry refetch; manual claim still available when applicable.
4. **Inline errors** — claim / link failures.
5. **Assignment status** — compact summary badge + short explainer + relocation flow steps (unchanged high-level journey).
6. **Section A — Linked assignments** — always rendered after load (empty state if none).
7. **Section B — Pending assignments to link** — rendered only when `pendingCount > 0`.
8. **Manual assignment ID claim** — fallback when there is nothing to auto-match, or optional path when only pending rows exist.

---

## Section A — Linked assignments

**Purpose:** Show work already attached to the employee account. Supports **multiple** linked rows with equal treatment (no automatic “pick one” navigation).

### Fields shown (per row)

| Field | Source (overview `linked[]`) |
|-------|--------------------------------|
| Company | `company.name` |
| Destination | `destination.label` (or “Destination TBD”) |
| Status | `status` and `current_stage`, joined when both present |
| Last updated | `updated_at`, falling back to `created_at` |
| Assignment ID | `assignment_id` (mono, secondary) |

### Actions

| Control | Behavior |
|---------|----------|
| **Open case** | `navigate` to `/employee/case/:assignmentId/summary` — full case loads on that route, not on the hub. |

---

## Section B — Pending assignments to link

**Purpose:** Make **unlinked** HR-provisioned work obvious. The app does **not** auto-open any pending row; the employee must **Link assignment** (or use manual claim if blocked).

### Fields shown (per row)

| Field | Source (overview `pending[]`) |
|-------|-------------------------------|
| Label | Fixed product copy: **“New assignment found”** (info badge) |
| Company | `company.name` |
| Destination | `destination.label` |
| Created | `created_at` (formatted) |
| Claim state | `claim.state` when present (small secondary line) |
| Assignment ID | `assignment_id` (mono, secondary) |

### Actions

| Control | Behavior |
|---------|----------|
| **Link assignment** | Calls `POST /api/employee/assignments/{id}/link-pending` via `employeeAPI.linkPendingAssignment` (strict pending eligibility). Body repeats the signed-in email/username for confirmation. Then refetch overview and open **`/employee/case/:assignmentId/summary`**. See [explicit-link-assignment-flow.md](./explicit-link-assignment-flow.md). |
| Blocked rows | When `claim.state === invite_revoked` or `extra_verification_required`, the link button is hidden and copy points to HR / manual UUID entry below. |

---

## Related documentation

- [post-login-routing-rules.md](./post-login-routing-rules.md) — how counts drive which hub sections matter alongside manual fallback.
- [explicit-link-assignment-flow.md](./explicit-link-assignment-flow.md) — validation, errors, and idempotency for **Link assignment**.
- [manual-assignment-id-fallback.md](./manual-assignment-id-fallback.md) — primary vs secondary manual UUID path (`/claim`).
- [new-assignment-notification.md](./new-assignment-notification.md) — banner when linked + new pending.
- [linked-vs-pending-model.md](./linked-vs-pending-model.md) — domain definitions.

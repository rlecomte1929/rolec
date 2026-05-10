# Manual assignment ID fallback

Employees usually land on linked and/or **pending** rows from the overview (`GET /api/employee/assignments/overview`). When **neither** exists, they still need a way to attach a case using the UUID from HR.

---

## When the manual path appears

| Situation | UI |
|-----------|-----|
| **No linked** and **no pending** (overview empty or error treated as empty) | **Primary** card: *Link your case manually (assignment ID)* — full form always visible. This is the preserved “assignment ID page” experience on the hub. |
| **Has linked** and/or **has pending** | **Secondary** card: *Enter assignment ID manually* — collapsed by default (*Show form*). Does not block Section A / B. |
| Pending-only users | Secondary card starts **expanded** (same form) so optional UUID entry stays easy alongside Section B. |

There is **no separate route** for assignment ID: everything stays on `/employee/dashboard` (`EmployeeJourney`).

---

## How it differs from auto-detected pending (Section B)

| | Section B — Pending | Manual assignment ID |
|--|---------------------|----------------------|
| Detection | HR provisioned work matched to **employee contact** already linked to the user; `employee_link_mode = pending_claim`. | User supplies **assignment UUID**; no requirement to be on the pending list first. |
| Backend | `POST /api/employee/assignments/{id}/link-pending` — **strict** eligibility (pending_claim, contact, company, invites). | `POST /api/employee/assignments/{id}/claim` — **manual claim**: session identifier check + `assignment_identity_matches_user_identifiers` + invite revoked check + attach. |
| Use case | Normal “we found your email” flow. | Recovery, wrong/missing contact data, HR only shared UUID, legacy rows. |

---

## Same canonical link service (no parallel claim path)

Manual entry **does not** implement a second attach pipeline on the client.

1. User submits **login identifier** + **assignment ID** (UUID).
2. Frontend calls **`employeeAPI.claimAssignment(assignmentId, email)`** → `POST /api/employee/assignments/{assignment_id}/claim` with body `{ email }`.
3. Server **loads the assignment**, verifies the caller may claim it, **attaches** `employee_user_id`, clears link mode as appropriate, **marks invites**, **case participant** + **case event** (see `finalize_assignment_claim_attach` in `backend/services/explicit_pending_link_service.py`, shared with the manual claim route in `main.py`).

Pending **Link assignment** continues to use **`linkPendingAssignment`** only — a different, stricter endpoint by design.

After a successful manual claim, the app **refetches the overview** and navigates to **`/employee/case/{id}/summary`** so the user enters the normal linked flow.

---

## Related docs

- [explicit-link-assignment-flow.md](./explicit-link-assignment-flow.md) — pending explicit link.
- [employee-assignment-hub.md](./employee-assignment-hub.md) — Sections A / B and hub layout.
- [post-login-routing-rules.md](./post-login-routing-rules.md) — when manual fallback is the main scenario.

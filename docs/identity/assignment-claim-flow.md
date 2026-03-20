# Assignment claim & link flow (canonical)

This document describes the **canonical** employee path to connect an authenticated user to pre-provisioned **`employee_contacts`** and **`case_assignments`**, for both **existing accounts** (sign-in) and **new accounts** (sign-up).

---

## Lifecycle states (data)

| Layer | States / notes |
|--------|----------------|
| **`users`** | Real auth account; unique email (when present). |
| **`employee_contacts`** | Company-scoped; optional `linked_auth_user_id`; unique `(company_id, invite_key)`; optional unique `(company_id, email_normalized)` when email set. |
| **`case_assignments`** | `employee_user_id` null → unclaimed; set → linked to auth user. |
| **`assignment_claim_invites`** | `pending` → claimable; `claimed` → tied to completion of claim; `revoked` → HR cancelled auto/manual claim for this assignment. |
| **`assignment_invites`** | Legacy case-scoped token; `ACTIVE` / `CLAIMED`. |

---

## Canonical service

**Module:** `backend/services/assignment_claim_link_service.py`  
**Function:** `reconcile_pending_assignment_claims(...)`

### Responsibilities

1. **Normalize** principal identifiers: trimmed lowercase keys from **email** and **username** (`normalize_invite_key`).
2. **Discover `employee_contacts`**
   - Email-shaped keys: `list_employee_contacts_matching_signup_email` (`email_normalized` OR `invite_key`).
   - All keys: `list_employee_contacts_by_invite_key` (username / invite key per company).
   - De-dupe contacts by `id` (same person may match both paths).
3. **Validate / link contact → auth**
   - If `linked_auth_user_id` is set to **another** user → **skip** contact (`skippedContactsLinkedToOtherUser`); no cross-account hijack.
   - Else → `link_employee_contact_to_auth_user` (idempotent).
4. **Eligible assignments**
   - For each linked contact: `list_unassigned_assignments_for_employee_contact` (`employee_user_id IS NULL`).
   - **Legacy** rows (no `employee_contact_id`): `list_unassigned_assignments_legacy_for_identifiers`.
5. **Attach & claim**
   - Skip if `employee_user_id` already equals principal (**idempotent**, `skippedAlreadyLinkedSameUser`).
   - Skip if `employee_user_id` set to someone else (`skippedAssignmentsLinkedToOtherUser`).
   - Skip if **only revoked** claim invites exist for that assignment (`is_assignment_auto_claim_blocked_by_revoked_invites`) → `skippedRevokedInvites`.
   - Else: `attach_employee_to_assignment`, `mark_invites_claimed` (pending claim rows + legacy invites).
6. **Side effects** (when `emit_side_effects=True`): `ensure_case_participant`, `insert_case_event` (`assignment.claimed`) — only when an attach actually occurred in that step.

### Ambiguity & isolation

| Scenario | Rule |
|----------|------|
| Same email, multiple companies | Multiple `employee_contacts` rows → each processed independently; **no merging across companies**. |
| Same contact, multiple assignments | All unclaimed rows attached in one run. |
| Contact linked to another user | **Do not** re-link or attach; count skip. |
| Revoked-only claim invites | **Do not** auto-attach; HR explicitly revoked. |
| Legacy row, no contact | Match on normalized `employee_identifier` only. |

### Idempotency

Safe to call after **every** login, **every** register, and **each** `GET /api/employee/assignments/current` (and dashboard bootstrap). Re-runs do not create duplicate assignment ownership; skips increment counters instead of failing.

---

## Integration points

| When | Behavior |
|------|----------|
| **POST `/api/auth/register`** (EMPLOYEE, email or username) | Runs full reconcile + side effects; returns `LoginResponse.reconciliation` when anything linked or message applies. |
| **POST `/api/auth/login`** (EMPLOYEE) | Runs reconcile; returns **`reconciliation` only if** at least one **new** assignment was attached (reduces repeat banners). |
| **GET `/api/employee/assignments/current`** | Runs reconcile (unless impersonating) then returns current assignment. |
| **GET `/api/dashboard`** (employee, no profile yet) | Runs reconcile before resolving assignment-backed profile. |
| **POST `/api/employee/assignments/{id}/claim`** | Manual claim; **blocked** if revoked-only claim invites (403). |

### Backward-compatible signup helper

`reconcile_employee_signup_after_register` in the same module wraps the canonical function (username omitted for register payload that only had email historically). `signup_reconciliation.py` re-exports it.

---

## User-visible behavior (frontend)

- **Register / login** responses may include `reconciliation` with `headline`, `message`, `attachedAssignmentIds`, etc.
- Client stores a one-shot **`sessionStorage.post_auth_claim_reconciliation`** (legacy: `post_signup_reconciliation` still read for older sessions).
- **Employee dashboard (`EmployeeJourney`)** shows a **success** alert from `headline` + `message`, then refetches the current assignment.

Copy examples:

- *“We found relocation case(s) associated with your email”* + linked count message when new assignments attached.
- *“Your profile is connected”* when only contacts linked (e.g. register path) and no assignment yet.

---

## Related docs

- [signup-vs-employee-contact.md](./signup-vs-employee-contact.md) — auth vs operational email.
- [unified-assignment-creation.md](./unified-assignment-creation.md) — HR/Admin creates contact + assignment.
- [data-reconciliation-plan.md](./data-reconciliation-plan.md) — one-off audit / safe repair for legacy inconsistent rows (duplicates, missing `employee_contact_id`, invite drift).
- [guardrails.md](./guardrails.md) — enforced invariants (DB + services + structured API errors).
- [flexible-parallel-user-journeys.md](./flexible-parallel-user-journeys.md) — UX scenarios and user-visible messages.
- [../assignments/assignment-claim-flow.md](../assignments/assignment-claim-flow.md) — older narrative (may be partially superseded by this file).

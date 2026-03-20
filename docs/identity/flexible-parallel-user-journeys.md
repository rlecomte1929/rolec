# Flexible parallel user journeys (HR ↔ employee)

ReloPass supports **any order**: HR can create a case and assignment **before** the employee has an account, or the employee may **already** have signed up. Linking is driven by **matching identifiers** (normalized email or username) on the **company-scoped** `employee_contacts` record, not by a single global “profile email” blocking signup.

See also: [guardrails.md](./guardrails.md), [assignment-claim-flow.md](./assignment-claim-flow.md), [signup-vs-employee-contact.md](./signup-vs-employee-contact.md).

---

## Supported order-of-operations scenarios

| # | Order | What happens |
|---|--------|----------------|
| A | HR creates case → HR assigns (identifier) → employee **registers** with same email/username | After register, backend **reconciles**: links `employee_contact` → auth user, attaches unclaimed assignments, marks invites. |
| B | HR assigns first → employee **already has account** → employee **signs in** | On login, reconcile runs; **new** attaches surface in `reconciliation` for UX. |
| C | Employee **registers first** → HR later assigns using **same** identifier | Next time employee loads employee routes or signs in, reconcile attaches pending assignment. |
| D | HR assigns with identifier → employee registers with **different** login | No auto-link; employee uses **assignment ID + claim** flow with the **same** email/username as on their account (must match HR’s identifier or manual HR fix). |
| E | HR revokes claim invite | Auto-link blocked; user sees **structured** warning; must contact HR. |
| F | Ambiguous / another account owns contact | Reconcile **skips** stealing; user sees **manual check** messaging; HR resolves data. |

---

## User-visible messages (product copy)

These align with backend `PostSignupReconciliation` / `IdentityErrorCode` and frontend strings.

### Signup (`/auth`, Create Account)

- **Info (employee role):** Explains that HR may have added the work email to a case **before** signup; that does **not** block creating a ReloPass login. “Email already in use” only when the email is already an **auth** account (`users`).
- **Error `AUTH_EMAIL_TAKEN`:** Shown when a **real** login already exists — user should sign in instead.
- **Error `AUTH_USERNAME_TAKEN` / `AUTH_USER_CREATE_FAILED`:** Same pattern; message from API `detail.message`.

### After signup success (employee dashboard)

- **Headline + message** from API when assignments linked, e.g. *“We found relocation case(s) associated with your email”* and instructions to open **My case**.
- **Profile only:** *“Your profile is connected”* — contact linked, assignment may arrive later when HR assigns.
- **Warnings:** Revoked invite; could not link (other account / conflict) — ask user to contact HR.

### Sign-in (post-auth)

- Same `reconciliation` payload when **new** assignments were attached on this login (stored in `sessionStorage` for one display on employee dashboard).
- Login errors use `{ code, message }` (e.g. `AUTH_USER_NOT_FOUND`, `AUTH_WRONG_PASSWORD`).

### Employee dashboard / My case entry (`EmployeeJourney`)

- **Case link status** badge:
  - **Linked** — assignment on this account.
  - **Connected — waiting for an assignment** — contact linked, no assignment yet.
  - **No case linked yet** — use correct login or manual claim.
- **No case card:** Step-by-step: sign in with HR’s identifier → Refresh → or assignment ID + manual claim.
- **Manual claim errors:** API `detail.message` (e.g. `CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH`, `CLAIM_INVITE_REVOKED`, `CLAIM_ASSIGNMENT_ALREADY_CLAIMED`).

### HR dashboard — after assign

- Explains employee can **register later** or **sign in**; linking happens when identifiers match.
- Assignment ID copy; invite token described as **optional**.

### Admin — add assignment success

- Same parallel-journey explanation plus assignment ID copy.

---

## Expected behavior by scenario

| Scenario | Employee expectation | HR expectation |
|----------|---------------------|----------------|
| A (register after assign) | After create account, success banner + case appears or clear “refresh / claim” path. | Tell employee which **email/username** was entered on the assignment. |
| B (existing user, sign in) | After login, banner if new links; dashboard shows case. | Same identifier as in HR tool. |
| C (assign after register) | Next visit or refresh triggers link; no dead-end if copy explains “refresh”. | Use exact employee email/username. |
| D (wrong login) | Clear error on claim; dashboard says use HR’s identifier or ID. | Fix identifier or guide claim with ID. |
| E (revoked) | Warning + contact HR. | HR re-sends or fixes invite state. |
| F (ambiguous) | Warning to contact HR; no silent cross-account merge. | Data fix / reconciliation plan. |

---

## Frontend implementation notes

- `useAuth` persists `reconciliation` when headline, message, attached IDs, linked contact IDs, or **any** skip counter is non-zero (so warnings are not dropped).
- `EmployeeJourney` reads `post_auth_claim_reconciliation` / legacy `post_signup_reconciliation` once, then clears keys.
- `getApiErrorMessage` (`utils/apiDetail.ts`) and `formatRichMessage` (`utils/richMessage.tsx`) normalize FastAPI `detail` and `**bold**` in backend strings.

---

## Related docs

- [guardrails.md](./guardrails.md) — technical invariants
- [data-reconciliation-plan.md](./data-reconciliation-plan.md) — legacy data repair

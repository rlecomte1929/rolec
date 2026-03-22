# Multi-assignment routing and case scope

Employees may have **multiple linked assignments** at once. The app must not assume “one employee = one implicit current case” on cross-assignment routes. This document defines routing rules, how they interact with **pending** (unlinked) assignments, and fallbacks.

See also: [linked-vs-pending-model.md](./linked-vs-pending-model.md).

---

## Query parameter: `assignment`

For employee flows that need a **single** assignment id (services steps, quotes inbox, resources by assignment, policy fetches, etc.), the scoped assignment is:

- **`?assignment=<assignment_id>`** — must be one of the employee’s **linked** assignments when resolving scope; with **two or more distinct** linked ids (after deduping duplicate overview rows), a valid query **or** a stored preference (see below) avoids the picker.

Helpers live in `frontend/src/utils/employeeAssignmentScope.ts`:

- `parseAssignmentSearchParam` — read `assignment` from the URL.
- `resolveScopedAssignmentId` — decide `effectiveId` and whether a **picker** is required (`?assignment=` → localStorage preference → single primary → picker).
- `getPreferredEmployeeAssignmentId` / `setPreferredEmployeeAssignmentId` — persist last focused assignment (wizard/case URL, picker choice, or single linked row); cleared with other `relopass_*` keys on logout.
- `withAssignmentQuery(path, assignmentId)` — append/replace `assignment` while preserving other query keys.

---

## Linked assignments: 0 / 1 / many

| Linked count | Scoped assignment for “single-id” flows | Direct deep links |
|--------------|----------------------------------------|-------------------|
| **0** | No assignment id until the user completes onboarding / links an assignment. Show existing empty states or dashboard guidance. | N/A |
| **1** | Use the **primary** linked assignment from the employee overview (same as today). Optional `?assignment=` is accepted if it matches that linked id. | Allowed: e.g. open `/services`, `/quotes`, `/resources` without forcing `?assignment=`. |
| **2+ distinct** | **Do not** silently pick among assignments the user has never focused. Require a valid `?assignment=` **or** a stored preference that still matches the linked set; otherwise show the **assignment picker**. Duplicate overview rows for the same `assignment_id` count as one. | Choosing a row navigates with `?assignment=` set and updates preference. **Do not** require the user to manually type an assignment id. |

Opening one case or choosing one assignment for a flow **does not remove** other linked assignments from the hub or from the picker; navigation preserves the ability to switch via dashboard + picker + deep links with `?assignment=`.

---

## Pending assignments (not linked)

**Pending** rows (`pending_claim`, visible on the employee dashboard) are **separate** from linked scope:

- They are **not** eligible for `?assignment=` until linked via claim (or equivalent).
- The UI continues to list them in their own section on the hub; they are not mixed into the linked picker as selectable scope for API calls that require a linked assignment.
- The app **must not** auto-select a pending assignment as the scoped “current” assignment when resolving `effectiveId`.

---

## Fallback behavior

1. **Invalid or missing `?assignment=` with 2+ linked** — show the scoped **picker** for that surface (services, quotes, resources, RFQ new, etc.), not a random default case.
2. **Stale `?assignment=`** (id not in linked set) — treat like missing: picker if 2+ linked; otherwise fall back to primary or empty state per rules above.
3. **Case-scoped routes** — e.g. `/cases/:caseId/resources` use the **case id** from the path; assignment query resolution does not override that.
4. **Top navigation** — with multiple linked assignments, “my case” style entry points prefer the **dashboard / hub** so the employee sees all linked (and pending) work; with exactly one linked assignment, direct navigation to that case’s summary remains allowed (see `AppShell`).

---

## Surfaces using scoped resolution

Non-exhaustive list aligned with `shouldLoadEmployeeAssignmentOverview` and per-page `resolveScopedAssignmentId` usage:

- Employee dashboard / hub (`EmployeeJourney`) — canonical place to see **all** linked and pending rows.
- Services flow (`ProvidersPage`, `ServicesQuestions`, recommendations, estimate, nav ribbon, RFQ new).
- Quotes inbox and RFQ creation entry.
- Resources (`/resources` by assignment; case route unchanged).
- Components that load assignment-scoped data from URL context (e.g. package summary / policy caps where wired).

Internal links in these flows should preserve `location.search` (or call `withAssignmentQuery`) so switching assignment does not silently drop scope.

# New assignment notification (linked employees)

When an employee **already has linked assignments** and HR later creates **new pending** work against their contact, the hub should surface that clearly — without hijacking navigation or auto-opening a case.

---

## Where the notice appears

- **Page:** `/employee/dashboard` (`EmployeeJourney`), **above** the “Assignment status” card and **below** global alerts / errors.
- **Component:** A compact banner (border + light blue background) with title, short copy, and actions.

---

## When it appears

All must be true:

1. Assignment overview has finished loading (`!assignmentLoading`).
2. **`linkedCount > 0`** (employee already has at least one linked assignment).
3. **`pendingCount > 0`** (one or more pending rows in Section B).

The banner is **suppressed** when the user has **dismissed** it for the **current set** of pending assignment IDs.

### Dismissal and revisit

- **Storage:** `localStorage` key `relopass_employee_new_pending_banner_dismissed_{relopass_user_id}` (falls back to `anon` if user id missing).
- **Value:** A stable **signature** of pending rows: sorted `assignment_id` values, newline-separated.
- **Dismiss:** User clicks **Dismiss** → signature is stored → banner hides for that combination.
- **New work:** If HR adds another pending assignment (or the set of IDs changes), the signature no longer matches → the **banner shows again**.

This is **per browser profile**, not cross-device. Clearing site data resets dismissal.

**Review and link** scrolls smoothly to Section B (`#employee-hub-pending-assignments`) without opening a case.

---

## UX principles

- **No auto-navigation** to wizard/summary for the new assignment.
- **Section A** remains the path to existing linked cases; **Section B** lists pending rows with **Link assignment** (explicit link endpoint).
- Banner copy states that existing cases stay available and nothing opens until the user acts.

---

## Related docs

- [employee-assignment-hub.md](./employee-assignment-hub.md) — Section B behavior.
- [explicit-link-assignment-flow.md](./explicit-link-assignment-flow.md) — linking pending rows.
- [manual-assignment-id-fallback.md](./manual-assignment-id-fallback.md) — UUID fallback when auto-detection is not enough.

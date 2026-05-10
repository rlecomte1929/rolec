# Wizard request churn fix (Phase 6)

## Causes (before)

1. **`GET /api/employee/assignments/current`** on wizard mount for assignment status — redundant with overview and refetched when navigating steps indirectly via provider pathname churn.
2. **`PATCH /api/cases/:id`** on every Continue even when the draft was unchanged (e.g. double submit).
3. **`getRelocationCase` / loadRequirements** after **every** `handleSave` — including intermediate “Save” on a step.
4. **`POST /api/notifications/notify-hr`** after **every** successful save.

## New rules

| Action | Behavior |
|--------|----------|
| **Save (PATCH)** | Runs only if `JSON.stringify(draft)` differs from last saved snapshot (`lastSavedDraftJsonRef`). |
| **Requirements / relocation read** | Called when `resolvedCaseId` first appears, and on **step forward** (`handleNext`) after a successful save — not after every intermediate `onSave`. |
| **Notify HR** | Only when completing **step 4** (moving to review step 5), once per that transition — not on every patch. |
| **Assignment status** | Taken from **`linkedSummaries`** row for the route assignment id (overview), not `getCurrentAssignment`. |

## UX

- **“Restoring your saved details…”** banner while `caseHydrating` is true.

## Files

- `frontend/src/pages/employee/CaseWizardPage.tsx`

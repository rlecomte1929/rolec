# Immigration Checklist — On-Brand (E language) Implementation Plan

> Off `main` (foundation components merged). Design: approved `immigration-checklist-E.html`
> mockup + `docs/design/employee-journey-ui-brief.md`. Branch: `feat/employee-journey-immigration`.

**Goal:** Re-skin `ImmigrationChecklistPage` (route `/employee/case/:caseId/immigration/checklist`)
from its current **dark theme** (off-brand, likely unreadable on the light `AppShell`) to the
**E light navy/teal-on-white** language, reuse `StatusPill` for document statuses, and add the
content-honesty note. Keep all logic (fetch, upload, `CaseDocumentsPanel`, navigation) unchanged.

**Why:** This is the only dark-themed screen in the employee journey — a jarring inconsistency
(near-white text on the white AppShell is likely broken). Bring it in line with the rest.

---

## Single task (no new component): restyle `ImmigrationChecklistPage.tsx`

**File:** `frontend/src/pages/employee/ImmigrationChecklistPage.tsx`

This is a re-color + component-reuse pass. **Do not change** the data fetch (`GET
/api/employee/cases/{caseId}/immigration`), the `REQUIRED_DOCS`/`PERMIT_LABELS` maps, the
upload handler, `CaseDocumentsPanel`, the toast, or the navigation. Only change presentation.

**Changes:**
1. **Re-color every dark token to the E light language:**
   - Headings → `text-navy-800` (`#0b2b43`). Body/muted → `text-[#374151]` / `text-[#6b7280]`.
   - Page content on white cards (`Card` already = white rounded-xl border `#e2e8f0`). Remove
     all `#1e293b`/`#0f172a`/`#1e3a5f`/`#475569`/`#f1f5f9`/`#94a3b8`/`#e2e8f0`(as text) dark values.
   - Accent → teal `#1f8e8b`/`accent-500`. Progress fill → navy `#0b2b43` (not `#3b82f6`).
2. **Permit context card** (top, matching the mockup): a `Card` showing "Your permit: {PERMIT_LABELS[permit_type]}"
   with the corridor `{corridor_from} → {corridor_to}` and a muted "Based on your role and salary —
   confirmed by your relocation team." line. (Use `CountryFlag` next to the corridor countries if
   the values are country names — optional, only if it renders cleanly.)
3. **Completion strip:** keep the progress bar but re-color (navy fill on `#e2e8f0` track) and label
   it "{completedCount} of {docs.length} documents ready".
4. **Content-honesty note** (required): an antigravity `Alert variant="warning"` reading
   "Indicative — your case officer confirms the final document requirements with the immigration
   authority." Place it under the completion strip.
5. **Document rows → `StatusPill`:** replace the dark status circle + `Badge` with `StatusPill`.
   Map the `DocStatus` to a `JourneyStatus` + label:
   - `verified` → `<StatusPill status="ready">Verified</StatusPill>` (teal)
   - `uploaded` → `<StatusPill status="submitted">Uploaded</StatusPill>` (navy)
   - `in_review` (if present) → `<StatusPill status="in-review">In review</StatusPill>`
   - `blocked` (if present) → `<StatusPill status="blocked">Blocked</StatusPill>`
   - `not_started` / default → `<StatusPill status="action">Action needed</StatusPill>` (amber)
   Keep the per-row "Upload" `Button` for `not_started` (re-color to the antigravity default — it
   already uses `Button`, just ensure variant/size are on-brand).
   (Read the existing `STATUS_CONFIG`/`DocStatus` definitions at the top of the file to get the
   exact status keys; map whatever keys exist.)
6. **Secure-upload reassurance** (optional polish): keep the existing footer note but re-color; the
   mockup's "Upload securely — only your relocation team can see these documents" line is a fine
   replacement if it reads naturally.
7. Imports: add `StatusPill` (and `Alert` if not already) from `'../../components/antigravity'`.
   Remove `Badge` import if it becomes unused (tsc `noUnusedLocals` will flag it).

**Verify:**
- `cd frontend && npx tsc --noEmit` clean.
- `cd frontend && npx vitest run` full suite green (no test should depend on the dark classes; if
  one asserts a dark color string, update it to the new on-brand value).
- `cd frontend && npm run build` succeeds.
- Commit: `feat(employee-journey): on-brand immigration checklist (E language + StatusPill)`.

## Self-review
- Only presentation changed; fetch/upload/panel/nav untouched. Reuses `Card`/`Button`/`StatusPill`/
  `Alert`. No dark tokens remain. Content-honesty note added.

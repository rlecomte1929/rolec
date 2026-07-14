# Wire `getRequirements` into the employee UI

**Date:** 2026-07-14 · **Status:** approved design, ready for implementation plan

## Context

`GET /api/cases/{id}/requirements` is live and correct, and nothing renders it.
`frontend/src/api/cases.ts:54` defines `getRequirements` and no file imports it.

`Step5ReviewCreate.tsx:145` instead renders `buildRequirementsFromMissingFields(caseId, missing)`
(`frontend/src/api/relocation.ts:70`) — a **synthetic, client-side** `CaseRequirementsDTO` built from
`relocation.missing_fields`, in which every item is forced to `pillar: 'Intake'`,
`severity: 'BLOCKER'`, `statusForCase: 'MISSING'`. It never sets `staWaived` or `covered`.

Two consequences:

1. The destination requirements engine — nationality gating, the `nothing_to_do` anti-silence item,
   provenance, `staWaived`, `covered` — has **never reached a screen**. The `RequirementsCoverageNotice`
   and `staWaived` blocks already exist in `Step5ReviewCreate.tsx` and are coded against the *real*
   DTO; they are unreachable only because they are fed the synthetic one. Step 5 was always meant to
   consume this endpoint.
2. The two lists mean different things. `missing_fields` = "your intake form is incomplete."
   `getRequirements` = "here is what the destination legally requires of you." Step 5 has been
   showing the first while implying the second.

Outcome: Step 5 shows the real dossier, per pillar, with a correct "none required" answer where that
is the truth — and never renders a fetch failure as an empty list.

## Non-goals

- No new route or page. Step 5 is the home.
- No provenance vocabulary design — the badge already exists (§3c). Reuse it.
- No fix to the pre-existing intake/wizard flow beyond what this change touches.

---

## 1. Data flow (`Step5ReviewCreate.tsx`)

Split the single `getRelocationCase` effect, which currently derives two unrelated things:

- **`getRelocationCase(caseId)` — keep.** Sets `missingFields` only. It independently gates the
  dossier-suggestion button (`:471`), the submit flow (`:257`), and the empty-state copy (`:489`).
  Its role is *intake completeness*, which is what it always actually was.
- **`getRequirements(caseId)` — new.** Sets `requirements`. This is the destination dossier.

Independent fetches, independent failure modes. A failure in one must not blank the other.

`buildRequirementsFromMissingFields` loses its only caller → **delete it** and the import it orphans.
`buildNextActionsFromMissingFields`, directly above it in the same file, has other callers and stays.

## 2. Types (`frontend/src/types.ts:470`)

Backend field names verified against `backend/app/schemas.py:95-152` — the DTO already uses
`statusForCase` (not `status`), so no rename is needed.

```ts
export interface RequirementItemDTO {
  // …existing
  statusForCase: 'PROVIDED' | 'MISSING' | 'NEEDS_REVIEW' | 'CONFIRMED';   // + CONFIRMED
  outcomeType?: 'action' | 'nothing_to_do';                               // new
  reason?: string | null;                                                 // new
  verificationStatus?: 'representative' | 'corpus_grounded' | 'expert_verified' | null;
}

export interface CaseRequirementsDTO {
  // …existing
  nationalityWaived?: string[];                                           // new
  nationalityClass?: 'OWN_NATIONAL' | 'EU_EEA' | 'THIRD_COUNTRY' | null;  // new
}
```

## 3. `components/requirements/RequirementList.tsx`

**a. `nothing_to_do` → confirmation card.** Branch on `outcomeType === 'nothing_to_do'`:
positive/check styling, **`reason` as the body** (today `reason` is never read — it is the only
human-readable payload of the item and is dropped entirely), **no status badge**, **no action
buttons**. An item that asks nothing of anyone must not look like a pending task with an Upload
button on it.

**b. Action rows: gate the button row on `onAction`.** The four buttons (Upload / Answer / Ask HR /
Mark Reviewed) render unconditionally. `<RequirementList>` has **exactly one caller** — Step 5
(`:454`) — and it does not pass `onAction`. So all four buttons are dead no-ops *everywhere*, not
just on Step 5. Render them only when `onAction` is provided, which means they stop rendering
entirely until some caller wires an action. Keep the prop rather than deleting the buttons outright:
the affordances are the right ones, they simply have nothing behind them yet.

**c. Provenance badge — already built, do NOT rebuild.** `RequirementList.tsx:24-34` already has
`provenanceBadge(item.verificationStatus)`, wired into the row at `:54`, with labels including
`Representative`, and a test at `__tests__/RequirementList.provenance.test.tsx`. It has simply never
had real data. It will light up on its own once the real DTO arrives — the four hand-authored EU
items carry `verificationStatus: 'representative'`. **No work here.** Verify it renders; add nothing.

## 4. Step 5 — the explainers

`RequirementsCoverageNotice` and the `staWaived` block already exist and finally receive real data.
No change needed to either.

**Add a `nationalityWaived` explainer, gated on `nationalityClass`:**

```
render only when nationalityClass is 'OWN_NATIONAL' or 'EU_EEA'
```

This gate is load-bearing, not cosmetic. `nationalityWaived` is **not symmetric**:

- French national → the 9 visa items. Meaningful: *"the long-stay visa track doesn't apply to you."*
- Indian national → the **4 EU items**. Rendering that verbatim would say *"Justificatif de domicile
  doesn't apply to you"* — confusing and arguably false. Their list did not shrink; the EU items were
  never theirs to lose.

So: for `THIRD_COUNTRY`, render nothing.

## 5. Error / empty states — the honesty requirement

Today the fetch `.catch()` sets `requirements = null` and the section renders **nothing at all**.
On this screen, an empty list *means* "nothing is required of you." So a backend hiccup would
silently make a legal claim we never intended. Four states, kept distinct:

| state | render |
|---|---|
| loading | skeleton / "Loading your requirements…" |
| **fetch failed** | explicit error + retry. **Never** an empty section. |
| `covered === false` | existing `RequirementsCoverageNotice` (no catalog for this destination) |
| covered, zero items | honest "nothing required" empty state — the only case where empty is a *claim* |

The distinction between rows 2 and 4 is the whole point: a failure must never impersonate an answer.

## 6. Testing

- `RequirementList`: a `nothing_to_do` item renders the `reason`, renders **no** action buttons and
  **no** status badge; an `action` item with no `onAction` renders no buttons; with `onAction`,
  renders them.
- `RequirementList`: the **existing** provenance test file gains a case pinning that
  `verificationStatus: 'representative'` renders its badge (the existing tests cover
  `expert_verified` / `corpus_grounded` / absent, but not `representative` — the one status our
  hand-authored EU content actually carries).
- `Step5ReviewCreate`: `nationalityWaived` explainer renders for `OWN_NATIONAL`/`EU_EEA` and is
  **absent** for `THIRD_COUNTRY` (pin the asymmetry — this is the trap).
- `Step5ReviewCreate`: a rejected `getRequirements` renders the error state, **not** an empty list.
- Existing Step 5 tests must still pass: `missingFields` still gates the dossier button and submit.

Repo gotchas to respect: `vitest`/jsdom has no `localStorage` (shim a Map-backed one), and importing
`api/supabase` in a test breaks jsdom (mock it). Icons are `lucide-react` only.

## 7. Verification

Type-check (`npx tsc --noEmit`), `npx vitest`, `npm run build`. Then drive it: create a case with
`destCountry: France` and `nationality: French` and confirm Step 5 shows 4 items + the "No visa or
residence permit required" confirmation card with its reason and no buttons; repeat with
`nationality: Indian` and confirm 9 visa items, no confirmation card, and **no** waived explainer.

# PROMPT 3 (v2 amendments) — PDF Import: Mode-Aware Changes Only

## Context

This document amends Prompt 3 (PDF Import & AI Extraction Flow) to align with the two-mode architecture introduced in Prompt 1 v2. The original Prompt 3 remains valid in full — read it first. This document lists only the changes.

---

## Change 1 — Entry point

**Original**: Import flow triggered from the mode switcher in the header ("Import from document" button).

**Updated**: The entry point is unchanged, but the label and position shift slightly:
- In the page header, "Import from document" is now a secondary link-style button, positioned beside "Build from template" as a mode option — consistent with Prompt 1 v2 header design.
- The import flow still opens as a full-screen modal overlay on top of `/hr/policy-builder`.

---

## Change 2 — Post-import landing mode

**Original**: After import, HR lands back on the canvas (which no longer exists as the default view).

**Updated**: After import completes (Step 4 of the import flow — "Apply to canvas"), HR is dropped into **Adjust mode**, not Configure mode. Reason: the import has already made decisions about benefit values (the AI extracted them), so the guided card-by-card Configure flow would be redundant. HR should land in Adjust mode to review the imported values in the compact accordion list, where the change indicators immediately show them what was extracted and what differs from the template baseline.

Show a contextual banner at the top of the Adjust mode accordion immediately after import:
```
✓ Import complete — 18 benefits applied from [filename]. 
  Changes are highlighted in amber.  [View all changes]  [Dismiss]
```

The "View all changes" link opens the floating changes tray (Prompt 1 v2).

---

## Change 3 — Template interaction

**Original**: The import flow assumed the canvas was already set up with tiers.

**Updated**: If no template has been applied yet when HR initiates an import:
- Before showing Step 1 (Upload), show a one-step pre-screen: "Before importing, pick a baseline. The import will override specific benefits, keeping the rest at template defaults."
- Show the three template cards (Essential / Standard / Generous) in compact form (smaller than the full picker modal, ~200px each).
- HR selects one → template is applied → import flow begins at Step 1.
- This ensures the imported policy lands on top of a complete baseline, not a blank config.

---

## Change 4 — Market context in Step 3 (Review extraction)

**Original**: No market context shown during review.

**Updated**: In Step 3 (Review extraction), each extracted rule card now includes the same inline market context line as the Configure mode benefit card (Prompt 2a):

```
⬡ Platform median: €1,800 · Your extracted value: €2,500 · [Set to median]
```

This is collapsed by default, expanded on demand — consistent with the Configure mode card pattern.

---

## No other changes to Prompt 3.

All step content, API connections, UX constraints, and the 4-step flow structure remain as specified in the original Prompt 3.

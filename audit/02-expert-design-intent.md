# Plan-Mode Expert Review — Designer Lens (Intent)

**Reviewer lens:** "Is the design plan articulating a visual system that buyers will trust, employees will understand, and HR will find professional?"
**Docs reviewed:** `relopass-figma-spec.md` (Phase-1 wireframe spec, April 2026), `relopass-brand-audit-2026-04-23.md` (live-site scoring 27/50), prior synthesis §5 (W1, W2, W3 weaknesses).

**Score: 7.0 / 10** — the design intent is clearly articulated; what's missing is the bridge between that intent and the in-product surfaces (versus the marketing site).

What would make it a 10: a design system applied to the in-product surfaces with the same rigor the figma-spec applies to the marketing site, plus a copy guideline that explicitly forbids the jargon classes currently leaking through.

---

## Strengths

1. **Figma spec is rigorous on global rules** — 8px base unit, 12-column grid, typographic hierarchy, "no stock photos, no suitcases, no skylines" rules. Designer would respect this brief.
2. **Module grid framing** ("Cases / Timelines / Documents / Providers / Policy controls / Visibility") is correct — it claims architecture, not feature list.
3. **CTA discipline** ("Book a demo" + "See the platform" everywhere) is consistent.
4. **In-house design system exists** (`frontend/src/components/antigravity/`) — Button, Card, Input, Badge, Alert primitives.

## Findings

### DES-1 [P0] — Brand-site scoring is 27/50 despite design-system rigor in spec
Spec is rigorous; site does not implement it. Specific gaps from `relopass-brand-audit-2026-04-23.md`:
- **Differentiation** ("Not an agency. Not a marketplace. Not an HR add-on.") — absent site-wide.
- **Category clarity** ("operating layer", "infrastructure") — replaced by softer "workspace", "process" framing.
- **Compliance promise** ("audit-ready close", "policy applied at case creation") — absent.
- **Homepage missing 4 of 8 required arc sections.**

**Designer-lens read:** the spec exists but the build skipped it. Either the spec wasn't enforced at handoff, or it was written *after* the site shipped. Both are real failure modes.

### DES-2 [P0] — In-product UX has not received the same design discipline
Prior synthesis §5 W1 (P0): Employee Dashboard depth 1/5 — UUIDs, Section A/B language, manual claim form, 9 nav items. Verified live by full-stack audit: `EmployeeJourney.tsx:217,243` still renders "Assignment ID from HR (UUID)" as of 2026-05-25.

**Designer-lens read:** the figma spec defines the marketing site but does not define the *product* surfaces with the same rigor. The product is where the buyer's first impression actually forms post-demo — and that surface is currently 1/5.

### DES-3 [P0] — 37 raw `<button>`/`<input>` elements bypass the antigravity design system
Per full-stack audit, ~25 in admin pages, 7 in `Auth.tsx`, 5 in HR pages. Each raw element renders slightly different from the system Button/Input — borders, focus rings, hover states, spacing.
**Designer-lens read:** in-house design systems work only when used consistently. 37 bypasses are enough to make the product feel "almost designed" — worse than no system at all, because users sense the inconsistency without naming it.

### DES-4 [P1] — Copy guidelines do not forbid the jargon classes that are leaking
Brand voice exists (`relopass-brand-voice` skill). Brand audit identifies bad words ("workspace", "seamless", "powerful", "all-in-one"). But the **product copy** is leaking a different class of jargon: implementation vocabulary (UUID, Section A, Layer-2, snake_case task IDs). The brand voice doc does not explicitly forbid this class.
**Recommend:** add to the brand voice doc — "never expose internal vocabulary in user-facing copy. UUIDs are not visible; Section letters are not visible; task IDs use English titles, not slugs."

### DES-5 [P1] — Estimate Review (W2, P0 in prior synthesis) is the value-prop screen and has no design spec
Prior synthesis: "Estimate Review is the lightest surface despite being the value-prop screen." Side-Output A specifies the data model but not the visual hierarchy. The single screen that turns abstract policy into concrete cost guardrails has no figma spec equivalent to the marketing-site rigor.
**Recommend:** Phase-1 wireframe spec for Estimate Review at the same depth as the homepage section in `relopass-figma-spec.md`.

### DES-6 [P2] — Wizard (`/journey`, `/employee/case/:caseId/intake`) does not have a documented step-by-step UX
The intake wizard exists in two versions (legacy + v2). No prose-level design doc walks through the 5-7 steps, the empty/error states, the save-draft behavior, or the "what's next" surfacing between steps. The technical AI Work Queue items for the wizard (P2-3, P2-5, P5-3) capture mechanics but not the UX narrative.

### DES-7 [P2] — Pets section design flagged (AIQ-367887...8109 from May 2026) — but the broader Family intake section has the same issue
The same modal pattern (collapsed-section-at-bottom) likely affects dependents, spouse, dual-career flags. Worth a single design pass over the entire Family intake, not just pets.

---

## What the design plan needs (priority order)

1. **In-product design spec** at the depth of the marketing-site spec, especially: Employee Dashboard, Estimate Review, Intake Wizard, HR Command Center.
2. **Update brand voice** to forbid the implementation-jargon class.
3. **Migrate the 37 raw HTML elements** to the antigravity system. This is design *enforcement*, not design *creation*.
4. **A copy pass** explicitly on the W1 surface — the current "Assignment ID (UUID)" phrasing is the single most damaging in-product copy.
5. **A figma spec for the Estimate Review screen** — the value-prop screen that currently has none.

## What this lens is NOT saying

- Not telling you to redesign the marketing site brand. The spec is good; enforce it.
- Not telling you to abandon the antigravity system. It exists and is correct; bypass it less.
- Not telling you to over-design admin tools. Admin UI is internal-facing and can be functional-first.

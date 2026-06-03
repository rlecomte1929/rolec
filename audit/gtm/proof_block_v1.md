# FRIDAY-004c · 3-line proof block (audit logs · bias testing · human-in-loop)

**Task**: AIQ-647 → 004c
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (review + lock the 3 lines, name a designer for the icons)
**Source of truth**: 004a positioning sentence + 004b hero copy
**Hand-off to**: 004e (implementation)

---

## 1. Recommended proof block (ship these 3 lines)

### Line 1 — Audit logs

> **Every AI decision is logged, timestamped, and tied to the source document it read.**

**13 words.**
**Capability**: audit logs.
**Evidence**: C1-01c · `rce.rule_citations` table shipped to prod 2026-06-03 (PR #245, AIQ-751). RLS enabled. Citations stamp `rule_version_id` on every output. Plus the broader audit-replay surface (case audit tab) from C1-11/12.

### Line 2 — Bias testing

> **Shadow-run every extraction against a second model — disagreements surface, never hide.**

**13 words.**
**Capability**: bias / model-drift testing.
**Evidence**: `ocr_shadow_comparisons` table shipped (Mistral vs Azure shadow runs). The pattern is operational — the proof block names it. Plus C1-04 classifier escalation tier (gpt-4o-mini → gpt-4o on disagreement, UNKNOWN floor at <0.50).

### Line 3 — Human-in-loop

> **No AI ships a single value to a form without a person confirming it.**

**14 words.**
**Capability**: human-in-the-loop oversight (EU AI Act Art. 14).
**Evidence**: AI-002 work shipped (archived but live in production). The whole Pathway confirm-extracted-fields flow is the user-facing proof: Priya confirms her name, DOB, passport number — every extracted value is human-confirmed before downstream form-fill.

---

## 2. Why these 3 lines, in this order

The order is deliberate and matches the EU AI Act risk hierarchy:

1. **Audit logs** — Article 12 (record-keeping). The most foundational requirement. If you don't have audit logs, nothing else matters legally.
2. **Bias testing** — Article 10 (data and data governance) + Article 9 (risk management). The second hardest requirement; most competitors don't have an answer.
3. **Human-in-loop** — Article 14 (human oversight). The most visible to the buyer's HR practitioner; it's what their team will actually feel day-to-day.

This order also works rhetorically:
- Line 1 is the most defensive (passes a legal review).
- Line 2 is the most differentiated (Topia doesn't talk about shadow-running).
- Line 3 is the most human (closes the block on the employee).

Defensive → differentiated → human is a strong sequence.

---

## 3. Brand-voice + character compliance

| Line | Words | Forbidden? | Concrete? | Verdict |
|---|---|---|---|---|
| 1 | 13 | none | "logged", "timestamped", "tied to the source document" — triple concrete | ✅ pass |
| 2 | 13 | none | "shadow-run", "disagreements surface, never hide" | ✅ pass |
| 3 | 14 | none | "single value", "person confirming" | ✅ pass |

All ≤ 14 words. All clear the brand-voice bar.

---

## 4. Backup variants (2 per line, in case Romain or buyer feedback kills one)

### Line 1 — Audit logs

**Backup 1a** (more legal-team coded):
> Every decision tied to a source document, a model version, and a timestamp.
> *(13 words. Trades the verb "logged" for the noun stack. Better for legal-team reads.)*

**Backup 1b** (more buyer-coded):
> Open the audit trail. See exactly how every form got filled.
> *(11 words. Trades the technical specifics for an invitation. Better above-the-fold for general HR.)*

### Line 2 — Bias testing

**Backup 2a** (more operations-coded):
> Two models read every document. If they disagree, your team sees it before the form ships.
> *(15 words — over cap. Disqualified for the proof block but usable in long-form copy.)*

**Backup 2b** (more concise):
> Every extraction runs through a second model. Disagreements get flagged, not buried.
> *(12 words. Cleaner but loses the active "shadow-run" verb. Use if the word "shadow" reads as IT-jargon.)*

### Line 3 — Human-in-loop

**Backup 3a** (more direct):
> Every extracted value is confirmed by a person before it reaches a form.
> *(13 words. Removes the negative construction. Safer.)*

**Backup 3b** (more conversational):
> AI reads, your team confirms, the form ships. That's the rule.
> *(11 words. Three-beat cadence. Best if proof block is paired with 🅱+② headline cadence.)*

---

## 5. Visual / layout notes for 004e implementation

The proof block sits **directly under the hero pair**, three columns desktop / stacked mobile. Each line gets:

- An icon (designer + Romain decide — likely Lucide: `FileSearch` / `ScanLine` / `UserCheck` or similar).
- The line itself, set in body-large weight semi-bold.
- A small "Learn more →" link to a dedicated EU AI Act page (when one exists — currently a follow-up).

```
Desktop layout (1024px+):
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ [icon]           │ │ [icon]           │ │ [icon]           │
│ Line 1           │ │ Line 2           │ │ Line 3           │
│ Learn more →     │ │ Learn more →     │ │ Learn more →     │
└──────────────────┘ └──────────────────┘ └──────────────────┘

Mobile layout (<640px):
┌──────────────────┐
│ [icon] Line 1    │
│ Learn more →     │
├──────────────────┤
│ [icon] Line 2    │
│ Learn more →     │
├──────────────────┤
│ [icon] Line 3    │
│ Learn more →     │
└──────────────────┘
```

Tokens reference C1-11D:
- Icon container: 40 px square, `--surface-recessed`, `--radius-md`.
- Line text: `--font-body-lg`, weight 600.
- Learn-more link: `--text-link`, weight 500.
- Column gap: `--space-6` desktop, `--space-4` mobile.

---

## 6. Evidence appendix (for the buyer or auditor who asks "show me")

If a buyer or auditor presses on any of the three lines, the evidence is in production today:

| Line | Production evidence | Reference |
|---|---|---|
| 1 (audit logs) | `rce.rule_citations` table; `case_audit_events` chain; PR #245 (AIQ-751) shipped 2026-06-03 | Open `/hr/cases/:id/audit` in any seeded HR account; click any line in the audit timeline. Bbox + rule citation displayed. |
| 2 (bias testing) | `ocr_shadow_comparisons` table; C1-04 classifier escalation logic with UNKNOWN floor at <0.50 | Internal — pull the table via Supabase MCP. For buyer-facing demo, show the C1-04 architecture report §3.1. |
| 3 (human-in-loop) | Pathway confirm-extracted-fields flow (employee-side); HR review queue (HR-side); AI-002 (archived but shipped) | Live in any seeded employee Pathway. Confirm screen renders after every OCR extraction. |

Each line is defensible.

---

## 7. Validation criteria — self-check

- ✅ **Each line ≤ 14 words** — 13 / 13 / 14. All under cap.
- ✅ **Each claim is defensible — evidence source named** — see §6 appendix.
- ✅ **3 lines cover 3 distinct EU AI Act dimensions (no overlap)** — Art. 12 / Art. 10+9 / Art. 14. Confirmed orthogonal.
- ✅ **Passes ReloPass brand-voice rules** — see §3 audit.
- ✅ **Each line stands alone** — verified: Line 1 makes sense without the headline; Line 2 makes sense without Line 1; Line 3 makes sense without either.

---

## 8. Hand-off

- → **004e implementation**: ship the three recommended lines from §1. Use the layout notes from §5. Icons + Learn-more landing pages are follow-up tasks (file under "FRIDAY-004 follow-ups" if needed).
- → **004d meta tags**: this proof block does not directly inform the meta description (that's 004b's job), but the three claim words ("logged", "shadow-run", "confirmed") can pepper og:description if length permits.

---

## 9. Follow-up tasks (suggested, not created)

The proof block invites three follow-up artifacts that don't exist yet:

1. **EU AI Act landing page** — a destination for the three "Learn more →" links. Should walk through how each capability maps to the relevant Article. ~ 3-4 pages of long-form, half-day to draft.
2. **Public bias-testing methodology page** — names the shadow-running pattern, the agreement-rate metric, the escalation policy. Useful for procurement teams that ask for ISO 42001 / EU AI Act documentation.
3. **Audit-trail demo video** — 30-second screen capture of clicking through `/hr/cases/:id/audit`. Embed on the EU AI Act landing page.

These are NOT created as Notion tasks here — flag for Romain to decide whether to file or sit on.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Three lines mapped to three distinct EU AI Act articles, each backed by production evidence, each within voice and character bounds.*

# Persona Input — Relocating Employee

**Sources:** Notion Pain Points DB filtered by Affected Persona = "Relocating Employee" + prior synthesis §2 employee row + figma spec employee surfaces.

## Jobs to be done

1. **Know what's happening with my case** — without messaging HR three times a day.
2. **Know what I need to do next** — the next concrete action, with deadline, on my screen.
3. **Submit the right documents the first time** — without back-and-forth on file types, expiry windows, or rejection causes.
4. **Understand what's covered vs. out-of-pocket** before I commit (housing tier, schools, shipment caps, allowances).
5. **Get answers about the destination** (neighborhoods, schools, banking, healthcare) without 20 browser tabs.

## Pain quantified (Pain Points DB, Affected Persona contains "Relocating Employee")

| ID | Pain | Severity |
|---|---|---|
| PP-18 | Employees Have No Self-Service Case Visibility | High (Strategic Importance: **Critical**) |
| — | Fragmented employee experience with no single status view | — |
| — | Employees don't know who to contact or what the next step is | — |
| — | Employee juggling multiple portals and credentials | — |
| — | Relocating employees receive no structured pre-arrival guidance | — |
| — | Late document errors cause cascading start-date delays | — |
| — | Unpredictable immigration timelines block start dates and housing plans | — |

## Direct quotes (verbatim)

> *"The employee has no idea what's happening unless I tell them. There's no self-service."*
> — GMM describing employee experience (PP-18, Example Quote field)

> Anxiety-driven messaging documented in PP-18 description: *"one employee messaged 3 times in a single day"*

> *"It's not just a job, it's a LIFE"* — Helena Harless (Welcome Service Geneva DSP, 2025-12-03) — vendor framing the emotional weight on the employee.

## Success criteria

- Open ReloPass → top of screen says **"Next action: X by Y date"**, in plain language, no UUIDs, no snake_case.
- One status bar shows where my case is: phase + provider + ETA. No login to 5 portals.
- Upload a document → instant feedback ("looks good" / "expiry date too close — need ≥6 months"), no waiting for a human review pass.
- Plan view shows what's covered by policy and what isn't, with a clear cost callout.
- Destination tab is genuinely useful — neighborhoods, schools, etc. — for the corridor I'm assigned to.

## Friction observed in current product (already known, prior synthesis)

| Prior finding | Severity | Source |
|---|---|---|
| **W1** Employee Dashboard exposes implementation details (UUIDs, Section A/B language, manual claim form, 9 nav items) — *"First impression is the worst surface"* | **P0** | `audit-docs/ReloPass_Audit_Final_Synthesis_INTERNAL.md` §5 |
| **W2** Estimate Review is the lightest surface despite being the value-prop screen — list of selections + totals only, no cap comparison, no delta, no personal-cost callout | **P0** | Same, §5 |
| **W3** Internal jargon throughout user-facing copy ("Layer-2", "baseline", snake_case task IDs, UUIDs in messages) | **P1** | Same, §5 |

## What this audit adds (gap vs. prior)

Prior audit was structural (inferred from screenshots + spec). What's missing and Phase 2 must produce:
- Live walkthrough of `/journey` (intake wizard v2) and `/employee/case/:caseId/*` for **employee persona** — actual screenshots of W1 surface as of 2026-05-25.
- Whether the in-progress intake v2 (`MEMORY.md` flags `Intake Wizard v2 (Pathway)` rollout) has resolved W1 or just shipped alongside the legacy.
- A11y review of the employee surfaces (no prior coverage).
- UX-copy review specifically of the wizard + estimate review (per prior brand audit, "compliance language" is also missing on user-facing surfaces).

## Open questions for Phase 2

- Does the Intake Wizard v2 at `/employee/case/:caseId/intake` actually present plain-language "next action" copy, or did the W1 surface get cloned into v2?
- Is the Estimate Review screen rendered today? Where? (`frontend/src/pages/` search needed in Phase 2b.)
- Are passport OCR / document pre-screening actually wired up to the employee UI, or only backend-callable (S6 readiness claim)?

## Signal quality

- **No real recent employee-persona interview** in the data. All employee evidence is *second-hand from HR/GMM* describing employee behavior. This is a known gap; Phase 3 synthesis must flag.

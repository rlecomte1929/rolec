# "Not a law firm" disclosure banner — design spec v0 (AIQ-681 / P1-06b)

> **Status: v0 design spec — pairs with the v0 disclaimer copy (P1-06a,
> `audit/legal_disclaimer_v0.md`).** Copy wording is pending external counsel
> redline (P1-06c); this spec covers placement, colour, dismissibility,
> persistence, and accessibility so engineering (P1-06d) can build against it.

## Goal

A single, recognisable disclosure pattern that tells users ReloPass gives
information, not legal advice — shown consistently across the five surfaces
where a user can act on AI-generated guidance.

## Component — reuse the design system

Build on the existing **`antigravity/Alert`** component with `variant="warning"`,
not a bespoke banner. It already carries the correct accessibility semantics:
`role="status"` + `aria-live="polite"` (WCAG SC 4.1.3 — announced without
interrupting). Add a dismissible variant (close button) where this spec calls
for it.

### Colour tokens (amber, design-system warning palette)

| Token | Value | Use |
|---|---|---|
| Background | `#f6f2e9` (antigravity warning bg) | banner fill |
| Border | `#e2d6bf` + 4px left accent | banner edge |
| Text | `#7a5e2a` | body + title |

**WCAG contrast:** text `#7a5e2a` on background `#f6f2e9` ≈ **5.4:1** — passes
**AA** for normal text (≥ 4.5:1). The muted tan-amber is intentional: calm and
on-brand (Stripe/Linear register), not an alarming red. Do **not** drop to a
lighter amber text that would fall below 4.5:1.

> Inline note: the roadmap-step filter banner shipped in AIQ-166 uses the brighter
> Tailwind `amber-50 / amber-800` (`#fffbeb` / `#92400e`, ≈ 8:1). That is a
> different, transient UI affordance. The legal disclosure should use the calmer
> design-system warning palette above for a consistent, recognisable "this is the
> legal notice" signal.

## The five surfaces

The banner appears on the same five touchpoints as the P1-06a copy. Placement,
persistence, and dismissibility differ by how much the user is about to rely on
the guidance.

| # | Surface | Placement | Persistence | Dismissible? |
|---|---|---|---|---|
| 1 | **Onboarding acknowledgment** | Modal/step body, above a required checkbox | Blocks progression until acknowledged | **No** — must tick to continue (one-time, logged) |
| 2 | **Roadmap overview** | Sticky banner at top of the roadmap view | Shown every visit | **Yes** — per session; reappears next visit |
| 3 | **Low-confidence step (inline)** | Inline, within the flagged step card | Shown whenever a LOW-confidence step is rendered | **No** — tied to the step, not dismissible |
| 4 | **Form pre-fill confirmation** | Inline, above the confirm CTA | Shown every pre-fill confirmation | **No** — must be visible at the moment of submit |
| 5 | **Human-Only step (inline)** | Inline, within the Human-Only step card | Shown whenever a Human-Only step is rendered | **No** — tied to the step |

### Persistence rules

- **Acknowledgment (surface 1)** is recorded once per user (timestamped — see
  P1-06c counsel note 2) and gates first display of any AI roadmap.
- **Roadmap banner (surface 2)** dismissal is **session-scoped** only. It must
  reappear on the next session so the disclosure is never permanently hidden.
- **Inline disclosures (surfaces 3–5)** are **not dismissible** — they are part of
  the step they annotate and disappear only when that step does.

## Accessibility checklist

- Contrast ≥ 4.5:1 (met: ≈ 5.4:1).
- `role="status"` + `aria-live="polite"` (inherited from `Alert`); the inline
  legal notices are not error states, so never `role="alert"`.
- Dismiss control (surface 2) is a real `<button>` with an accessible name
  ("Dismiss disclaimer"), keyboard-focusable, ≥ 24×24px target.
- Disclosure is never conveyed by colour alone — the text itself states "not legal
  advice", and an info/scale icon supplements the amber fill.
- Low-confidence CTA ("Consult an accredited immigration lawyer — [find one in
  Service Providers]") is a focusable link, not plain text.

## Out of scope (handoff)

- Final copy wording → P1-06c (external counsel redline).
- Component build + wiring into the 5 surfaces → P1-06d.
- Dedicated full "Terms & disclaimer" page linked from each banner → P1-06.

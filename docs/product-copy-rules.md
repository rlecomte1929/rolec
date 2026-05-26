# Product copy rules — ReloPass

> **Source of truth for this appendix.**  
> This file is the canonical source for the "Product copy" section of the `relopass-brand-voice`
> skill. Keep this file and `SKILL.md` in sync whenever rules are added or changed.
>
> Extracted from `audit/02-expert-ux-copy.md` (May 2026 expert audit).
> Tracked in AI Work Queue as **AUDIT-BRAND (AIQ-367)**.

---

## Why a separate appendix?

The brand voice doc (`relopass-brand-voice` skill) covers the **marketing register** —
tone, positioning, forbidden startup hype, and headline patterns. Product copy has an
additional failure class that the marketing register doesn't catch: **implementation
jargon** — backend vocabulary leaking into user-facing strings.

The rules below are enforceable on every in-product text string (UI labels, helper text,
error messages, empty states, button labels, status badges).

---

## Cross-cutting pattern rules

| Pattern | ❌ Forbidden | ✅ Required |
|---|---|---|
| **Backend status enum → UI text** | Raw codes: `GREEN`, `AMBER`, `RED`, `fulfilled`, `invite_revoked`, `pending` | Map through a single `statusLabel()` utility. Human-readable: "On track", "Needs attention", "At risk", "Quote received", "Invitation cancelled by HR", "Waiting on vendor" |
| **ID / UUID exposure** | "Assignment ID (UUID)", "Enter mobility_cases.id (UUID)", "UUID from HR", "Mobility case UUID" | "Case code from HR". HR-facing: "case code (the long string of letters and numbers separated by dashes)". Never expose table names or column types |
| **Field-level help text** | Placeholder-only, or inconsistent inline text | Consistent pattern: **label** above + **helper text** below the field + **error in place** below the field. Never put the only instruction inside a placeholder (placeholders disappear on focus) |
| **Action button labels** | Generic: "Continue", "Submit", "Next", "Save" | Outcome-described: "Save and continue", "Send for review", "Request quotes", "Confirm move date" |
| **Empty states** | "No X" / "No X match your criteria" | "No X yet. \[Reason or guidance\] → \[CTA\]". Example: "No cases match this filter. Try changing the risk level above, or [view all open cases]." |
| **Error messages** | "Unable to X" / "Error occurred" / single-line blame | Two-part: **what went wrong** + **what to do next**. Example: "Your email doesn't match what HR registered. Try the email on your offer letter, or ask HR to update it." |
| **Internal vocabulary in UI** | "Section A/B", "Layer-2", "snake_case", "draft_json", table or column names, framework terminology | Describe the concept in plain English. If a technical reference is needed for HR power users, put it in parentheses *after* the human label |

---

## Severity mapping for product copy violations

Apply the same severity tiers as the brand voice doc:

- **🔴 SITE-WIDE** — Status enums and UUIDs in the employee first-impression surface
  (W1: `EmployeeJourney` first load, `Auth`). Any authenticated employee may see these
  on their very first interaction with the product.
- **🟠 PAGE-LEVEL** — Error messages on claim/link flows; empty states on core HR views
  (`HrCommandCenter`, `HrDashboard`).
- **🟡 SENTENCE-LEVEL** — Field labels, helper text, secondary microcopy on internal
  admin or power-user surfaces.

---

## `statusLabel()` contract

Any raw status code rendered as text is a **🔴 violation** unless routed through a
`statusLabel()` utility co-located with the design system. The utility must cover at
minimum:

| Raw code | User-facing string |
|---|---|
| `invite_revoked` | "Invitation cancelled by HR — contact them to reissue" |
| `GREEN` | "On track" |
| `AMBER` | "Needs attention" |
| `RED` | "At risk" |
| `fulfilled` | "Quote received" |
| `pending` | "Waiting on vendor" |
| `draft` | "In progress" |
| `submitted` | "Submitted" |
| `approved` | "Approved" |
| `rejected` | "Not approved" |

Any code not in the map must render as `"Unknown status"` — **never** the raw code itself.

---

## Employee copy vs HR copy — voice consistency rules

The brand voice doc targets HR/mobility managers as the **buyer persona**. Product copy
must also serve **relocating employees** (first-time users, anxious, unfamiliar with
mobility ops). Both audiences share the same second-person register but have different
vocabulary tolerances.

| Surface | Audience | Rules |
|---|---|---|
| Employee-facing (W1 `EmployeeJourney`, `Dashboard`) | Relocating employee | Second-person "you/your". Sentence case. Zero internal vocabulary: no UUIDs, no status codes, no field names. Guidance-first error messages. |
| HR-facing (`HrDashboard`, `HrCommandCenter`) | HR professional | Second-person "you/your" for actions. Third-person for the employee ("the employee", "their case"). Mobility-industry terms acceptable ("assignment", "policy", "tier"). Database/code terms still forbidden. |
| Admin surfaces | Internal staff | More technical labels acceptable in parentheses, but human label must still come first. |

Never let the two registers bleed into each other:

- ❌ "Your relocation journey" on the HR dashboard (lifestyle language)
- ❌ "Enter mobility_cases.id" on the employee surface (table name)
- ✅ "The case" (neutral, understood by both personas)

---

## Known violations as of May 2026 audit

These were flagged as P0 in `audit/02-expert-ux-copy.md` and are tracked in the AI
Work Queue:

| File | Line(s) | Violation | Task |
|---|---|---|---|
| `frontend/src/pages/EmployeeJourney.tsx` | 217, 243 | "Assignment ID from HR (UUID)", "use the UUID from HR in the right field only" | AUDIT-A4 |
| `frontend/src/pages/EmployeeJourney.tsx` | 338 | "Unable to link this assignment." (no guidance) | AUDIT-A4 |
| `frontend/src/pages/EmployeeJourney.tsx` | 688, 733 | Raw `Claim state: {st}` — status code exposed | AUDIT-A4 / AUDIT-A5 |
| `frontend/src/pages/Dashboard.tsx` | 107–109 | `GREEN`/`AMBER`/`RED` badge text | AUDIT-A5 |
| `frontend/src/pages/HrCommandCenterCaseDetail.tsx` | 339–347 | `fulfilled` / `pending` quote status raw | AUDIT-A5 |

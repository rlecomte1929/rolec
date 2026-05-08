# Architecture Diagrams — ReloPass v1

These diagrams capture the v1 product design decisions for ReloPass.
They describe the user-facing moments where each architectural choice
becomes visible.

The diagrams are intentionally hand-drawn (Excalidraw). The goal is
decision capture, not visual polish. Re-draw only when a real design
decision changes.

## Index

| # | Diagram | Decision captured |
|---|---------|-------------------|
| 01 | [Benefit extraction](./01-benefit-extraction.png) | When the AI extracts a value, the HR human classifies it as one of: cap, fixed, conditional, service, or ambiguous. Ambiguous values route to a manual review queue. |
| 02 | [Policy classification](./02-policy-classification.png) | The AI proposes a category mapping per clause; HR confirms or corrects; unmappable clauses go to a backlog that drives schema improvement. |
| 03 | [Tier-snapshot binding](./03-tier-snapshot-binding.png) | One policy per company. Each benefit is configured per *tier composition* — a tuple of `employee_grade`, `family_status`, `assignment_type`, and `host_country_allowance_band`. Tier dimensions are configurable per company; not all compositions need configured values. Cases bind to the published policy snapshot at the employee's full tier composition. Blank cells return "not configured + escalation" rather than silent fallbacks. |
| 04 | [Assistant scope filtering](./04-assistant-scope-filtering.png) | Retrieval is permission-filtered before generation. The assistant cannot see facts above the employee's tier. Refusals are typed (out-of-tier / out-of-policy / ambiguous) and audit-logged. |

## Companion documents

- [`../decisions/2026-05-08-policy-data-model.md`](../decisions/2026-05-08-policy-data-model.md) — the schema decision derived from these diagrams.

## Status

v1 product diagrams. Override layer (per-employee exceptions) is intentionally deferred to v3.

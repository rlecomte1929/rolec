# Persona Input — HR Manager / Global Mobility Manager

**Sources:** Notion Pain Points DB (Affected Persona ∈ {HR Director, Global Mobility Manager}) + Customer Interviews DB (in-house buyer = Victoria @ NBIM, 2025-10-07) + prior synthesis §2 per-persona row + AI Work Queue HR-targeted items.

## Jobs to be done (JTBD)

1. **Get a real-time, single view of every active case across providers** (immigration, housing, shipping, etc.) without pinging each one.
2. **Apply company policy consistently** (caps, levels, exceptions) across cases and over time.
3. **Reconcile actual spend vs. policy budget** per case and across the program — surface overruns before invoicing surprises.
4. **Maintain audit-ready records** of who did what, when, against what policy version.
5. **Reduce time spent as human glue** between employee + 6–8 providers + HR business partners.

## Pain quantified (from Pain Points DB, citation = `PP-<id>` + URL)

| ID | Pain | Severity | Strategic Importance | Frequency |
|---|---|---|---|---|
| PP-1 | No real-time visibility into case status for HR teams | **Critical** | **Critical** | **Very High** |
| PP-13 | 15 Hours Per Week on Manual Provider Coordination | **Critical** | **Critical** | Low¹ |
| PP-18 | Employees Have No Self-Service Case Visibility (HR is bottleneck) | High | **Critical** | Low¹ |
| PP-20 | No Unified Cross-Provider Status Dashboard | High | High | Low¹ |
| — | Manual Policy Compliance Checking Against 40-Page Doc | — | — | — |
| — | Manual spreadsheet-based relocation tracking is embarrassing and error-prone | — | — | — |
| — | Provider communication fragmented across email with no audit trail | — | — | — |
| — | Right-to-work checks missed or completed too late | — | — | — |
| — | Manual compliance tracking leading to costly penalties | — | — | — |
| — | Immigration compliance tracked entirely by memory | — | — | — |
| — | Policy enforcement eroded by senior business pressure | — | — | — |
| — | No centralized tracking of relocation costs versus budget | — | — | — |
| — | Document collection from employees is chaotic and version-confused | — | — | — |
| — | Colleague cover creates context gaps and recovery burden | — | — | — |

¹ "Low frequency" in single-interviewee count, but Strategic Importance is Critical — the pain has high amplitude per occurrence, not high count of mentioners. PP-1 has Very High frequency, which is the cross-validating signal.

## Direct quotes (citable, verbatim)

> *"We spend 40% of our mobility team's time just chasing status updates. That's one full day per person, per week, gone."*
> — Sarah K., GlobalTech (PP-1, Example Quote field)

> *"My calendar is basically just chasing status updates."*
> — Marcus, GMM (PP-13)

> *"Right now I have to ping each provider individually to know if anything is stuck."*
> — Marcus, GMM (PP-20)

> *"Too many contacts and handovers, lack of single ownership"*
> — **Victoria @ NBIM** (2025-10-07, in-house buyer, Mom Test A, pain 5/5, **WTP 4/5**, identified as **highest-priority pipeline contact**)

## Success criteria (what "good" looks like to this persona)

- Open the platform on Monday morning → see every case + every provider task in one grid, color-coded by status, sorted by what's blocked.
- Define a policy once → it applies automatically at case creation, with exceptions flagged not hidden.
- Cost-to-date vs. budget visible per case, drillable to line items, exportable for finance.
- Every action (status change, document review, exception approval) has a who/when/policy-version stamp; CFO/audit can pull a clean trail.
- ≥30% reduction in HR-hours per case (target derived from prior audit T7: "30-40% in SME + mid-market routine").

## Friction observed (cross-persona, currently in the product)

Per prior synthesis §5 (already known):
- **W3 (P1)** — internal jargon ("Layer-2", "baseline", "Section A/B", snake_case task IDs) leaks into the HR-facing UI.
- **W4 (P1)** — Stakeholder model is thin (no full RACI / multi-approver chains).
- HR Command Center exists (`frontend/src/pages/HrCommandCenter.tsx`) but live-evidence depth deferred to Phase 2c.

## Open questions for Phase 2 to answer (live UI)

- Does the HR Command Center actually deliver the "single grid" PP-20 demands, or is it currently a list-of-lists?
- Is policy-vs-spend reconciliation present in any HR view today, or only conceptual (W2 Estimate Review = P0 "fix")?
- Does `hr_coordination.py` router surface provider status in a single endpoint or N round-trips?
- Is the audit log queryable from the HR UI, or backend-only?

## Notes on signal quality

- Only **one** real recent in-house HR buyer interview (Victoria @ NBIM, 2025-10-07) — 7+ months old as of audit date.
- Pain Points DB compensates with 14+ HR/GMM-tagged items and direct quotes, but the field "Frequency" sits at "Low" for several Critical-Severity items because the count of interviewees is small. **The right read is: high amplitude per pain, low statistical N — do not collapse to "low impact."**
- Phase 3 synthesis must flag: customer-discovery throughput is the binding constraint on confidence in this audit, just as the prior synthesis flagged in T15 §11.

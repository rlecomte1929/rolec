# Persona Input — Provider / Supplier (4th persona, lighter weight)

**Sources:** Helena Harless interview (2025-12-03, Welcome Service Geneva DSP — vendor perspective) + Pain Points DB cross-persona items + `backend/app/routers/provider_portal.py` + `providers.py` surface area + AI Work Queue P3-4 dossier builder + AIQ-4-D provider task portal UI + AIQ-14 provider status grid.

## Jobs to be done (vendor lens, looking inward into ReloPass)

1. **See my own tasks across all cases** — assigned to me, ranked by deadline, in one view.
2. **Update status / add notes / upload docs** without an email round-trip.
3. **Have a clear handoff contract** — what HR needs from me, what I need from the employee, what the deadline is.
4. **Get paid** — invoicing visibility (out of scope for the platform layer, but expected to flow).

## Direct quotes (verbatim)

> *"It's not just a job, it's a LIFE"*
> — Helena Harless, Welcome Service Geneva DSP (2025-12-03, Mom Test A, pain 5/5, **WTP 2/5** — vendor unwilling to pay; she's a relationship channel, not a direct buyer)

## Pain points relevant to vendor visibility

| Pain | Notes |
|---|---|
| Provider communication fragmented across email with no audit trail | Vendors don't trust the comms ledger because there isn't one |
| Limited visibility into immigration firm progress | Mirrors PP-20 ("ping each provider individually") |
| Immigration timelines now unpredictable and up to 18 months | Vendor-facing pain; pricing/SLA implication |
| No automated document validation before lawyer review | Lawyers receive incomplete dossiers |

## Success criteria (vendor lens)

- Single login → my tasks list, filterable by deadline / status / case.
- Status update is 1-click; comment is one keypress; doc upload is one drag-drop.
- HR-facing notes vs. employee-facing notes are separable.
- I can see the case context (employee, destination, deadline) without HR forwarding it.

## Friction observed in current product

| Finding | Evidence |
|---|---|
| Provider portal exists | `backend/app/routers/provider_portal.py` + `frontend/src/features/services/` |
| Provider task portal UI is "Ready for AI" or in progress | AIQ-4-D (May 2026) — `Build provider task portal UI — scoped to provider JWT` |
| Provider × Case status grid is the most-requested HR feature (PP-20), also vendor-relevant | AIQ-14-A (data model + API) + AIQ-14-B (UI) — flagged "shadcn/ui Table, no heavy grid lib" |
| Vendor-facing UX has no real interview signal beyond Helena (a relationship vendor, not a transactional one) | Single data point |

## Strategic positioning (from prior synthesis)

- ReloPass explicitly does NOT compete with vendors — it coordinates them.
- Phase-2 complement positioning (Topia) implies vendors are stakeholders, not adversaries.
- Helena's WTP=2 is correct posture for relationship vendors; transactional vendors (immigration lawyers, housing agents) may have different WTP — **not yet sampled.**

## Cross-persona overlap

- PP-20 (No Unified Cross-Provider Status Dashboard) is HR-facing **and** vendor-facing — solving it helps both.
- The "provider task" abstraction (provider_tasks table per AIQ-14-A notes) is the shared substrate.

## Open questions for Phase 2

- Is the provider portal UI **deployed today** or still in queue?
- If deployed, does it meet the "single login → my tasks" success criterion above?
- How does authn work for vendors? Provider JWTs per AIQ-4-D — are they secure and short-lived?
- Does the provider see HR-internal notes by accident? (RLS check.)

## Signal quality

- **One** vendor-side interview (Helena, DSP — relationship vendor).
- Zero transactional-vendor interviews (immigration counsel, housing, schools, shipping).
- Findings here are directionally correct but quantitatively under-sampled.
- Provider as a paying-buyer persona is **not** the target (per S6 Phase-1 strategy). Treat as stakeholder, not customer.

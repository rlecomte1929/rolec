# ReloPass — Andrea's Relocation Plan: Full Experience Audit & Delivery Plan

**Date:** 2026-08-22 · **Case:** Andrea (Venezuelan, Google Dublin, family of 4) — real case
`6ecadafe`, company "Google" `46fc3db0` · **Method:** live prod DB + API re-run + code + Notion.

---

## Verdict

Most of the machinery Andrea needs **exists and works** — the corridor roadmap overlay, the RFQ
system, the recommendation engine, the HR quote-comparison API, curated Irish vendors. But she
cannot experience any of it today, for two reasons that sit underneath everything:

1. **A live P0 regression.** `GET /api/public/corridor-requirements` and
   `GET /api/cases/{id}/requirements` return **500 for every corridor** (verified FR→NO, IN→DE,
   ES→IE). The requirements checklist — the spine of the whole plan — is down in production. Logged
   as a new P0 Notion task.
2. **Her case is hollow.** She never completed intake (`intake_step=0`, still the hardcoded
   family-of-4 "Singapore" seed profile), so every profile-driven feature has nothing to compute
   from: **0 services selected, 0 recommendations, 0 RFQs, 0 vendor shortlist, 0 vendors on
   profile** — and 16 *stale, generic* roadmap milestones generated before the CSEP fix shipped.

Fix those two and most of what you asked about lights up, because the features already run for
cases that have a profile (399 corridor milestones across 55 cases; 1,069 recommendation slates;
30 RFQs, 8 quoted).

---

## Feature-by-feature — what's present, what's missing

### 1. The roadmap (current vs future, immigration, timeframe)
**Present.** The CSEP corridor overlay (AIQ-1867 #1929 + #1938) is merged and generating real
journeys — **399 corridor milestones across 55 cases**, each with durations, prerequisites and a
`blocking` flag, so "do this now" vs "this comes later" and the timeframe are all modelled. The
immigration steps are correct for a third-country move: Critical Skills Permit → long-stay D visa →
IRP/Stamp 1 (Burgh Quay, 90 days) → PPSN → Revenue RPN.
**Gap for Andrea.** *Her* case still shows the 16 **generic** milestones (`task_visa_docs_prep`,
`task_visa_submit`…) — they were generated before #1938, so they're stale. Her roadmap needs to be
**regenerated** (or re-created by completing intake) to pick up the CSEP steps.
**Action:** regenerate Andrea's roadmap; add a "current focus" band to the plan view that surfaces
the non-blocked, next-actionable steps distinctly from future ones.

### 2. Immigration steps & deadlines
**Present.** Nationality-aware, honest, and now sourced: 29 approved Ireland requirements + the 9
VE→IE entry-visa/family facts, with the D-visa deadline and IRP 90-day window in the step graph.
The employee immigration view gives the correct third-country message ("your HR opens the file").
**Gap.** The corridor **immigration engine** (`immigration_requirements`/`immigration_milestones`)
is still empty (0 rows) — the milestones/timeline are served from the roadmap overlay, not that
engine, so "available forms" (PPSN REG, CSEP application, IRP booking) are still not modelled as
fillable forms. And the requirements 500 (P0) currently hides all of it.

### 3. Launch an RFQ to movers & get the best quote
**Present.** A full RFQ system exists: `POST /api/rfqs`, token-scoped supplier links
(`/api/supplier/rfq`, no account needed), `quotes`, `quote_lines`, and `rfqs.preferred_quote_id` /
`validated_quote_id`. It's exercised in prod — **30 RFQs, 8 with quotes back**.
**Gap.** For Andrea specifically: **0 RFQs** (no intake → no services → nothing to quote). And
system-wide, the *selection* half is barely used: **0 of 30 RFQs ever had a preferred quote set**,
only 1 was validated — a code comment even notes the supplier-link step "no UI ever did." The
"pick the best quote" loop needs finishing (see #6).

### 4. Are service providers appearing on her profile?
**Present.** Her employer's HR has curated **29 real Irish suppliers** (AIB, Bank of Ireland,
Revolut; Savills, Sherry FitzGerald; Fragomen IE, Matheson; PwC/KPMG/Deloitte IE; Nord Anglia;
Santa Fe/Crown Dublin) — the curation layer works.
**Gap.** **None appear on Andrea's profile**, because vendors surface through the recommendation
engine / service selection, and her case has no selected services and no profile. This is the same
root cause as everything else: hydrate the case and the curated vendors flow to her.

### 5. Advice on where to live + area recommendations by her requirements
**Present.** Housing & school recommendation endpoints exist; geocoding is wired (Geoapify,
AIQ-1607); Dublin neighbourhoods + schools were seeded (AIQ-1882, merged); the engine produces
1,069 recommendation slates for profiled cases.
**Gap.** Empty for Andrea (no address / commute / profile). And there is **no dedicated
"where should I live" area-advisor** that *ranks neighbourhoods* against her stated requirements
(commute to Grand Canal Dock, family of 4, budget) — today it returns housing *vendors*, not a
ranked area shortlist with rationale. Worth building as its own surface.

### 6. HR visibility of a quote summary + comparison table → approve the selected quote
**Present (as API).** `GET …/quotes?comparison=1` emits a compare event for 2+ quotes;
`comparison_readiness`/`comparison_available` exist; `assignment_policy_service_comparisons` holds
the policy min/standard/max vs the requested value with variance + `approval_required`; and
`rfqs.preferred_quote_id` / `validated_quote_id` / `validation_reason` model the HR sign-off.
**Gap — this is the biggest product gap for what you described.** The pieces exist but are not
assembled into the **HR-facing "summary + comparison table → approve"** experience: 0/30 RFQs have
a preferred quote set, so the loop isn't being completed. HR needs one screen that shows, per
service: the quotes side-by-side, the policy cap/variance, a recommended pick, and a one-click
"approve this quote" that writes `validated_quote_id` + reason.

### 7. Destination "settle-in" advice & basic services
**Present.** Ireland's settle-in pack shipped (AIQ-1746, merged #1913) and the false
"register your residence" line was removed — **16 published Ireland resources** (9 guides, 4
official links, 3 tips).
**Gap.** It's **thin and country-level, not Dublin-specific** (all 16 rows have `city_name=null`),
and the employee resource endpoint returned **0** in testing — a serving/profile gap on top of the
P0. The full breadth a relocator expects (cost of living with real Dublin rents, healthcare/GP
reality, banking catch-22, transport/Leap card, schools, community) is only partly there.

---

## Governance flag (needs your call)

The 9 VE→IE facts were not just loaded — they were **approved on 2026-08-21 12:02 UTC, including
the 4 rows flagged `needs_lawyer_review`** (Spanish-residence-≠-Irish-entry, CSEP immediate
reunification, spouse Stamp 1G, dependant Join-Family visa). Those legal claims are now live and
served without counsel — the opposite of the gate we set. Decide: roll them back to `pending`, or
accept them as representative for the demo with a visible "not legal advice" treatment.

---

## The plan — deliver Andrea's best experience while making HR's life easy

**Wave 0 — Unblock (today).**
- **Fix the P0 requirements 500** (new Notion task). Nothing else is testable until this is up.
- Decide the 4 `needs_lawyer_review` rows (roll back to pending, or accept-as-representative).

**Wave 1 — Hydrate Andrea's case (so everything computes).**
- Kill the family-of-4 "Singapore" seed; capture her real profile. Best HR-facilitation move:
  **HR document extraction** — HR uploads her contract/offer, an LLM proposes the fields, HR
  validates once, intake is pre-filled, no employee re-entry.
- **Regenerate her roadmap** so the CSEP steps + durations replace the 16 generic milestones.
- Outcome: recommendations, services, vendors and RFQs all become available on her profile.

**Wave 2 — Close the service loop you described (employee ↔ suppliers ↔ HR).**
- One-click **launch RFQ to the curated Dublin movers** from her service list.
- Build the **HR quote comparison + approval screen**: side-by-side quotes, policy cap/variance,
  a recommended pick, one-click approve → writes `validated_quote_id`. This is the missing half.

**Wave 3 — Advice depth (the "where do I live / what do I need to know" layer).**
- A **neighbourhood advisor**: geocode her Grand Canal Dock office, rank Dublin areas by commute +
  family + budget, with rationale — not just a vendor list.
- Deepen the **Dublin-specific settle-in content**: real rents, healthcare/GP reality, the bank
  proof-of-address catch-22, Leap card, schools, community.

**Wave 4 — Polish & completeness.**
- Model the fillable Irish forms (PPSN REG, CSEP application, IRP booking) as documents.
- The relocation-agent seat (AIQ-1884) so an external agent can work her case and hand back to HR.

**The through-line for HR:** upload once → validate the AI's extraction → curate vendors (done) →
review the roadmap and the quote comparison → approve. Every employee-facing feature has an HR
review/approval surface, which is exactly the "facilitate HR" posture ReloPass is selling.

---

## Evidence appendix
- **P0:** `/api/public/corridor-requirements` 500 for FR→NO, IN→DE, ES→IE (request_id
  462dd172-…); `/api/cases/{id}/requirements` 500. Deploy `65659473`.
- **Andrea `6ecadafe`:** 16 generic milestones; 0 services/recs/RFQs/shortlist/vendors; seed profile.
- **Platform works with a profile:** 399 corridor milestones / 55 cases; 1,069 rec slates; 30 RFQs
  (8 quoted, 0 preferred, 1 validated).
- **IE requirement_items:** 65 (29 approved incl. the 9 VE→IE; 36 pending). **country_resources IE:**
  16 published (country-level).

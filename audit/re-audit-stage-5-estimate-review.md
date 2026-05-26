# Re-audit — Stage 5 (Estimate Review redesign / W2)

**Lens:** Designer (live) + UX copy on the value-prop surface.
**Method:** Direct read of `frontend/src/pages/services/ServicesEstimate.tsx` (page wrapper, 122 LOC post-Stage-5) + `frontend/src/features/recommendations/PackageSummary.tsx` (the engine room, 619 LOC). Compare against Side-Output A spec (color-signaling per FX with date stamping, per-service breakdown with multiplier transparency, exception flow integration, personal-cost callout).

**Baselines (Phase 2):**
- `ServicesEstimate.tsx` scored **4 / 10** in `02-expert-design-live.md`
- W2 was a P0 weakness in the April 2026 synthesis (`audit-docs/ReloPass_Audit_Final_Synthesis_INTERNAL.md` §5)

**After Stage 5:**
- ServicesEstimate page: **8.5 / 10** (+4.5 vs the audit's named baseline)

The big jump is because **Side-Output A is already substantially implemented** in `PackageSummary.tsx` — the audit's "still bare" was outdated by the time Stage 5 ran. Stage 5's own contribution is the page-wrapper copy patch.

---

## What's actually on `main` (the W2 redesign)

`PackageSummary.tsx` (619 LOC) is the Side-Output A implementation. It renders:

| Spec item | Implementation | Lines |
|---|---|---|
| Per-service breakdown | "Selected services" card with item name + category + estimated cost | 388-411 |
| Per-service cap comparison | `comparison[]` array with `total / cap / covered / extra / status` per item | 159-204 |
| Status badge per service | "Within cap" (green) / "Over cap" (orange) / "Not capped" (gray) | 278-291, 449-460 |
| Visual cap bar | Stacked green (Covered) + orange (Extra) bar per service | 482-506 |
| Personal-cost callout | Orange "You pay: $X" line under each over-cap item | 514-516 |
| Totals row | Total package cost / Company covered (green) / Your out-of-pocket (orange) | 588-602 |
| Exception flow — request | "Request exception" button for employees on over-cap items + modal | 530-548, 568-586 |
| Exception flow — status | Badge per category for existing exception requests (pending/approved/rejected) | 518-528 |
| Existing exceptions display | Top card listing all employee exceptions + HR notes | 324-377 |
| Currency conversion | `convertUsdToDisplay()` + employee-chosen `displayCurrency` | 297, 19-23 |
| Multi-role view | "HR view — same numbers the employee sees" badge for HR/Admin | 424-428 |
| Loading state | `role="status"` + `aria-live="polite"` + spinner | 301-311 |
| Empty state | "No items in your package yet" → "Edit selections" CTA | 379-387 |
| Help copy when caps missing | Yellow alert explaining why some categories show as out-of-pocket | 439-444 |

This is a serious, comprehensive value-prop surface — exactly what Side-Output A asked for. The Phase-2 audit (predating these changes) was correct *at the time* and the work since then has closed the gap.

---

## Stage 5 own contribution — page-wrapper copy patch

The wrapper `ServicesEstimate.tsx` (122 LOC) still contained two pieces of generic copy that the Stage-2 re-audit (`audit/re-audit-stage-2-copy.md` COPY-5) had explicitly called out as in-scope for Stage 5:

| Before (W2 wrapper) | After (Stage 5 patch) | Source rule |
|---|---|---|
| `Next steps: 1) Select vendors  2) Request quotations  3) Receive offers  4) Decide` | "What happens next" heading + outcome-described prose: *"Pick the vendors you want quotes from — we'll send the request in one click. Offers come back here as vendors respond, then you compare and decide."* | docs/product-copy-rules.md "Action button labels: outcome-described, not generic" |
| Empty state: "Pick the services you need, answer a few preferences, then choose providers from the recommendations to build your shortlist. Your selections save automatically and you can come back here any time to see the cost overview vs your HR policy caps." | Tighter empty-state guidance with explicit reason + concrete CTA: *"You haven't picked any services yet. Choose what you need, set a few preferences, and we'll build a side-by-side view of what your company's policy covers and what comes out of pocket."* + CTAs "Start picking services" / "See recommendations" | docs/product-copy-rules.md "Empty states: No X yet. [Reason] → [CTA]" |

Subtitle also tightened: `Shortlist vs HR policy caps.` → `Your services vs your company's policy.` (drops "shortlist" jargon).

---

## Findings status

### W2 (P0) — Estimate Review is the lightest surface despite being the value-prop screen
**Substantially closed on main.** The PackageSummary redesign matches the Side-Output A spec across all 13 items checked. Page-wrapper copy now matches the BRAND product-copy rules.

### COPY-5 (P1 from Stage 2) — "Next steps" generic numbered list
**Closed by Stage 5.** Rewritten to outcome-described prose.

### Empty-state pass (P1) on ServicesEstimate
**Closed by Stage 5** for this specific surface (was on the broader Stage-6 empty-state pass list).

### Remaining Side-Output A gaps

| Gap | Status | Notes |
|---|---|---|
| ECB FX date stamping | ❌ Not implemented | `servicesCurrency.ts` (77 LOC) does conversion but doesn't surface a rate-date stamp. Requires backend `/api/fx/ecb` endpoint + UI display. Out of Stage 5 scope. |
| Multiplier transparency | ⚠ Partial | Caps show numeric value (e.g. "Cap: $X") but don't display *which* policy tier multiplier produced the number (e.g. "VP × Premium × Singapore"). Available on the HrPolicy page but not inline here. |

Both gaps are P2 polish — the screen meets its value-prop role without them.

---

## Scoring rationale

| Sub-dimension | Δ vs Phase-2 baseline of 4/10 |
|---|---|
| Per-service cap comparison with visual bar (the core of Side-Output A) | +1.5 |
| Personal-cost callout ("You pay: $X" in orange) at item + total level | +1.0 |
| Exception flow integration (request + status + HR notes) | +1.0 |
| Currency conversion + multi-currency support | +0.5 |
| Stage 5 page-wrapper copy patch (outcome-described "Next steps" + empty state) | +0.3 |
| Help copy when policy caps are missing or partial | +0.2 |
| **Net** | **+4.5 → 8.5 / 10** |

Score moves to 9.5+ once ECB FX date stamping + multiplier transparency land.

---

## Design (live) lens — composite update for the screen

The page-level Design-live lens is broader than just ServicesEstimate. Stage 5's contribution is one major surface moving from 4 → 8.5, which contributes about +0.5 to the system-wide Design-live score.

| Lens | Pre-S5 | Post-S5 |
|---|---|---|
| Design (live) | 6.8 (post-S2) | **7.3** |

---

## Files touched in Stage 5

```
audit/re-audit-stage-5-estimate-review.md     (this file)
audit/STAGES.md                                (Stage 5 row + scoreboard)
frontend/src/pages/services/ServicesEstimate.tsx (2 copy patches — "Next steps" + empty state)
```

Source-code touch: 1 file, ~14 LOC net change. All TS clean.

---

## What Stage 5 explicitly did NOT do

- Touch `PackageSummary.tsx` — the audit's W2 redesign target was already implemented there (~619 LOC of cap comparison + exception flow + currency conversion). Verified, not re-built.
- Add ECB FX date stamping — requires backend work.
- Add multiplier transparency — requires plumbing policy tier metadata through the comparison object.
- Run `/design-shotgun` — generating design variants for an already-shipped value-prop screen would have produced waste. Skipped consciously.
- Run `/plan-ceo-review` against the spec — the strategic anchor framing (W2 = the value-prop) is already locked.

## Recommended next design actions

1. **AUDIT-W2-followup-fx** (P2): ECB FX endpoint + UI date stamp. ~1 day.
2. **AUDIT-W2-followup-multiplier** (P2): show "Cap derived from: {tier} × {package} × {corridor}" inline. ~half-day.
3. Continue to Stage 6 (design-system enforcement — antigravity migration + empty-state pass) which will keep moving the Design-live lens up.

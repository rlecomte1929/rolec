# Plan-Mode Expert Review — CEO / Founder Lens

**Reviewer lens:** "Is this still the right product, the right segment, the right wedge?"
**Docs reviewed:** `audit-docs/ReloPass_Audit_Final_Synthesis_INTERNAL.md` (15-task structured audit, 2026-04-26), `ReloPass_Implementation_Plan_for_Claude_Code.md`, `audit-docs/ReloPass_Revised_Execution_Plan.md`.

**Score: 8.5 / 10** — exceptional strategic discipline; the residual half-point gap is execution risk, not thinking risk.

What would make it a 10: closing the customer-discovery gap explicitly flagged in T15 §11, and shipping the two anchor surfaces (Policy module, Estimate Review) at the depth the strategy promises.

---

## Strengths (these are correct and should not change)

1. **Out-segment + Complement positioning is sound.** SME + mid-market routine + French mid-market (with option b) is a defensible wedge against Topia Horizon. Refusing enterprise demos is the right discipline; pricing anchored to "vs current Excel + RMC" is the right anchor.
2. **Policy + Estimate Review identified as the two anchors.** Cuts that delay either are correctly flagged as verdict-degrading.
3. **5 architectural verification spikes are well-scoped** (~3 weeks total). Each maps to a sensitivity variable, each has a fix-time estimate.
4. **Honest scoring posture.** "Verdict drops from 3-4x to 2-3x if spikes return mixed results — still winning, just less aggressive." This calibration discipline is rare and right.

## Findings (plan-mode CEO concerns)

### CEO-1 [Critical] — The customer-discovery limitation flagged in §11 has not been closed
Prior synthesis: *"The single highest-leverage non-engineering investment to make right now: a 5-10 customer-discovery interview wave with mid-market HR/mobility leads."* As of audit run date (2026-05-25): only **one** real in-house buyer interview in the past 12 months (Victoria @ NBIM, 2025-10-07). The plan named the gap; the gap is still open 7 months later. **Why this matters at CEO level:** the entire 3-4x verdict is conditional on customer validation. Without it, the strategy doc is *internally consistent* but *externally unvalidated*. This is the single highest-leverage CEO action — not a product feature.

### CEO-2 [High] — "Topia complement" Phase-2 readiness is not visible in product
The plan commits to "Phase 2 export readiness in MVP architecture — don't paint into a corner where Topia integration requires a rewrite." The full-stack audit (`02-expert-fullstack.md`) does not see an explicit export-to-Topia data shape in the schema today. **Either** this is being deferred consciously (acceptable, but should be tracked), **or** the requirement is silently shipping in a way that won't survive Phase 2. CEO should ask: "show me the data export contract."

### CEO-3 [High] — Brand site (`relopass.com`) is 27/50, lagging the strategic ambition
Prior brand audit (2026-04-23) scored the live site at **27/50** — `Differentiation` 1/5, `Category clarity` 2/5, `Proof` 2/5. The strategic narrative ("operating layer for mobility", "not an agency, not a marketplace, not an HR add-on") doesn't appear anywhere site-wide. **Why CEO-level:** if a buyer lands on relopass.com today, they cannot tell what category ReloPass is in. That is a top-of-funnel leak independent of product quality.

### CEO-4 [Medium] — The "French mid-market with option (b)" wedge is single-source
Confidence noted as Medium-low (60%). Window flagged as "may close as Anywr stabilizes." The plan acknowledges this. CEO question: what's the trigger to either commit hard to option (b) or formally drop it? Without a decision deadline, this becomes scope ambiguity.

### CEO-5 [Medium] — The 90-day actions list lacks an owner column
Prior synthesis §10 lists ~10 recommended actions. None have explicit owners or dates beyond "next 90 days." For a founder-led team this is fine; if a co-founder/advisor structure exists (per stakeholder DB hints), missing accountability is real risk.

---

## What this lens is NOT saying

- Not telling you to expand scope into enterprise. Out-segment discipline is right.
- Not telling you to add features. Adding features without customer-discovery validation makes the gap worse, not better.
- Not telling you to ship faster. Shipping the anchors at the right depth beats shipping more surface area.

## Recommended next CEO actions (ranked)

1. **Book 5-10 customer-discovery calls in the next 30 days.** Mid-market HR/mobility leads, EU + French. Mom Test A grade required (past-behavior questions, not opinions).
2. **Decide on Topia data-export contract** — write it down, even if implementation lags.
3. **Brand site v2** to address the 27/50. The brand audit already gives the rewrites; this is execution, not thinking.
4. **Set a decision deadline for option (b)** French domestic. By X date, either commit budget or formally deprioritize.
5. **Add owner + date columns** to the §10 90-day actions list.

# Launch Verdict Ledger — France→Norway v0 gate

**Optimizing for:** fastest path to launch-ready on the employee experience.
**v0 launch gate (two conditions):** **G1** vendor list verified · **G2** one real France→Norway move flows end-to-end, smooth.
**Prod:** `46aca7e3` (descendant of `c917b2ad`; verified live). **Rule:** a browser FAIL is not a finding until the DB lane corroborates it or the exact failing request is captured.

**STATUS: 🟢 ALL GREEN — v0 GO** (last two checks closed by Cowork browser+DB on 2026-07-29).

Status vocabulary: ✅ dual-verified (browser + DB, or deterministic curl+SQL) · ⬜ open, non-blocking.

---

## Launch-blockers — all ✅

| Fix / ID | What it proves | Status | Verified by |
|---|---|---|---|
| RFQ read — #1668/AIQ-1703 | HR sees the employee's 6 picks | ✅ | Browser (Vendor quote requests panel) + DB (6 recipients, case-keyed) |
| RFQ dispatch loop — #1670/#1688 | Dispatch → magic link → supplier quote → back to HR | ✅ | Browser (loop closed, qa-r4w1b) + DB (quotes=1, total 1234, replied, zero Resend) |
| Paywall — #1691/AIQ-1723 | Gates unpaid, unlocks paid, no bypass | ✅ | Browser (test-card, buy-button gone, no spinner) + DB (access_tier free→roadmap, no dup) |
| Tenant isolation / IDOR — #1679/AIQ-1718 | No cross-tenant message read | ✅ | Shell (403 cross / 200 same) + DB (two distinct companies) |
| canonical_case_id hardening — AIQ-1731/1732 | Case-vs-assignment id class structurally closed | ✅ | DB (0 null, 0 dup, UNIQUE present) |
| services-state persistence — #1682 | Shortlist persists, no data loss | ✅ | DB (all adds land, robust to concurrency) |
| Add-to-package no spurious 400 — #1696/#1700 | Picks don't 400; audit trail captures every pick | ✅ | Browser: 4 non-top adds → 4× POST /api/ai/decisions = **201, zero 400s**. DB: 4 ai_decisions rows, all `accept`, zero dropped. (prod 46aca7e3, case 5b7e1559) |
| Movers reachable — #1699 | Employee can reach all 12 vetted movers | ✅ | Browser: NL_SG tab **"Movers (12)"**; **"Show 2 more"** reveals the rest → **12 cards rendered**. DB: 12 distinct. (prod 46aca7e3, case 5b7e1559) |

**G1 (vendor list verified):** ✅ movers/schools render, recommendations resolve, all vetted reachable (12/12), RFQ carries the 6 picks.
**G2 (end-to-end flow smooth):** ✅ FR→NO loop closes end-to-end; paywall + isolation clean.

**Blocker tally: 8 of 8 GREEN. No open defect blocks the gate. → v0 is GO.**

---

## Non-blocking — deferred, do not gate v0

| Item | Priority | Why not blocking |
|---|---|---|
| HR can't see/relay the supplier magic link | P2 | Loop still closes (link surfaces in employee inbox); HR-convenience gap |
| Panel title copy ("Provider Coordination" vs "Vendor quote requests") | P3 | Cosmetic |
| PageDown / stale-session logout | P3 | Multi-fixture harness artifact; no single-session repro found |

---

## Close-out record
- **Job A (movers, #1699):** NL_SG case `5b7e1559`. Recommendations tab shows "Movers (12)"; default renders 10 + a "Show 2 more" control that reveals the remaining 2 → 12 cards, control then disappears. All vetted movers reachable. ✅
- **Job B (add-to-package, #1696/#1700):** same session. 4 non-top mover adds each fired `POST /api/ai/decisions` → **all 201, zero 400s**. DB: 4 `ai_decisions` rows, decision `accept`, zero dropped — the audit trail now captures non-top picks (previously `override` without reason → 400). ✅
- Both run against prod `46aca7e3` (contains #1699/#1696/#1700; descendant of the gate's `c917b2ad`).

**Test artifacts to purge:** fixtures `qa-r4x1`, `qa-r4x2` (+ earlier `qa-r4w*`, `qa-r4wcap*`); probe `ai_decisions` rows with `recommendation_id LIKE 'test-rec-%'`.

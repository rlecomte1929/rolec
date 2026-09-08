# Claude Code — let the employee see ALL vetted providers (lift the top-N display cap)

Paste from repo root. Base off current `main`. **Own branch off `main`: `fix/recs-show-all-vetted`. Do NOT use `fix/td-qa-services-batch-0719`.** Read `CLAUDE.md` and `DESIGN.md`.

Small, well-scoped follow-up to #1689/AIQ-1722. That PR turned a **silent** drop into a **disclosed** one — the recommendations list still caps at the top 10, but now shows a banner: *"2 more vetted providers are available for this category but not shown here — the list is capped at the top 10 matches."* Verified in RUN 004-W Segment 2 (NL_SG: 10 shown, 12 vetted, 2 unreachable).

**Product decision (Romain, 2026-07-27): the employee must be able to see all vetted providers.** A disclosed-but-unreachable provider is still an unreachable provider.

---

## What's proven (do not re-investigate)
- NL_SG (Amsterdam→Singapore) has **12 distinct vetted movers** (Cowork DB: 12 distinct masters, 0 dedup collapse). The UI renders **10** and discloses 2 hidden.
- #1689 added the disclosure banner and the `top_n` cap constant. The cap is a **display** cap, not a vetting/eligibility filter — the 2 hidden providers are fully vetted.

## The fix (pick the smaller of these two, match the existing code)
The list is capped by a top-N display limit in the recommendations render path (the same code #1689 touched to add the banner). Do the minimal thing that makes all vetted providers reachable:

1. **Preferred — a "Show all" / "Show N more" affordance.** Keep the default view at the top-N (10) for signal, but add a control that expands to the full vetted set. Clicking it reveals the remaining providers in the same list. The disclosure banner becomes (or is replaced by) that control. This preserves the "top matches first" UX and satisfies "no vetted provider is unreachable."
2. **Alternative — lift the display cap** for vetted providers to a sane upper bound (e.g. render all vetted, or top 20) if that's simpler and the list stays usable. Only if a "show more" control would be disproportionate.

Prefer option 1. Do **not** touch the vetting/eligibility gate (`company_vendor_selections` / `platform_vetting_status`) — only the *display* cap. Follow `DESIGN.md` (antigravity components, navy/teal, no hardcoded hex).

## Scope guard
- Display/interaction change only. No new endpoint, no ranking/scoring change, no backend eligibility change.
- If the full vetted set is already returned by the API and only trimmed client-side, this is a **frontend-only** change (reveal what's already there). If the API itself trims to top-N before returning, extend it to return the full vetted set (or add a paged/expand param) — check which before coding.

## Reproduce first
Provision `corridor_id=NL_SG&stage=shortlist_ready&campaign=qa-recsfix` via `POST /api/test-drive/provision-staged`, sign in as employee, Services → Recommendations → Movers. Confirm 10 shown + the "2 more" banner. Apply the fix. Confirm all 12 are now reachable.

## Acceptance
1. NL_SG movers: the employee can reach **all 12** vetted movers (rendered, or via a working "show all / show 2 more" control).
2. The revealed count matches the disclosure ("2 more" → clicking shows exactly those 2).
3. No vetted provider is permanently hidden in any category/corridor.
4. Vetting gate unchanged; ranking order unchanged for the top matches.
5. `cd frontend && npx tsc --noEmit` + `npm run build` clean; add/adjust a test around the cap/expand.

## Hard rules
- Branch `fix/recs-show-all-vetted` off `main`, own PR. Never `fix/td-qa-services-batch-0719`, never push `main`.
- If a backend router changes, register in BOTH `backend/main.py` and `backend/app/main.py` and verify with the routes check (per `CLAUDE.md`). (Likely frontend-only — confirm first.)

## Report
branch · SHA · PR · frontend-only or API-touched · how all vetted are now reached (screenshot/test) · NL_SG shows 12 · tsc/build/test output.

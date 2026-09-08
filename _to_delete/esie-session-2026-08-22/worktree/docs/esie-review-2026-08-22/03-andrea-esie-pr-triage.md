# Andrea (ES→IE) go-live — PR triage, 2026-08-22

*Triage of the "5 already-built PRs" from `ReloPass_ES-IE_Andrea_GoLive_Assessment_2026-08-20.md`, reconciled against the current state of `main`.*

---

## Headline

**The merge bottleneck is already cleared.** All five Wave-1 PRs merged into `main` on 20–21 Aug — within ~24 hours of that assessment being written. On top of that, both Wave-2 "build/load" items (the roadmap, AIQ-1867; the VE→IE entry-visa load, AIQ-2027) are also merged. So the assessment's entire three-part code plan — *merge 5, build 1, load 1* — is **done in code**.

What's left for Andrea is **not merge work**. It's a small set of human-gated / data items, plus a fresh live check to confirm the ~15 merged PRs actually moved her off the AMBER 52% score.

**Recommended next action:** stop treating this as a merge queue. Run the three non-code items below and re-score, rather than re-reviewing PRs that are already in.

## The 5 Wave-1 PRs — all MERGED (no action)

| # | Ticket | What it unlocks for Andrea | PR | Status in `main` |
|---|---|---|---|---|
| 1 | AIQ-1879 | `relocationBasics` stops 500ing (corridor write) | #1925 | ✅ merged 08-21 07:22 (`51d38648`) |
| 2 | AIQ-1746 | Dublin settle-in pack; false "register your residence" line removed | #1913 | ✅ merged 08-20 20:59 (`16026cb7`) |
| 3 | AIQ-1882 | Dublin neighbourhoods + geocoding (housing/schools/commute) | #1915 | ✅ merged 08-20 20:48 (`6467b613`) |
| 4 | AIQ-1868 | HR "no verified IE readiness template" flag cleared | #1920 | ✅ merged 08-20 21:10 (`06345963`) |
| 5 | AIQ-1872 + AIQ-1883 | Ireland-capable advisors; Dublin movers — no Singapore / `example.com` | #1927 | ✅ merged 08-21 07:22 (`32d5abc3`) |

Verdict: **nothing to merge.** These are in `main` and (via Render's auto-deploy of `main`) should be live.

## Wave-2 "still unbuilt" items — now also merged

| Ticket | Assessment status (08-20) | Current state in `main` |
|---|---|---|
| **AIQ-1867** — wire the CSEP journey into Andrea's roadmap | "genuinely unbuilt" | ✅ built & merged: #1929 (`0f5752a1`), #1938 (`317ffaf0`), #1940 (`b6dd1bb6`), and #1952 (`f9112c13`, "the corridor journey reaches the screen the employee actually opens"), plus #1958 (CSEP "easy-to-miss" traps) |
| **AIQ-2027** — load VE→IE entry-visa + family facts | "research delivered; load pending" | ✅ landed as candidates + promotion recorded: #1934 (stage candidates), #1945 (evidence landing), #1942 (record promotion), #1946 (review-page 500 fix), #1948 (endpoint publishes citation URLs only) |

Caveat on AIQ-2027: the assessment flagged **4 of the 9 VE→IE rows for counsel** before approval. The facts are landed as *candidates*; whether counsel has cleared those 4 and they've been promoted to served is a review/attestation gate I can't see from git — confirm it before relying on the VE→IE immigration content.

## What actually remains for Andrea's go-live

None of these is a PR merge; three of the four are human-gated or per-case data, which is why they don't show up as "unmerged code."

1. **Approve the 6 pending Ireland `requirement_items`** (emergency-tax trap, 183-day residency, PRSI, split-year, RPN). Admin `review_status` flip — explicitly a **human gate, do not auto-approve**. This switches on the six highest-value "non-obvious" items that are currently invisible. *(DB/admin action — not visible in git.)*
2. **Fix Andrea's own case (`6ecadafe`)**: `intake_step=0` and a hardcoded family-of-4 "budgetMonthlySGD" seed profile. She needs intake completed (or pre-filled) and the Singapore/Oslo seed cleared, or she logs into a wrong, empty profile. *(Per-case data — not code.)*
3. **Confirm the VE→IE candidates are promoted + counsel-cleared** (the 4 flagged rows above). Until then her Venezuelan entry-visa/family branch may still be thin.
4. **Re-run the live Madrid→Dublin E2E and re-score.** The last result on disk is `t18_results_1787290309969.json` (08-21), which predates or coincides with the final merges. A fresh `scripts/madrid_dublin_runner.mjs` run against `api.relopass.com` is the only way to confirm the merged PRs moved her past **AMBER 52%** and that PLAN/forms/milestones/recommendations/geocode/advisors now pass live.

Non-blocking (per the assessment, and confirmed as design gaps, not Andrea-blockers): uncurated companies still get wrong defaults (a Munich school for a Dublin move), and the raw marketplace endpoint isn't corridor-filtered. Andrea's company "Google" is curated (29 Irish suppliers), so these don't block her.

## Method & limitations (so you can trust or re-check this)

- **Authoritative:** every "merged" claim is `git log origin/main --grep "(#PR)"` against your current `main` (HEAD `850d344b`, 2026-08-22 09:16). Merge timestamps are `git show -s`.
- **Can't confirm from here:** live CI status and the set of *genuinely open* PRs — this VM has no `gh` CLI and the remote is a local `no-mistakes` mirror. `git branch --no-merged` is unreliable because your squash-merge flow leaves already-merged branches looking unmerged, so I did **not** infer "open PRs" from it.
- **Assumed, not verified:** merged → deployed (Render auto-deploys `main`). I did not hit `api.relopass.com` or the prod DB — that's items 1–4 above and needs your go-ahead.

## What I can do next (read-only unless you say otherwise)

- Run the live Madrid→Dublin E2E (`scripts/madrid_dublin_runner.mjs`) and give you the fresh score + the exact remaining live failures — this replaces guesswork with the current number.
- Or check the prod DB read-only for items 1 and 3 (are the 6 IE requirement_items still `pending`? are the VE→IE candidates promoted?) — a read against Supabase, on your go-ahead.

---

*Read-only triage. No PRs merged, no code changed, no production writes. Companion to `corridor-facts-audit-2026-08-22.md` and `corridor-facts-forward-plan-2026-08-22.md`.*

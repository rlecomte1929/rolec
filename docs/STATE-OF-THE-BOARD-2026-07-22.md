# ReloPass — State of the Board

**As of 2026-07-22 · `main @ 646bd682` · Supabase `nsvefcvpvwwwhuqyuqmp`**
Source of truth for any agent picking up work. Verified by Cowork against repo + prod DB.

---

## 1. Launch readiness — one-line verdict

The **employee journey is proven end to end** (provision → intake → roadmap → shortlist → RFQ submit → survey), all data correctly attributed. The **vendor loop closes on the HR side and it doesn't connect** — that's the one real feature gap, now scoped and decomposed. Three small honesty/hygiene fixes are ready. **You can launch on the employee experience once the RFQ confirmation copy is made honest.**

---

## 2. ✅ Shipped & verified in production

| Area | Evidence |
|---|---|
| Survey campaign attribution (no-session → NULL, not cohort) | `bf725c34`; verified 2 rows land NULL |
| Provisioning default (plain link → `unattributed`, not insead-2026) | `3dde2f7b`; verified 3 `unattributed` sessions, cohort clean |
| Session survives navigation | `b8cb5562` |
| Country autocomplete corruption | `466b1ab3` |
| Policy publish hang + 409 | `14b02998` + `d4470263` |
| Policy tabs contradiction | `378fe551` |
| Survey validation naming | `ebee2aa1` |
| `/cases/{id}/vendors` 500 (dropped `vendors` join) | `9d3fab9b` + `ebf7b731` |
| "HR owner" chip showed employee | `ff4ea8dd` |
| Services destination gate (unblocked RFQ) | `d034299b` |
| Outbox recipient allowlist | `659a33dd` (merged — cron stays disabled) |
| Vendor seeding (loud-failure) | `d7be1663` + `2031a050` |
| Staged-provisioning fixture (`provision-staged`, dual-registered, qa-gated) | `83105ed2` |
| **First RFQ ever submitted** → landed in `rfqs`(1)/`rfq_items`(2)/`rfq_recipients`(6), **0** in `rfq_requests` | Cowork DB verify |
| Supplier magic-link security (M1/M2/M3: PII, cross-tenant, expiry) | code audit — all PASS |
| AIQ-1652 Neighbourhood/Living-Areas core + Phase A | PRs #1597–#1618; migrations live in prod |
| PRIV-004 geocoding sub-processor gate (Geoapify, disabled-until-keyed) | AIQ-1661, memo-confirmed |

---

## 3. 🔧 Ready for Claude Code (small, filed, own branches)

| # | Task | Priority | Notion |
|---|---|---|---|
| A | Merge staged-fixture currency fix (PR #1620 exists) | P3 | AIQ-1661 |
| B | RFQ confirmation copy — stop falsely claiming HR visibility | **P1 / trivial** | filed |
| C | CI collection landmine (`test_budget_summary_honest.py`) before AIQ-1527 merges | P2 | filed |
| D | Taxonomy cleanup — 2 mislabelled `living_areas` suppliers | P3 | filed |
| E | Abandon `feat/housing-neighborhood-p01` (415-commit-stale, fully superseded) | — | this doc |

**B is the launch gate.** It's trivial and needs no product decision — the confirmation currently tells testers "your HR team can see the providers you picked," which is provably false.

---

## 4. 🔴 Your decision, not an agent's

| Item | State |
|---|---|
| **RFQ loop rewire** — employee writes `rfqs`, but no HR surface reads it & no supplier token minted | P1, Red, Needs Decomposition (3 sub-tasks: HR read of `rfqs` · token+dispatch · copy gating). Launch on the employee experience now, or hold for the HR loop. |
| **Stripe / paywall** — `feat/stripe-payment-checkout` worktree live, `feat/stripe-payments` on origin | Red — money+secrets, needs your hands on keys. Spec ready at `docs/stripe-portable-webhook-spec.md`. Nothing on `main`. |

---

## 5. ⏸ Blocked / parked (correctly)

- **Audos Q2/Q3** (supplier submits quote / quote returns to HR) — blocked on the loop rewire (§4), **not tooling**. A supplier can't quote through a loop that never contacts them.
- **J1/J2** (intake→roadmap→services deep) — need more staged-fixture stages; the fixture exists, the additional stages don't yet.
- **AIQ-1652 memo items #1–#10** — proposal-only, not started, correctly.

---

## 6. Lane discipline (learned this cycle — enforce it)

| Work type | Lane |
|---|---|
| git push / branch / cherry-pick / rebase / migrations | **Claude Code** (repo-connected, has push creds) |
| Live Supabase reads / DB verification / purges | **Cowork** |
| Browser QA / provisioning walks / static-snapshot analysis / research | **Audos** |

**The Audos lane cannot reach `rolec` git or the standalone Supabase** — this blocked ~6 jobs (verify, rebase, DB check, Stripe ×3). Route repo/DB work away from it. A repo task is not done without a commit SHA on a named branch; mirror edits under `imported-source/` are no-ops.

## 7. Standing hard rules (bind every lane)

Never push to `main` · never use `fix/td-qa-services-batch-0719` (unreviewable) · new router → register in BOTH `backend/main.py` + `backend/app/main.py` · new `public` table → RLS + policy + `REVOKE ALL FROM anon` · never `apply_migration` to prod (commit + out-of-band) · never set `OUTBOX_DISPATCH_CRON_ENABLED` · never provision on `insead-2026` (use `qa-*`) · mask PII before any LLM call · no EU AI Act *status* claims in shipped copy.

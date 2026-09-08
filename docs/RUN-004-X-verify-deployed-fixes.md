# RUN 004-X — verify the three deployed fixes (short pass)

**Prod commit: `c917b2ad`** (verified live). Two quick browser jobs for Audos; Cowork already did the DB half of the third.
Same hard rules: type by keyboard · one fixture per browser session · never `insead-2026` · no real emails · never set `OUTBOX_DISPATCH_CRON_ENABLED` · BLOCKED ≠ FAIL · stop before the cap.

**Segment 0 (gate):** `curl -s https://api.relopass.com/health` → must show `"commit":"c917b2ad…"`. If not, stop.

---

## JOB 1 — Movers: employee can now reach ALL 12 vetted (#1699)

**Mint:** `corridor_id":"NL_SG"`, `stage":"shortlist_ready"`, `campaign":"qa-r4x1"`.
**Browser (employee):** sign in (confirm label) → Services → Recommendations → **Movers** tab.
1. Count the movers reachable. Previously capped at 10 with a "2 more available" banner and **no way to see them**.
2. ⭐ **Look for a "Show all / Show 2 more" affordance and use it** → confirm you can now reach **all 12** distinct movers.

**PASS:** all 12 vetted movers are reachable (rendered directly or via the show-more control). **FAIL:** still stuck at 10 with no way to reveal the rest.

**Cowork DB (hand me the case_id):** confirm distinct vetted movers = what you could reach.

---

## JOB 2 — "Add to package" fires ZERO 400s + logs the audit decision (#1696 / #1700)

Root cause (Cowork-captured): the old 400 was `POST /api/ai/decisions` rejecting non-top picks sent as `override` **without a reason**. #1696 reclassifies a plain in-list add as `accept` (no reason needed); #1700 makes any dropped audit write log instead of swallow.

**Mint:** `corridor_id":"FR_NO"`, `stage":"roadmap_ready"`, `campaign":"qa-r4x2"`.
**Browser (employee):** Services → select **Movers + Schools** → answer the pre-filled questions → **Get recommendations**.
1. Add **6 items** (3 movers + 3 schools), including **non-top** picks in each category (the ones that used to 400). PageDown for inner scroll, click by coordinate.
2. ⭐ **Watch the console/network for `400` on `/api/ai/decisions`.** Expected: **zero 400s** now (was 4 of 6). If your harness can't see the network panel, at least confirm **no `Failed to load resource … 400` console lines** appear during the adds.
3. Confirm all 6 land in the package and "Request quotations" enables.

**PASS:** zero 400s during 6 adds; all 6 persist. **FAIL:** any 400 on `/api/ai/decisions`.

**Cowork DB (hand me the case_id):** I'll confirm `ai_decisions` now has a row per pick (overrides/accepts included) and `services_state` holds 6 item ids.

---

## Report block
```
RUN 004-X · JOB __ · DATE ____ · CAMPAIGN qa-r4x_ · CORRIDOR ____
PROD COMMIT (seg 0): ____
JOB 1: movers reachable = ____ / 12 · show-all affordance present? ____
JOB 2: 400s on /api/ai/decisions during 6 adds = ____ (expect 0) · 6/6 persisted? ____
🔴 CRITICAL: ____
FOR COWORK — DB: case ____ assignment ____   ARTIFACTS: qa-r4x_
```

**Already verified by Cowork (no browser needed):** the `canonical_case_id` hardening (AIQ-1731/1732) — DB shows 0 nulls, 0 duplicates, UNIQUE constraint in place. That structurally closes the case-vs-assignment id class of bugs.

# Audos — RUN 004-X close-out (two checks, then STOP)

This is the final verification gating **v0 launch**. Two surgically small jobs. Each has **one** assertion — the moment it passes, record ✅ and **STOP that job. Do not chain, do not add adversarial variants, do not pivot.** These are pure UI/experience checks; all correctness (DB counts, endpoint behaviour) is already proven by Cowork.

## Non-negotiable rules (baked in from prior runs)
- **Deploy gate first, every job:** `curl -s https://api.relopass.com/health` → must be `"commit":"c917b2ad…"`. If not, STOP and report the commit.
- **Type by keyboard** (setting fields programmatically doesn't fire React handlers). **PageDown** for inner scroll containers. **Click custom controls by coordinate, never by ref.** Country fields = dropdown.
- **One fixture per browser session**, fresh session each job (multi-fixture-in-one-browser caused the stale-session logout). Confirm the top-right account label before acting.
- Never `insead-2026` · no real emails · never set `OUTBOX_DISPATCH_CRON_ENABLED` · ≤20 actions/job.
- **A FAIL is not final until corroborated:** if either assertion fails, capture the exact failing request (URL + status + body) OR say "inconclusive" — do not record a FAIL verdict without it. Then hand Cowork the `case_id` regardless of pass/fail so the DB lane confirms.

## Vocabulary appendix (exact strings — do not accept look-alikes)
- Health commit expected: `c917b2ad`.
- Fixture mint: `POST https://api.relopass.com/api/test-drive/provision-staged` with `{"first_name","campaign","corridor_id","stage"}`. Read `employee.email`/`employee.password` from the JSON.
- Stage meaning: `shortlist_ready` = server rows exist; `roadmap_ready` = start pre-shortlist so you exercise the Add flow.
- The 400 under test is on `POST /api/ai/decisions` (the audit write), **not** services-state.

---

## JOB A — Movers: employee can reach all 12 vetted (#1699)
**Mint:** `{"first_name":"R4x1","campaign":"qa-r4x1","corridor_id":"NL_SG","stage":"shortlist_ready"}`
**Steps:** sign in as employee (confirm label) → Services → Recommendations → **Movers** tab.
**⭐ Single assertion:** a **"Show all" / "Show N more"** control is present and, when used, the employee can reach **all 12** distinct movers (previously hard-capped at 10 with no way to see the rest).
- PASS = all 12 reachable → record ✅, STOP.
- FAIL = still stuck at 10 with no reveal control → capture what the "N more" banner says, STOP.
**Hand Cowork:** `case_id` (I confirm 12 distinct vetted movers exist for it).

## JOB B — "Add to package" fires zero 400s (#1696 / #1700)
**Mint:** `{"first_name":"R4x2","campaign":"qa-r4x2","corridor_id":"FR_NO","stage":"roadmap_ready"}`
**Steps:** sign in as employee (confirm label) → Services → select **Movers + Schools** → answer pre-filled questions → **Get recommendations** → add **6 items** (3 movers + 3 schools), **deliberately including non-top picks** in each category (those are the ones that used to 400).
**⭐ Single assertion:** **zero `400`s on `POST /api/ai/decisions`** across all 6 adds. (Old failure: non-top picks sent `decision:'override'` with no reason → `400 {"detail":"Reason is required for decision 'override'."}`.) If your harness has no network panel, assert instead that **no `Failed to load resource … 400` console line** appears during the 6 adds.
- PASS = zero 400s, all 6 land in the package, "Request quotations" enables → record ✅, STOP.
- FAIL = any 400 on `/api/ai/decisions` → capture URL+status+body, STOP.
**Hand Cowork:** `case_id` (I confirm `ai_decisions` has a row per pick and `services_state` holds 6 item ids).

---

## Report block (per job)
```
RUN 004-X · JOB _ · DATE ____ · CAMPAIGN qa-r4x_ · CORRIDOR ____
DEPLOY GATE: commit ____ (expect c917b2ad)
ASSERTION: ____  → PASS / FAIL / INCONCLUSIVE
IF FAIL: exact request URL + status + body ____
FOR COWORK: case_id ____   ARTIFACTS: qa-r4x_
```

When both jobs report ✅ and Cowork's DB corroboration agrees, every v0 launch-blocker is dual-verified → **ship.** No RUN 004-Y.

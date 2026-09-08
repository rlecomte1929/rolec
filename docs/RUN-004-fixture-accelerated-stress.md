# RUN 004 — Fixture-Accelerated Stress Campaign

**Date:** 2026-07-22 · **Target:** `relopass.com` · **Deployed head:** `main @ 81e405d8`
**Executor:** Audos (browser) · DB verification → Cowork · **Format:** RUN 003 *conventions*, inverted *shape*.

---

## 0. Why this is NOT RUN 003 (read first)

RUN 003 walked the whole journey by hand. That caused every marathon death, false blocker, and session that ran out of budget before reaching its assertion (45/50, 40/50, ×4).

**RUN 004 uses the `provision-staged` fixture to JUMP to the state under test**, then stresses the edge. A test that took 45 actions in RUN 003 takes ~8 here.

```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4x","campaign":"qa-r4x","corridor_id":"<CORRIDOR>","stage":"<STAGE>"}'
```
Stages: `credentials · case_created · intake_complete · roadmap_ready · shortlist_ready`.
Returns HR + employee credentials for a session already at that stage. Sign in, start ~2 actions from the assertion.

**Rule:** if a segment can start from a stage, it MUST — do not hand-walk setup. Hand-walking is the anti-pattern this campaign exists to retire.

---

## 1. What we're actually trying to learn (not re-prove)

The happy FR_NO path is proven. RUN 004 targets the **four blind spots**, in priority order:

| Seg | Surface | Why it's unknown |
|---|---|---|
| **A** | Non-FR_NO corridors (GB_US, IN_DE, NL_SG, ES_AE) | **Everything to date was Paris→Oslo.** Do the others provision, seed, resolve currency, render a roadmap? |
| **B** | RFQ HR loop (just shipped) | HR-reads-`rfqs`, dispatch, supplier quote, quote-back — never browser-tested. Q2/Q3. |
| **C** | Stripe paywall (just shipped) | Roadmap gate/unlock — **test-mode only, never a real payment.** |
| **D** | Adversarial / boundary inputs | Concurrency, malformed input, escaping — cheap via fixture. |

---

## 2. Global rules

1. **Campaign per segment:** `qa-r4a` … `qa-r4d`. **Never `insead-2026`.**
2. **Mint via `provision-staged`.** Read credentials from the JSON (`employee.email`/`employee.password`, `hr.email`/`hr.password`), not a screenshot.
3. **≤20 actions per run.** The fixture makes this comfortable. Stop before the cap.
4. **Type by keyboard · PageDown for wheel-ignoring inner containers · click custom controls by coordinate, never by ref · country fields use the dropdown.** (The three lessons that cost runs.)
5. **🔴 STRIPE: test-mode only. Never enter real card details, never complete a real payment.** Use only the test-card instructions the paywall itself shows (test-drive mode surfaces them). If a real-payment field with no test instructions appears → **stop, that's the finding.**
6. **No real emails:** a hard guard (`2dbe082d`) blocks test personas from emailing suppliers. If any segment produces an *actual* outbound email → 🔴 critical, stop.
7. Screenshot each assertion. One retry max. **BLOCKED ≠ FAIL.** Approve no supplier records. Report every `qa-r4*` artifact for purging.

---

## SEGMENT A — Corridor coverage ⭐ biggest blind spot

**Question:** do the 4 non-FR_NO corridors actually work, or is the platform silently FR_NO-only?

**Run 4 short passes, one per corridor.** For each: mint at `stage=shortlist_ready`, sign in as employee, reach Recommendations + Review & budget.

| Corridor | Route | Tier |
|---|---|---|
| `IN_DE` | India → Munich | A (real content expected) |
| `GB_US` | London → New York | B (thin) |
| `NL_SG` | Amsterdam → Singapore | B (thin) |
| `ES_AE` | Madrid → Dubai | B (thin) |

**Per corridor record:**
- Did `provision-staged` **succeed** for this corridor? (HTTP 200 + non-empty `shortlist`?) — if 404/empty, that corridor doesn't stage → finding.
- Origin/destination render correctly (not defaulted to Oslo)?
- **Currency** — IN_DE→EUR, GB_US→USD, NL_SG→? (SGD not in FX map → expect USD fallback), ES_AE→? (AED → USD fallback). Record actual.
- Supplier counts per category — non-zero, or empty marketplace?
- Roadmap renders with corridor-appropriate content, or generic fallback?
- Early-coverage warning shown for Tier-B corridors?

**This is the highest-value segment** — it's never been looked at. A corridor that 404s on staging or shows Oslo as origin is a real launch-scope finding.

---

## SEGMENT B — RFQ HR loop, end to end ⭐ (Q2/Q3, finally runnable)

**Question:** does the just-shipped HR loop close — HR sees the picks, dispatches, supplier quotes from the inbox, quote returns?

Mint `stage=shortlist_ready` on `qa-r4b`, `corridor=FR_NO`. Capture **both** credential sets.

1. Employee → Review & budget → **Request quotes** → submit. Confirm.
2. Sign in as **HR**. ⭐ Does the **Pending RFQs / Provider Coordination** panel now show the **6 picked vendors with status**? (AIQ-1681 repointed this to canonical `rfqs` — verify it renders.)
3. ⭐ HR **dispatches** the RFQ. Record: is a **supplier magic link surfaced in the inbox** (per the inbox-only decision)? Copy it.
4. Open the link in a **clean context** → supplier submits a quote (amount `1234`, note `QA R4B`). Confirm.
5. Back as HR → does the **quote appear** / link to the quote-review page (AIQ-1679)?
6. ⭐ Confirm **no real email** was implied — the flow should route through the inbox, not "emailed to supplier."

**Cowork DB-verifies:** `rfq_recipients.token_hash` now 6/6 (was 0/6); `quotes`/`quote_lines` row on submission; **zero Resend log entries**.

---

## SEGMENT C — Stripe roadmap paywall 🔴 test-mode only

**Question:** does the roadmap gate for an unpaid case and unlock after a test-mode payment?

Mint `stage=roadmap_ready` on `qa-r4c`, `corridor=FR_NO`. Sign in as employee.

1. Is the roadmap **gated** behind a paywall for a `free`/unpaid case? Record the gate copy.
2. Does the paywall show **test-mode payment instructions with exact test-card details** (AIQ-1648, test-drive only)? Record them.
3. ⭐ **Using ONLY the on-screen test card**, complete the test-mode checkout. **Never a real card.**
4. After checkout: does it **return to the roadmap** and **unlock** it (AIQ-1644 webhook-lag poll)? How long until unlock?
5. Try to reach a paid surface on a *second, unpaid* case → still gated? (entitlement scoping, AIQ-1652 fail-open fix).

**If any step asks for a real card with no test instructions → stop, that's the finding.** Do not improvise a payment.

**Cowork DB-verifies:** `access_tier` flip `free → roadmap`; no duplicate on webhook retry.

---

## SEGMENT D — Adversarial / boundary (cheap, run if budget)

Independent, fixture-accelerated. Each ~5 actions.

| ID | Case | Expected |
|---|---|---|
| D1 | RFQ submit twice rapidly (same shortlist) | One RFQ, no dup |
| D2 | Supplier opens magic link **after** submitting a quote | Rejected (409 "already quoted") |
| D3 | Supplier quote note = `<script>alert(1)</script>` | Stored + rendered **escaped**; no dialog |
| D4 | Quote amount `0`, negative, `999999999999` | Validated / no overflow |
| D5 | `provision-staged` with `stage=INVALID` | 422, clean error (not 500) |
| D6 | `provision-staged` with `campaign=insead-2026` | **Rejected** (gate must refuse the live cohort) |
| D7 | `provision-staged` with `stage=shortlist_ready` on a Tier-B corridor | Sane result or honest early-coverage state |
| D8 | Two staged sessions, same first name | Distinct sessions, unique suffixes |

D6 is a **safety assertion** — the fixture must never touch the live cohort.

---

## 3. Report block (per segment)

```
RUN 004 · SEG __ · DATE ____ · CAMPAIGN qa-r4_ · CORRIDOR ____
MINT: stage ____ · HTTP ____ · shortlist non-empty? ____
BUDGET USED __/50   VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

WHAT I OBSERVED (facts only): ____
🔴 CRITICAL (report first, stop): ____

FOR COWORK — DB: [tables + identifiers] ____
ARTIFACTS TO PURGE: qa-r4_ ____
BLOCKED BY: ____
```

## 4. Sequence & learning goal

Run **A first** (biggest unknown), then **B** (loop finally testable), then **C** (paywall), **D** as budget allows. One segment per session; mint fresh each time.

**What we learn:** whether the platform is genuinely multi-corridor or FR_NO-only; whether the RFQ loop closes for real; whether payment gates correctly; and where the edges break. None of this is re-proving the happy path — it's mapping the parts nobody has looked at, fast, because the fixture removes the setup tax that made RUN 003 collapse.

# RUN 004-S — Scoped Verification Campaign

**Date:** 2026-07-20 · **Target:** `relopass.com` / `api.relopass.com` · **Deployed head:** `main @ 518bf11c`
**Executor:** Audos (browser, black-box) · DB verification routed to Cowork · code reads via GitHub API
**Format:** RUN 003 conventions — segments, fresh session each, ≤40 actions, `PASS / FAIL / BLOCKED / NOT-RUN`, **BLOCKED ≠ FAIL**

---

## 0. Why "scoped" and not RUN 004

Only **one** app-code change has reached `main` since RUN 003: `518bf11c` (notification outbox). Verified:

| Commit | Contents | State |
|---|---|---|
| `5f3baf0e` | outbox recipient allowlist guard (S1a) | **branch only — NOT deployed** |
| `3f9ed63a` | eager policy resolution (P0-1) | **branch only — NOT deployed** |
| `121403c8` | F14 shared taxonomy | **branch only — NOT deployed** |

**Therefore explicitly OUT of scope** — testing them against production would re-measure RUN 003 and manufacture false failures:

- ❌ Over-cap → Policy Exception → HR notification (needs `3f9ed63a` + a persistence decision)
- ❌ Policy resolution coverage (same)
- ❌ Service→benefit taxonomy (needs `121403c8`)
- ❌ The outbox recipient guard (needs `5f3baf0e` merged)

**IN scope — four things never tested, all testable today:**

| Segment | What | Why now |
|---|---|---|
| **A** | Supplier exposure | 9 auto-approved, unvetted suppliers are live. Exposure is unmeasured. |
| **B** | RFQ loop end to end | Fully built, six migrations, **never QA'd**. |
| **C** | Notification delivery | The only thing that shipped. Ungated dispatcher on `main`. |
| **D** | Regression sweep | Confirm the 12 fixes verified 2026-07-19 still hold. |

---

## 1. GOALS

**G1 — Establish empirically whether unvetted suppliers reach customers.** Nine Norway suppliers carry `platform_vetting_status='approved'` with `vetted_by=NULL`, auto-approved at import. Database exposure is zero (no RFQs, no shortlists), but nobody has checked whether they *render*. Convert a hypothesis into a measured fact.

**G2 — Produce the first honest defect list for the RFQ layer.** It was reported non-functional, is in fact fully built, and has never been walked end to end. Establish what works before anyone writes RFQ code.

**G3 — Confirm the one shipped change behaves, and that the email cron is inert.** `518bf11c` added a 15-minute dispatcher with no recipient guard on `main`. Confirm it cannot fire, and that policy-exception notification behaviour matches intent.

**G4 — Protect the fixes already banked.** Twelve fixes were verified on 2026-07-19. Confirm none regressed under `518bf11c`.

**Non-goal:** proving the over-cap chain. It is gated on an undeployed fix and an undecided design. Any attempt will BLOCK.

---

## 2. SPEC — global rules

1. **Campaign isolation:** every URL uses `?campaign=qa-run004s`. **Never** the plain link — it defaults to `insead-2026`, live cohort data, already purged twice.
2. **Pin the corridor:** `&corridor=FR_NO` (Paris→Oslo). Tier-A, and the only corridor where the 9 Norway suppliers apply — which is what makes Segment A possible.
3. **Fresh session per segment**, ≤40 actions. Approaching the cap → stop and report partial. Never fail a run on budget.
4. **Carry credentials between segments in your run log.** A fresh context loses them; a lost password already killed one run.
5. **Never re-provision mid-segment** — it creates a new case and voids the run.
6. **UI-observable assertions only.** Database questions go to Cowork.
7. **Change nothing.** No approvals, no supplier edits, no enabling of any variable, no commits.
8. Screenshot every assertion as `RUN004S-<step>`. One retry max per step.
9. Report every `qa-run004s` artifact for purging.

### 2.1 Survival rules (these killed prior runs)

- **S1 — Never type into a pre-filled country field.** On intake Step 2, `Nationality` pre-fills and `Passport country` auto-populates on focus. Typing **appends** → "FranceFranc" → permanent "No match"; backspace and Cmd+A do not clear it. **Recovery: reload the page.** Auto-save restores the clean value.
- **S2 — Sign-in may need a ref-click.** Coordinate clicks sometimes don't submit; click by element reference or press Enter in a field.
- **S3 — Decline the PostHog consent banner first.** It overlays the page bottom and blocks clicks. May reappear after a session change.
- **S4 — Already-signed-in guard:** click "Sign out and use my test account".
- **S5 — Native `<select>`** may ignore clicks; set the value or use keyboard + Enter.

### 2.2 Run log

```
RUN 004-S | date ____ | campaign qa-run004s | corridor FR_NO (pinned) | main @ 518bf11c
HR_EMAIL ____ HR_PW ____ | EMP_EMAIL ____ EMP_PW ____
INTAKE_CASE_ID ____ | SERVICES_CASE_ID ____
Seg A __ | Seg B __ | Seg C __ | Seg D __
```

---

## 3. PLAN

### SEGMENT A — Supplier exposure *(highest value; run first)*

**Question:** do the 9 auto-approved, unvetted Norway suppliers render to a customer?

| # | Action | Expected | Verdict |
|---|---|---|---|
| A1 | Provision at `/test-drive?campaign=qa-run004s&corridor=FR_NO`; decline banner; first name `RunA`; capture both credential pairs | Credentials issued; page reads **Paris → Oslo** | FAIL if corridor differs |
| A2 | Sign in as HR → create case → assign to the employee, seniority **Manager** | "Assignment created" + "Open case →" | FAIL if silent |
| A3 | Record `INTAKE_CASE_ID` | Captured | — |
| A4 | Sign in as employee (fresh context) → complete intake. **Step 2: fill Full name + Passport expiry ONLY** (S1) | Reaches roadmap | Reload on "No match" |
| A5 | Open **Services** | Wizard loads | — |
| A6 | **Inspect the Banks / Banking category** | Record whether **DNB Bank**, **Nordea Norway**, **SpareBank1** appear | **If any appear → EXPOSURE CONFIRMED** |
| A7 | **Movers** | Record whether **Crown Relocations (Norway)**, **AGS Movers Norway** appear | as above |
| A8 | **Legal / immigration** | **Expat Relocation Norway**, **Immigrationlawyer.no** | as above |
| A9 | **Tax / finance** | **PwC Norway (Global Mobility)**, **BDO Norway (International Tax)** | as above |
| A10 | For any that appear, capture what is shown — name, description, contact, any "verified" badge | Screenshot each | Evidence for severity |
| A11 | If **none** appear: record what *is* shown per category, so Cowork can trace the filter | List rendered suppliers | Determines whether a filter exists |

**Interpretation:** any of the nine rendering = a live product issue — unvetted, machine-imported vendors presented to a customer as platform suppliers. **Do not fix it, do not edit any record.** Report with screenshots.

---

### SEGMENT B — RFQ loop end to end *(fresh session)*

**First honest defect list for a fully-built, never-tested subsystem.** Expect breakage; that is the point. Record each break with layer (UI / API / data), reproduction, and whether it blocks or degrades the loop.

| # | Action | Expected | Verdict |
|---|---|---|---|
| B1 | Sign in as employee (Segment A credentials); open **Services** | Loads on the same case | FAIL if a new case appears |
| B2 | Initiate a quote / RFQ request for a service category | Request form opens | FAIL if entry point missing |
| B3 | Submit the request | Confirmation; a request record appears | Record the exact failure if not |
| B4 | Sign in as HR → find the RFQ | Visible with status | FAIL if HR cannot see it |
| B5 | Inspect recipients | Suppliers listed; note **which** — cross-check against the Norway nine | Feeds Segment A |
| B6 | Locate the supplier magic link (if surfaced in the UI) | Link present | BLOCKED if only emailed |
| B7 | Open the supplier quote page in a **clean context** (no session) | Public page loads, scoped to that RFQ only | FAIL if it requires login or exposes other data |
| B8 | Submit a quote as the supplier | Accepted | Record failure precisely |
| B9 | Return as HR / employee | Quote visible; comparison surface if any | FAIL if submitted quote never appears |
| B10 | Record which UI vocabulary is used — "RFQ" vs "quote request" | Note wording per screen | Feeds the A1 canonical-model audit |

**Security checks (record, do not exploit):**
- B7a — does the supplier page expose any case PII beyond the brief (employee name, address, salary)? **Any leak is 🔴 critical, stop and report.**
- B7b — does the URL contain a guessable identifier, or a token?

---

### SEGMENT C — Notification delivery + cron inertness *(fresh session)*

| # | Action | Expected | Verdict |
|---|---|---|---|
| C1 | HR sends a message on the case thread | Sent | — |
| C2 | Employee opens the notification bell | Message appears; **badge count == items listed** | FAIL on false badge (F3 regression) |
| C3 | Employee replies | Sent | — |
| C4 | HR opens the bell | Reply appears | FAIL if cross-persona delivery breaks |
| C5 | **Check the test inbox** for `@probe.test` addresses | Note whether any email was generated | Records current email-vs-in-app behaviour |
| C6 | **Do NOT set `OUTBOX_DISPATCH_CRON_ENABLED`.** Confirm via GitHub API that the repo variable is unset | Unset | **FAIL if set — escalate immediately** |
| C7 | Confirm `5f3baf0e` is still unmerged | Branch only | Guard is not protecting production yet |

**Note:** the dispatcher on `main` has **no recipient guard** — that fix is on an unmerged branch. C6 is the only thing preventing real sends. Treat it as a safety assertion, not a checkbox.

---

### SEGMENT D — Regression sweep *(fresh session, ≤25 actions)*

Confirm the 12 fixes verified 2026-07-19 still hold under `518bf11c`. Spot-check; do not re-run exhaustively.

| # | Fix | Assertion |
|---|---|---|
| D1 | F1 | Credential emails render in full, not truncated |
| D2 | F2 | "Assignment created" confirmation appears |
| D3 | F4 | No "you haven't published a benefits policy" banner |
| D4 | F8 | Intake address shows "Verified" + commute map |
| D5 | F10 | Roadmap renders **in-session** — *not* the "2 working days" holding state |
| D6 | F15 | No "destination missing" dead-end |
| D7 | F16 | `SERVICES_CASE_ID` **==** `INTAKE_CASE_ID` |
| D8 | TD-BUG-2 | Already-signed-in guard appears |
| D9 | TD-BUG-4 | HR landing is case-first, setup marked "Optional" |
| D10 | TD-BUG-5 | "No invite email was sent" |
| D11 | TD-BUG-6 | Employee landing says "Your relocation starts here"; the word "journey" absent |
| D12 | F12 | Record the estimate currency — expect **USD**; correct is **NOK**. **Known-open, not FAIL** |

---

## 4. EDGE CASES

Independent, short, skippable. Run as budget allows.

| ID | Case | Expected |
|---|---|---|
| E1 | Supplier magic link opened **after expiry** | Rejected |
| E2 | Supplier token A used to request RFQ B | **Denied** — cross-tenant guard. Any success is 🔴 critical |
| E3 | Supplier page opened twice / quote submitted twice | No duplicate quote, no error state |
| E4 | RFQ submitted with **no** eligible suppliers in category | Graceful empty state, no crash |
| E5 | Quote submitted with a negative or zero amount | Validated / rejected |
| E6 | Quote amount with 15 decimal places or 1e12 | Handled, no overflow |
| E7 | Supplier name / quote note containing `<script>alert(1)</script>` | Stored and rendered **escaped** |
| E8 | Two concurrent cases, same employee | Case binding stays correct (F16 guard) |
| E9 | Provision with `?corridor=INVALID` | Safe fallback, **no 500** |
| E10 | Deliberately corrupt the Nationality field → reload | Reload restores clean value (documents S1) |
| E11 | Intake submitted with destination blank | Graceful prompt, not the F15 dead-end |
| E12 | Employee signs in **before** HR hands off (second provision) | Sensible empty state, no spinner |
| E13 | Tier-B corridor `&corridor=NL_SG` | Early-coverage warning; thin roadmap acceptable, not FAIL |
| E14 | Confirm **zero** rows created under `insead-2026` | Real campaign stays clean |

---

## 5. METRICS

| Metric | Baseline | Target |
|---|---|---|
| Unvetted Norway suppliers rendered to a customer | **unmeasured** | measured — count + screenshots |
| RFQ loop completion (request → quote visible to HR) | **never tested** | measured, with a defect list |
| RFQ security findings (PII leak, cross-tenant) | unknown | enumerated with severity |
| Cross-persona notification delivery | 2/2 (07-19) | 2/2 held |
| Badge count accuracy (F3) | correct | correct |
| `OUTBOX_DISPATCH_CRON_ENABLED` | unset | **unset** |
| Regression count among the 12 banked fixes | 0 | **0** |
| Rows created under `insead-2026` | 0 | **0** |

---

## 6. VERIFICATION

- **Per segment:** screenshot per assertion, named `RUN004S-<step>`.
- **Segment A:** any supplier rendered must be evidenced by screenshot, not description.
- **Segment B:** output is a written defect list — reproduction steps per defect, layer, blocking vs degrading. Each becomes a Notion AI Work Queue item with Layer + Autonomy Tier.
- **Any 🔴 finding** (case PII on the supplier page, cross-tenant token access, cron enabled) → **stop the campaign and escalate immediately.** Do not continue collecting.
- **Database confirmation** — routed to Cowork, not Audos:
  - did any `qa-run004s` RFQ write to `rfqs` or `rfq_requests`? (settles the A1 canonical question with live evidence)
  - did any Norway supplier enter `rfq_recipients`?
  - `insead-2026` row count unchanged?
- **Diff rules vs RUN 003:** BLOCKED → PASS = a gating fix shipped. PASS → FAIL = genuine regression, file immediately. Known-open still failing = expected, confirm only.

---

## 7. Report

```
RUN 004-S | date ____ | main @ 518bf11c | campaign qa-run004s | corridor FR_NO

SEG A — SUPPLIER EXPOSURE
  Banks: DNB __ Nordea __ SpareBank1 __
  Movers: Crown NO __ AGS __
  Legal: Expat Relocation NO __ Immigrationlawyer.no __
  Tax: PwC NO __ BDO NO __
  EXPOSURE CONFIRMED? ____   Screenshots: ____
  If none rendered — what WAS shown per category: ____

SEG B — RFQ LOOP
  Furthest step reached: ____
  Defects [layer | repro | blocking?]: ____
  B7a case PII on supplier page? ____   B7b token or guessable id? ____
  UI vocabulary observed (RFQ vs quote request): ____

SEG C — NOTIFICATIONS
  HR→emp __  emp→HR __  badge==list __  emails generated: ____
  OUTBOX_DISPATCH_CRON_ENABLED: ____ (MUST be unset)   5f3baf0e merged? ____ (MUST be no)

SEG D — REGRESSION
  D1..D11 pass? ____   Regressions: ____   D12 currency: ____ (known-open)

EDGE CASES RUN: ____   Failures: ____
🔴 CRITICAL FINDINGS: ____
ARTIFACTS TO PURGE: ____
```

**Sequence:** A → B → C → D, edge cases last. Segment A first because it is the only one measuring a live customer-facing risk. Start only after Track B (`qa-p0-1`) has finished — do not interleave campaigns.

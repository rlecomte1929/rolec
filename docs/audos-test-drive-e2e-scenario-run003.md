# ReloPass Test-Drive — E2E Scenario **RUN 003** (four-segment format)

**Supersedes:** v1 single-block, the v2 three-segment draft, and the earlier RUN 003 draft (whose over-cap premise was wrong — see §0).
**Executor:** Audos autonomous browser QA — black-box, UI-observable assertions only.
**Built on:** the v2 three-segment design, corrected by **live manual verification 2026-07-19** (campaign `qa-verify-0719`, corridor FR_NO), which **inverted six** of v2's expectations and **re-diagnosed** the over-cap blocker.

---

## 0. ⚠️ READ FIRST — corrections that prevent false results

### 0.1 Six v2 expectations are now INVERTED
Asserting them as-written would produce false FAILs *in the opposite direction*.

| v2 said | Verified reality (2026-07-19) | RUN 003 assertion |
|---|---|---|
| B6: assert the **"2 working days" holding state**; an instant roadmap = false FAIL | **F10 FIXED** (AIQ-1614): roadmap renders **in-session** — "Roadmap validated", 16 tasks, 5 phases | **Assert a RENDERED roadmap.** Holding state = **FAIL** |
| B7a: `SERVICES_CASE_ID` should **differ** (F16) | **F16 FIXED** (AIQ-1612): same case id as intake | **Assert MATCH.** Mismatch = **regression** |
| B10: expect **"Destination missing"** (F15) | **F15 FIXED** (AIQ-1613): no block | **Assert it advances** |
| A7: expect **no success toast** (F2) | **F2 FIXED** (AIQ-1617): "Assignment created" + "Open case →" | **Assert confirmation appears** |
| A8: HR must publish a policy (fresh acct has none) | **F4 FIXED** (AIQ-1621): a default policy is **already published** at provisioning | **Assert one already exists;** publishing is optional |
| A4: credential emails **truncate** (F1) | **F1 FIXED** (AIQ-1622): full emails render | **Assert full email readable** |

Also fixed since v2: **F8** geocoding (address shows "Verified" + live commute map), **F7/F6** policy publish, **TD-BUG-6** ("journey" removed).

### 0.2 The over-cap blocker was MIS-DIAGNOSED — this matters most
The earlier RUN 003 draft told the agent that Housing "now shows a real cap comparison" and that "No policy rule" must be gone. **That is not true on the live build**, and the reason is *not* the taxonomy:

- ✅ The **taxonomy bridge shipped** (AIQ-1611).
- ✅ The **seed is correct** — `policy_config_benefits` for test-drive companies contains `host_housing_cap`, covered, at **5500 / 3800 / 2400 EUR**.
- ❌ **Policy RESOLUTION never runs for `is_test` cases.** Resolved policies: **0 of 31** test-drive cases — versus **2 of 2** real cases. `resolved_assignment_policy_benefits` is empty, and the Services page reads *resolved* benefits.

**Consequence:** every Services card still reads "No policy rule for this category". This is **BLOCKED (known)**, *not* FAIL, and *not* a taxonomy problem. RUN 003 must include the diagnostic in **B16** to distinguish the two, so the result is attributed correctly.

### 0.3 Still genuinely open (record, don't FAIL)
- **F12-R currency** — defaults to **USD**; correct default on Paris→Oslo is **NOK** (destination currency — note the original ticket wrongly said "EUR").
- **Country autocomplete** — pre-filled country fields **append** typed input and cannot be cleared (see S1). Most likely cause of the RUN 002 intake stall.
- **Segment capture** — `tester_segment` is only captured at the survey by design, so any dropout is NULL.

---

## 1. Global rules (non-negotiable)

1. **Campaign isolation:** every URL uses `?campaign=audos-e2e-03`. **NEVER** the plain `/test-drive` link — it defaults to `insead-2026`, the real cohort campaign (purged twice already because of this).
2. **Pin the corridor:** always append `&corridor=FR_NO` (Paris→Oslo, Tier-A, real immigration content). Randomisation is what made RUN 001 and RUN 002 incomparable.
3. **Fresh session per segment**, **≤40 actions each**. If you near the budget, stop and report the segment partially — never fail the run for budget.
4. **NEVER re-provision after Segment A.** B/C/D sign in at `/auth?mode=login` with A's captured credentials. Re-provisioning creates a new case and invalidates the run.
5. **Carry variables between segments** via the run log (§3) — a fresh session loses local state.
6. **UI-observable assertions only.** No database access.
7. **Verdicts:** `PASS` · `FAIL` (worked before, broken now) · `BLOCKED` (unreachable due to a *known* open defect) · `NOT-RUN`. **BLOCKED ≠ FAIL.**
8. Screenshot every assertion as `RUN003-<step>`. One retry max per step. **Fix nothing.**
9. Report every `audos-e2e-03` artifact created, for cleanup.

---

## 2. 🛟 Survival rules — this is where previous runs died

**S1 — NEVER type into a pre-filled country field.** On intake Step 2, `Nationality` arrives pre-filled ("France") and `Passport country` **auto-populates on focus**. Typing **appends** → "FranceFranc" → permanent "No match". Backspace ×25 and Cmd+A do **not** clear it.
> **If a country field shows "No match" → RELOAD the page.** Auto-save restores the clean value. Then fill only genuinely empty fields. This single rule most likely prevents the stall that ended RUN 002.

**S2 — Sign-in needs a ref-click.** Coordinate clicks on "Sign in" sometimes don't submit. Click **by element reference**, or focus a field and press **Enter**.

**S3 — Dismiss the analytics banner first.** A PostHog EU consent banner overlays the page bottom. Click **Decline**; it may reappear after a session change.

**S4 — Already-signed-in guard.** If a session exists, `/test-drive` shows "You're already signed in as … Sign out first" plus a **"Sign out and use my test account"** button. Click it.

**S5 — Native `<select>`** may ignore clicks — set the value directly or use keyboard + Enter.

---

## 3. Run-log variable block (fill first; carry across segments)

```
RUN_ID: RUN 003     DATE: ____     CAMPAIGN: audos-e2e-03
CORRIDOR: FR_NO (Paris → Oslo)  [PINNED]     SENIORITY: Manager
POLICY_PUBLISHED: (expect pre-seeded = YES)
ESTIMATE_CURRENCY: ____ (expect USD until F12-R ships; correct = NOK)
HR_EMAIL: ____        HR_PASSWORD: ____
EMP_EMAIL: ____       EMP_PASSWORD: ____
INTAKE_CASE_ID: ____  SERVICES_CASE_ID: ____   MATCH? ____
ROADMAP_STATE: (rendered | holding)
HOUSING_CARD_STATE: (policy limit shown | "No policy rule")
```

---

## SEGMENT A — HR setup (fresh session #1, ≤40 actions)

| # | Action | Expected | Verdict rule |
|---|---|---|---|
| A1 | Load `https://relopass.com/test-drive?campaign=audos-e2e-03&corridor=FR_NO` | Hero "Run one relocation, end to end"; eyebrow **PARIS → OSLO**; Start form near top | FAIL if hero/form absent |
| A2 | Decline the analytics banner (S3) | Banner gone | — |
| A3 | Assert corridor pinning | "Your corridor: Paris → Oslo" **and** step 2 "Your route is already set: Paris → Oslo" | FAIL on a different corridor |
| A4 | First name = `Audos3`; email blank; **Start the test** | "Your two test logins" appears | FAIL if no credentials |
| A5 | Capture `HR_*` / `EMP_*` | Both `@probe.test`; **emails fully readable** (F1 fixed) | FAIL on truncation |
| A6 | Assert "Your test: Paris → Oslo — already set for you." | Present | — |
| A7 | **Sign in →**, then sign in as HR (S2/S4) | `/hr/welcome` loads | FAIL if login fails |
| A8 | Assert HR landing is **case-first** (TD-BUG-4) | "**Open your first relocation case**"; setup shown as "**Optional**" | FAIL if forced through company setup |
| A9 | Click **Create your first case →** | Case form opens **directly**, no bounce to `/hr/welcome` | FAIL if it loops (TD-BUG-1 regression) |
| A10 | Assert missing-policy banner is **absent** (F4 fixed) | No "you haven't published a benefits policy" warning | Record `POLICY_PUBLISHED` |
| A11 | Employee email = `EMP_EMAIL`; first name `Audos3`; **Seniority = Manager** (S5) | Accepted | — |
| A12 | Click **Assign** | **"Assignment created"** + **"Open case →"** appear immediately | **FAIL if silent** (F2 regression) |
| A13 | Assert no Resend invite (TD-BUG-5) | "**No invite email was sent** — … test account" | FAIL if an invite was emailed |
| A14 | **Open case →**; record `INTAKE_CASE_ID` from the URL | Case Summary: route **Paris → Oslo**, reference, shared plan, **Policy exceptions** panel, Suppliers & Budget | FAIL on route mismatch |
| A15 | HR **Inbox** → case thread → send: *"Hi Audos3 — your budget is at the Manager tier cap. Anything above needs my approval."* | Shows as sent | Required for the 2-notification assertion (B3) |
| A16 | *(Optional, budget permitting)* Policy → publish **once**, reload | Single clear publish; no stuck spinner; Builder and Published tab **agree** (F7/F6) | FAIL on 409 / stuck spinner / contradiction |

**Verdict A:** PASS if the case exists on the correct corridor and the assignment confirmation appeared.

---

## SEGMENT B — Employee: intake → roadmap → services (fresh session #2, ≤40 actions)

| # | Action | Expected | Verdict rule |
|---|---|---|---|
| B1 | New session → `/auth?mode=login`; decline banner; sign in as `EMP_EMAIL` (S2) | `/employee/welcome` | — |
| B2 | Assert landing copy | "**Your relocation starts here**" — "journey" must **not** appear (TD-BUG-6) | FAIL if "journey" present |
| B3 | Open the notification bell | **[HEADLINE 1 · HR→emp]** **2** unread: case assigned **+** the HR cap message from A15 | FAIL if 0; note if only 1 |
| B3a | Badge count == number listed (F3 fixed) | Match | FAIL on false badge |
| B4 | **Intake** Step 1: target date ~60 days out (corridor pre-filled) | Advances | — |
| B5 | Step 2: fill **Full name** + **Passport expiry ONLY**. **DO NOT TYPE into Nationality / Passport country** (S1) | Continue enables | **If "No match" → RELOAD (S1), then continue** |
| B6 | Step 3: continue solo | Advances | — |
| B7 | Step 4: job title, contract start, salary band, office address `Karl Johans gate 1, Oslo`, work pattern, assignment type | Address shows "**Verified**" + live commute map (F8 fixed) | FAIL if geocode silently fails |
| B7a | Assert **Continue** reachable by normal scroll (not hidden behind the fixed legal footer — R2-07) | Visible above footer | Record if PageDown was needed |
| B8 | Step 5 Review: tick the data-use checkbox; **leave the optional AI-improvement consent unticked**; **✦ Generate my roadmap** | Submits → roadmap | — |
| B9 | Record `INTAKE_CASE_ID` from the roadmap URL | Captured | Must equal A14's id |
| B10 | **[HEADLINE 2 · the payoff]** Observe the roadmap | **RENDERED in-session**: "Roadmap validated", "Paris to Oslo", phased tasks (Pre-departure/Immigration/Logistics/Arrival/Post-arrival), progress % | **FAIL if "We're building your roadmap… 2 working days"** — that is now a regression |
| B11 | Open **Services**; record `SERVICES_CASE_ID` from the URL | Wizard loads | — |
| B12 | **Compare `SERVICES_CASE_ID` vs `INTAKE_CASE_ID`** | **MUST match** (F16 fixed) | **FAIL on mismatch** |
| B13 | Assert no destination block (F15 fixed) | No "Destination city/country is missing" | **FAIL if blocked** |
| B14 | Record `ESTIMATE_CURRENCY` | Expect **USD**; correct = **NOK** | **Known-open (F12-R)** — not FAIL |
| B15 | Assert policy wiring banner | "**Company policy comparison is active**" | FAIL if absent |
| B16 | **[HEADLINE 3 · over-cap DIAGNOSTIC]** Inspect the **Housing** card | **Branch:** (a) shows a **policy limit / cap comparison** → resolution ran → **go to B17**. (b) reads "**No policy rule for this category**" → **BLOCKED (known)** — cause is *policy resolution not firing for is_test cases*, **not** the taxonomy | Record `HOUSING_CARD_STATE`. Note: uncapped categories (Insurance, Electricity, Pets) legitimately show no cap — that is correct, not a defect |
| B17 | *(Only if B16a)* Select a Housing option **above** the cap; advance to Review & budget | Over-cap / "needs approval" / over_budget indication appears | FAIL if an over-cap selection is accepted silently |
| B18 | Before leaving: reply on the HR thread — *"The Manager cap looks low for Oslo — can we discuss?"* | Sent | Required for C2 |

**Verdict B:** PASS through B15. B16–B17 **BLOCKED** until policy resolution fires for `is_test` cases (0/31 today; real cases 2/2).

---

## SEGMENT C — HR verify (fresh session #3, ≤30 actions)

| # | Action | Expected | Verdict rule |
|---|---|---|---|
| C1 | New session; sign in as HR | Console loads | — |
| C2 | Open the notification bell | **[HEADLINE 4 · emp→HR]** the employee reply (B18) is present | **FAIL if absent** — cross-persona break |
| C3 | Open the case → **Policy exceptions** panel | If B17 ran: an automated **Policy Exception** row. If B16 was BLOCKED: panel empty → **BLOCKED**, not FAIL | Record |
| C4 | *(Only if B17 ran)* Assert HR got an **in-app** notification about the exception and **zero emails** | In-app notification present | FAIL if emailed instead |

---

## SEGMENT D — Completion + survey (fresh session #4, ≤25 actions)

| # | Action | Expected | Verdict rule |
|---|---|---|---|
| D1 | Return to `/test-drive?campaign=audos-e2e-03&corridor=FR_NO` (sign in as employee if needed) | Session recognised | — |
| D2 | Click **I've completed my test** | Routes to the survey | FAIL if it dead-ends |
| D3 | Segment question ("Do you work in HR, mobility or relocation?") → **Yes** | Accepted → records `prospect` | — |
| D4 | Complete: overall 4/5; friction text; problem-fit; one change; **testimonial + tick quote consent**; trust/intent; **pilot interest = Yes**; referral + `referral@probe.test` | Accepted | — |
| D5 | Submit | Thank-you confirmation | FAIL if blocked |

---

## 4. Edge-case suite (independent; run only if budget remains)

| ID | Edge case | Expected |
|---|---|---|
| E1 | Same first name provisioned **3×** | 3 distinct sessions, unique suffixes, no collision |
| E2 | Provision **without** `&corridor=` | Auto-assigned from the 5, Tier-A favoured |
| E3 | `?corridor=INVALID` | Safe fallback to auto-assign; **no 500** |
| E4 | Visit `/test-drive` while already signed in | "Sign out to use your test account" guard (TD-BUG-2) |
| E5 | Click **I've completed my test** twice quickly | No duplicate/error state |
| E6 | Open `/test-drive/survey` with **no session** | Handled gracefully; no crash |
| E7 | Survey with **all optional fields blank** (segment only) | Succeeds |
| E8 | Answer segment **"No"** | Stored as `internal`, not prospect |
| E9 | **Invalid email** in the survey lead-in | Validated / rejected |
| E10 | Testimonial `<script>alert(1)</script>` | Stored + rendered **escaped**; no execution |
| E11 | Employee signs in **before** HR hands off (2nd provision) | Sensible empty state; no spinner/crash |
| E12 | Deliberately type into pre-filled Nationality → "No match" → reload | Reload restores clean value (documents S1) |
| E13 | Tier-B corridor `&corridor=NL_SG` | Early-coverage warning; thin roadmap is **acceptable**, not FAIL |
| E14 | Confirm **zero** rows created under `insead-2026` | Real campaign stays clean |

---

## 5. Report format

```
RUN 003 | <date> | corridor: FR_NO (pinned) | seniority: Manager | policy: pre-seeded | currency: ____
Seg A: __   Seg B: __   Seg C: __   Seg D: __
Headlines: H1 HR→emp notif __ | H2 roadmap rendered __ | H3 over-cap __ | H4 emp→HR notif __
Case IDs: intake=____ services=____  MATCH? __
Known-open confirmed: F12-R currency __ | over-cap resolution __ | country autocomplete __
Regressions (were fixed, now broken): ____
New findings: ____
Verdict: ____
```

**Diff rules vs RUN 002:** BLOCKED → PASS = the gating fix shipped. PASS → FAIL = genuine regression, file immediately. Known-open still failing = expected; confirm, don't re-file.

---

## 6. What gates the headline assertion

B16–B17 and C3–C4 are unreachable until **one** fix ships: **policy resolution must run for `is_test` test-drive cases.** Evidence: **0 of 31** test-drive cases resolved vs **2 of 2** real cases; the seed already holds `host_housing_cap` (5500/3800/2400 EUR) and the service→benefit bridge already exists. Nothing in this script can bypass it — hence **BLOCKED**, not FAIL.

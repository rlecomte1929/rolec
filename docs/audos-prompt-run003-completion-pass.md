# RUN 003 — Completion Pass (close out the campaign)

**Date:** 2026-07-20 · **Target:** `relopass.com` · **Deployed head:** `main @ 518bf11c`
**Executor:** Audos — browser, black-box · DB confirmation routed to Cowork
**Campaign:** `qa-run003c` · **Corridor:** `FR_NO` (pinned) · **Format:** RUN 003 conventions
**Purpose:** finish the three parts of RUN 003 that were never executed. **RUN 004-S is cancelled — do not run it.**

---

## 0. Scope

### What is left, and why it matters

| # | Item | Status |
|---|---|---|
| **1** | **Completion + survey flow** (RUN 003 Segment D, D1–D5) | **Never run.** Fully deployed. |
| **2** | **A16 — policy publish (F7/F6)** | Contested: reported broken by Audos, recorded fixed by AIQ-1615/1616, **never tested by anyone**. |
| **3** | **B7a — Continue button behind the legal footer (R2-07)** | Reported in RUN 002, not reproduced, unsettled. |

**Item 1 is the priority.** It is the campaign's measurement instrument — `POST /survey` (test_drive.py:536), `POST /complete` (:802), `POST /event` (:713) are all live on `main` and none has been walked end to end. It captures the segment question, the testimonial with quote consent, pilot interest, and the referral that creates a `prospect_candidates` row. If it is broken, the INSEAD cohort runs to completion and produces **no usable data**, and that is only discovered afterwards.

### Explicitly OUT of scope — do not attempt

These are gated on code that is **not deployed** (`3f9ed63a`, `121403c8`, `5f3baf0e` are all branch-only). Attempting them manufactures false failures:

- ❌ Over-cap → Policy Exception → HR notification (RUN 003 B16/B17, C3/C4)
- ❌ Policy resolution coverage
- ❌ Service→benefit taxonomy behaviour
- ❌ Outbox recipient guard
- ❌ **Do NOT set `OUTBOX_DISPATCH_CRON_ENABLED`**

---

## 1. GOALS

**G1 — Prove the campaign can actually collect data.** A tester completes both personas, marks the test complete, submits the survey, and every artifact lands: session marked complete, survey response, funnel events, testimonial, pilot-interest flag, referral row.

**G2 — Settle A16 and B7a with evidence**, so two contested findings stop consuming review cycles.

**G3 — Confirm the survey degrades gracefully.** Testers will double-click, leave optional fields blank, mis-type emails, and abandon. None of that may lose a response or crash.

**G4 — Close RUN 003.** After this pass, every RUN 003 assertion is PASS, FAIL, or explicitly BLOCKED-pending-deploy. No unknowns.

---

## 2. SPEC — global rules

1. **Campaign:** `?campaign=qa-run003c` on every URL. **Never** the plain link — it defaults to `insead-2026`, live cohort data, purged twice already.
2. **Corridor:** `&corridor=FR_NO`, pinned.
3. **Fresh session per segment**, ≤40 actions. Approaching the cap → stop and report partial. Never fail a run on budget.
4. **Carry credentials in the run log** — a fresh context loses them, and a lost password already killed one run.
5. **Never re-provision mid-segment.**
6. **UI-observable assertions only.** DB questions go to Cowork.
7. **Change nothing** — no approvals, no supplier edits, no variables, no commits.
8. Screenshot every assertion as `RUN003C-<step>`. One retry max per step.
9. Report every `qa-run003c` artifact for purging.

### 2.1 Survival rules (these ended prior runs)

- **S1 — Never type into a pre-filled country field.** On intake Step 2, `Nationality` pre-fills and `Passport country` auto-populates on focus. Typing **appends** → "FranceFranc" → permanent "No match"; backspace and Cmd+A do not clear it. **Recovery: reload the page** — auto-save restores the clean value.
- **S2 — Sign-in may need a ref-click.** Click by element reference, or focus a field and press Enter.
- **S3 — Decline the PostHog consent banner first.** It overlays the page bottom and blocks clicks; may reappear after a session change.
- **S4 — Already-signed-in guard:** click "Sign out and use my test account".
- **S5 — Native `<select>`** may ignore clicks; set the value or use keyboard + Enter.

### 2.2 Run log

```
RUN 003-C | date ____ | campaign qa-run003c | corridor FR_NO | main @ 518bf11c
HR_EMAIL ____ HR_PW ____ | EMP_EMAIL ____ EMP_PW ____
SESSION_LABEL ____ | INTAKE_CASE_ID ____
Seg 1 __ | Seg 2 __ | Seg 3 __
```

---

## 3. PLAN

### SEGMENT 1 — Journey to the completion CTA *(≤40 actions)*

The completion CTA appears once both personas are reachable, so this segment necessarily walks the journey. **A16 and B7a are checked inline** — no separate segment needed.

| # | Action | Expected | Verdict |
|---|---|---|---|
| 1.1 | `https://relopass.com/test-drive?campaign=qa-run003c&corridor=FR_NO`; decline banner (S3); first name `RunC` | Credentials issued; page reads **Paris → Oslo** | FAIL if corridor differs |
| 1.2 | **Do the three videos play?** Click each of the Start / HR / Employee clips | Each plays | Record if any is missing or broken — they are campaign assets |
| 1.3 | Capture both credential pairs **before navigating away** | Recorded | — |
| 1.4 | Sign in as HR (S2/S4) | `/hr/welcome` | — |
| 1.5 | **⭐ A16 — POLICY PUBLISH (contested).** Open Policy / Benefits. Publish **once**, via a single path. Reload. | One clear publish · **no stuck "Publishing…" spinner** · no 409 · Builder and Published tab **agree** | **This settles F7/F6. Record the exact behaviour and screenshot the button state after success.** |
| 1.6 | Create case → assign to employee, seniority **Manager** | "Assignment created" + "Open case →" | FAIL if silent |
| 1.7 | Record `INTAKE_CASE_ID`; send an HR inbox message on the case | Sent | — |
| 1.8 | Fresh context → sign in as employee | `/employee/welcome` | — |
| 1.9 | Intake Step 1 — target date ~60 days out | Advances | — |
| 1.10 | Step 2 — fill **Full name + Passport expiry ONLY**. **Do not type into Nationality / Passport country** (S1) | Advances | Reload on "No match" |
| 1.11 | Step 3 — continue solo | Advances | — |
| 1.12 | Step 4 — job title, contract start, salary band, office address `Karl Johans gate 1, Oslo`, work pattern, assignment type | Address shows "Verified" + commute map | — |
| 1.13 | **⭐ B7a — CONTINUE BUTTON (contested).** Before scrolling: is **Continue** reachable by normal scroll, or obscured by the fixed legal footer? | Reachable without PageDown | **Record precisely: visible / needs PageDown / unreachable. Screenshot. This settles R2-07.** |
| 1.14 | Step 5 — tick the data-use checkbox; leave the optional AI-improvement consent unticked; **Generate my roadmap** | Roadmap renders **in-session** | FAIL if the "2 working days" holding state appears |
| 1.15 | Open Services briefly; confirm the case id matches `INTAKE_CASE_ID` | Match | FAIL on mismatch |
| 1.16 | **Locate the "I've completed my test" CTA** | Present and clickable | **FAIL if it never appears — that alone blocks all campaign measurement** |

**Do not click complete yet.** Segment 2 starts there.

---

### SEGMENT 2 — Completion + survey ⭐ *the never-tested path*

| # | Action | Expected | Verdict |
|---|---|---|---|
| 2.1 | Click **I've completed my test** | Routes to the survey | **FAIL if it dead-ends or errors** |
| 2.2 | Lead-in: name `Run C Tester`; email `runc@probe.test`; company/role `QA / Tester`; sector `energy` | Accepted | — |
| 2.3 | **Segment question** — "Do you work in HR, mobility or relocation?" → **Yes** | Accepted | Should record `prospect` |
| 2.4 | Q1 Overall → **4** | Accepted | — |
| 2.5 | Q2 Friction → `Country field appended text and could not be cleared.` | Accepted | — |
| 2.6 | Q3 Problem fit → **Yes, clearly** + one line | Accepted | — |
| 2.7 | Q4 One change → `Show the policy cap earlier.` | Accepted | — |
| 2.8 | **Q5 Testimonial** → `ReloPass turns a messy relocation into one visible case.` **and tick the quote-consent box** | Both accepted | Consent must be capturable |
| 2.9 | **Q6 Pilot interest** → **Yes — let's talk** + optional note | Accepted | — |
| 2.10 | **Q7 Referral** → name `QA Referral`, company `QA Corp`, contact `referral@probe.test`, tick "you can mention I referred them" | Accepted | Should create a `prospect_candidates` row |
| 2.11 | **Submit** | Thank-you state renders | **FAIL if submission errors or hangs** |
| 2.12 | Record the thank-you copy and whether any `mailto:` opens | Note behaviour | TD-12 expects a client-side mailto, not a platform send |
| 2.13 | Reload the survey URL after submitting | Sensible state — not a blank form inviting a duplicate | Record |

---

### SEGMENT 3 — Survey edge cases *(short, independent, fresh contexts)*

| ID | Case | Expected |
|---|---|---|
| E5 | Click **I've completed my test** twice rapidly | No duplicate session-complete, no error |
| E6 | Open the survey URL **with no session** | Graceful handling; no crash |
| E7 | Submit with **only** the segment question answered, all optional fields blank | Succeeds |
| E8 | Answer the segment question **"No"** | Stored as `internal`, not prospect |
| E9 | Enter an invalid email (`notanemail`) in the lead-in | Validated / rejected, not silently accepted |
| E10 | Testimonial containing `<script>alert(1)</script>` | Stored and rendered **escaped**; no execution |
| E1 | Provision the same first name **3×** on `qa-run003c` | 3 distinct sessions, unique suffixes, no collision |
| E2 | Provision **without** `&corridor=` | Auto-assigned from the five; Tier-A favoured |
| E3 | Provision with `?corridor=INVALID` | Safe fallback; **no 500** |
| E14 | Confirm **zero** rows created under `insead-2026` | Real campaign stays clean |

---

## 4. METRICS

| Metric | Baseline | Target |
|---|---|---|
| Tester reaches the completion CTA | **unmeasured** | reached |
| Survey submits successfully | **never tested** | 1/1 |
| A16 policy publish clean (no spinner / no 409) | **contested** | settled with evidence |
| B7a Continue reachable without PageDown | **contested** | settled with evidence |
| Survey edge cases passing | unknown | 10/10, or defects listed |
| Videos playing | unverified | 3/3 |
| Rows under `insead-2026` | 0 | **0** |

---

## 5. VERIFICATION

Screenshot every assertion. Segments 1.5 and 1.13 must each carry a screenshot — they are settling contested findings and a description is not sufficient.

**Database confirmation — routed to Cowork, not Audos.** Report the session label and Cowork will verify that the survey actually persisted:

- `test_sessions` — is the row `status` complete with `completed_at` set, and is `tester_segment` populated (currently NULL for every dropout)?
- `survey_responses` — did the row land, with the testimonial and the quote-consent flag?
- `funnel_events` — did `POST /event` fire, and at which stages?
- `prospect_candidates` — did Q7 create a row tagged `referred_by`?
- `insead-2026` — row count unchanged?

**This is the part that matters most.** A thank-you screen that renders while nothing persists is the worst possible outcome, because the campaign would appear to work.

**Escalate immediately and stop** on: a survey submit that errors, a completion CTA that never appears, or any `insead-2026` write.

---

## 6. Report

```
RUN 003-C | date ____ | main @ 518bf11c | campaign qa-run003c | corridor FR_NO
SESSION_LABEL ____ | survey email runc@probe.test

SEG 1 — JOURNEY
  Videos play (3/3)? ____
  ⭐ A16 policy publish: clean / spinner hangs / 409 ____   [screenshot ____]
  ⭐ B7a Continue: visible / needs PageDown / unreachable ____   [screenshot ____]
  Roadmap in-session? ____   Case id match? ____
  Completion CTA present? ____

SEG 2 — COMPLETION + SURVEY
  Complete → survey routed? ____
  All 7 questions accepted? ____   Quote consent ticked? ____
  Submit succeeded? ____   Thank-you rendered? ____   mailto behaviour: ____
  Post-submit reload state: ____

SEG 3 — EDGE CASES
  E5 __ E6 __ E7 __ E8 __ E9 __ E10 __ E1 __ E2 __ E3 __ E14 __
  Failures: ____

FOR COWORK TO VERIFY IN DB
  Session label: ____   Survey email: ____   Referral email: referral@probe.test

ARTIFACTS TO PURGE: ____
🔴 CRITICAL: ____
```

**Sequence:** Segment 1 → 2 → 3. Start only after Track B (`qa-p0-1`) finishes — do not interleave campaigns. **RUN 004-S is cancelled.**

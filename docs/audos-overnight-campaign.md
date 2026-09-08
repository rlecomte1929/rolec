# Audos — overnight test campaign (unattended)

**Date:** 2026-07-20 · **Target:** `relopass.com` · **Deployed head:** `main @ 518bf11c`
**Mode:** unattended. Romain is asleep. **Nothing here requires a decision, an approval, or a config change.**
**Campaigns:** `qa-night-01` … `qa-night-14` (one per test) · **Never `insead-2026`.**

---

## 0. Why this works when the full journey does not

Four consecutive runs died trying to walk provision → HR → intake → roadmap → survey in one session. That path is 60–80 actions against a ~50 ceiling.

**Every test below is independent and fits in ≤12 actions.** If one fails or blocks, the rest are unaffected. Run as many as you can; partial completion is a good outcome. Do **not** attempt the full journey — it needs the staged-provisioning fixture (filed as P1) which does not exist yet.

**Expected total:** ~14 short sessions. If you run out of budget or hit repeated failures, stop and report what you completed.

---

## 1. Safety rules — non-negotiable while unattended

- **Never use `insead-2026`.** One campaign per test: `qa-night-01`…`qa-night-14`.
- **Approve nothing.** No supplier records, no policy publishes beyond what a test explicitly says, no task approvals.
- **Delete nothing. Change no configuration.** Do **not** set `OUTBOX_DISPATCH_CRON_ENABLED` or any repo variable.
- **Send no email.** If any test would trigger an outbound send, stop that test and note it.
- **Do not exploit anything.** T12 checks that a script tag is *escaped* — record what renders; never attempt to run injected code anywhere else.
- **If you find a 🔴 critical** (case PII on a public page, cross-tenant data access, a real email sent) — **stop the whole campaign immediately** and put it at the top of the report.
- **Record every artifact created** (campaign + session label) so it can be purged in the morning.
- Screenshot each verdict. `BLOCKED` and `NOT-RUN` are valid answers.

### Survival rules
- **S1 — never type into a country picker.** Known defect: typing appends to an injected autocomplete ("France"→"Franceance"). Use the dropdown list and click the option. If a field shows "No match", reload the page.
- **S2 — click custom controls by coordinate, not by ref.** Ref-clicks silently fail on the segment toggle, consent checkbox and pilot-interest buttons.
- **S3 — decline the analytics banner first.** It overlays the page bottom and blocks clicks. It reappears after navigation.
- **S4 — capture credentials before navigating away.** Non-ASCII password → record it and stop that test; that is itself a finding.
- **S5 — session does not survive navigation** (known P1). Do not navigate away mid-test and expect to return.

---

## 2. Batch A — provisioning edge cases (~30 actions total)

| ID | Test | Steps | Expected | Record |
|---|---|---|---|---|
| **T1** | Duplicate name uniqueness | Provision `NightA` **3×** on `?campaign=qa-night-01&corridor=FR_NO` | 3 distinct sessions, unique email suffixes, no collision or error | The 3 suffixes issued |
| **T2** | No corridor supplied | Provision on `?campaign=qa-night-02` (omit `&corridor=`) | A corridor is auto-assigned from the five; page states it clearly | Which corridor was assigned |
| **T3** | Invalid corridor | Provision on `?campaign=qa-night-03&corridor=INVALID` | Safe fallback to auto-assign. **No 500, no blank page** | What it fell back to |
| **T4** | Tier-B corridor coverage | Provision on `?campaign=qa-night-04&corridor=NL_SG` | Early-coverage warning shown ("this corridor is in early coverage") | Exact warning text, or NONE |
| **T5** | Already-signed-in guard | With a live test session, load `/test-drive?campaign=qa-night-05&corridor=FR_NO` | "You're already signed in as … Sign out first" + a sign-out button | Present / absent |

---

## 3. Batch B — survey edge cases (~50 actions total)

For each: provision fresh, click **I've completed my test** in the *same page load* (S5), then exercise the case.

| ID | Test | Action | Expected | Record |
|---|---|---|---|---|
| **T6** | Minimum viable submit | Answer **only** the required segment question. Leave every optional field blank. Submit | Succeeds; thank-you renders | Pass/fail |
| **T7** | Segment "No" branch | Answer segment **No**; name `NightNo`; email `nightno@probe.test`. Submit | Succeeds | Pass/fail — Cowork will verify it stored `internal`, not `prospect` |
| **T8** | Invalid email | Enter `notanemail` in the lead-in email. Submit | Validated and rejected, **or** accepted — either is a finding | Which happened. *(A row from 2026-07-15 contains `not-an-email`, so validation may be absent)* |
| **T9** | Escaping check | Testimonial = `<script>alert(1)</script>`. Name `NightXSS`, email `nightxss@probe.test`. Submit | Stored and rendered **escaped**. No dialog, no execution | What rendered. 🔴 if a dialog appears |
| **T10** | Double submit | Click Submit twice rapidly | One response, no duplicate, no error state | What happened |
| **T11** | Double completion | Click **I've completed my test** twice rapidly | No duplicate session-complete, no error | What happened |

---

## 4. Batch C — public surface, no auth (~20 actions, cheap)

| ID | Test | Expected | Record |
|---|---|---|---|
| **T12** | Videos serve | Load `/test-drive/hr.mp4` and `/test-drive/employee.mp4` directly | A native video player renders (not the ReloPass page, not an error) | Pass/fail each. *(`start.mp4` already verified serving — a previous "404" was a cancelled-request artifact, not a defect)* |
| **T13** | Compliance copy guard | Search `/`, `/platform`, `/why`, `/how-it-works` for: "EU AI Act Ready", "compliant", "certified", "high-risk" | **None present.** Any occurrence is a 🔴 legal issue | Exact string + page if found |
| **T14** | Legal pages reachable | `/privacy` and `/security` load | Both render | Pass/fail |

---

## 5. Batch D — route guards (~15 actions) ⭐ highest security value

Sign in as a **test-drive employee** (provision on `qa-night-14`, capture credentials per S4), then attempt each URL directly.

| ID | URL | Expected | Record |
|---|---|---|---|
| **T15** | `/admin` | Blocked or redirected. Employee must not see admin CMS | What rendered |
| **T16** | `/admin/vetting-queue` | Blocked | What rendered |
| **T17** | `/hr/policy` | Blocked — an employee must not read HR policy config | What rendered |
| **T18** | `/hr/welcome` | Blocked | What rendered |

**Any of these rendering real content for an employee is 🔴 — stop the campaign and report it first.** Record the exact URL and a screenshot.

---

## 6. Report format

```
OVERNIGHT CAMPAIGN — 2026-07-20/21
Completed: __/18    Blocked: __    Not run: __

🔴 CRITICAL (if any, listed first): ____

BATCH A — PROVISIONING
  T1 duplicate names (3 suffixes): ____
  T2 no corridor -> assigned: ____
  T3 invalid corridor -> ____   (500? YES/NO)
  T4 NL_SG early-coverage warning: ____
  T5 already-signed-in guard: ____

BATCH B — SURVEY (all submitted via in-page CTA, session intact)
  T6 minimum submit: ____
  T7 segment=No: ____        (session label for Cowork: ____)
  T8 invalid email: rejected / accepted ____
  T9 escaping: ____          🔴 if dialog appeared
  T10 double submit: ____
  T11 double completion: ____

BATCH C — PUBLIC
  T12 hr.mp4 ____  employee.mp4 ____
  T13 compliance strings found: ____ (expect NONE)
  T14 /privacy ____  /security ____

BATCH D — ROUTE GUARDS  ⭐
  T15 /admin ____   T16 /admin/vetting-queue ____
  T17 /hr/policy ____   T18 /hr/welcome ____

FOR COWORK (DB verification in the morning)
  Campaigns used: qa-night-01 … qa-night-__
  Session labels + survey emails: ____
  Verify: T7 stored tester_segment='internal'; T9 testimonial stored escaped;
          T8 whether the invalid email persisted; T10/T11 no duplicate rows;
          all rows carry the correct qa-night-* campaign, not insead-2026.

ARTIFACTS TO PURGE: ____
```

---

## 7. What NOT to attempt overnight

Full intake journey · roadmap · Services · supplier exposure · RFQ loop · over-cap chain · anything needing a code change, a migration, an approval or a deploy. All are either blocked on undeployed code or need the staged-provisioning fixture. **Attempting them repeats the pattern that killed four runs.**

If you finish everything and have budget left: **stop.** A clean partial report is worth more than an extra improvised test.

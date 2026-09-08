# Audos — next session + the harness change that unblocks all future runs

**Date:** 2026-07-20 · **Deployed head:** `main @ 518bf11c`
**Read §0 first.** It changes what to run and why.

---

## 0. Why four runs in a row have died the same way

RunC (accented char in a password), RunD (mis-transcribed password), RunE (budget at 38/50), and the Cowork run (never reached the journey end) all failed for one structural reason:

**The full journey does not fit the budget.** Provision → HR setup → assign → employee login → 5-step intake → roadmap → Services → completion → survey is **60–80 actions** against a ~50-action ceiling. Every run spends its whole allowance *constructing state* and dies before reaching the assertion. The country-autocomplete defect burns another 5–10 actions per run.

**Stop trying to run the whole journey. It cannot succeed as designed.**

---

## 1. Findings already established — do NOT re-derive

| Finding | Status |
|---|---|
| Survey files to `campaign='insead-2026'` when session context is absent | ✅ Confirmed (Cowork, DB) — **P0 filed** |
| Test-drive session lost on navigation; completion CTA + survey link disappear | ✅ Confirmed (Cowork) — **P1 filed** |
| Country picker autocomplete corruption, mechanism root-caused | ✅ Confirmed 3× (Audos) — **P1 filed** |
| Policy publish takes 20–40s then succeeds (not a hang) | ✅ Confirmed (Cowork) — **P2 filed** |
| Policy tabs contradict each other (F6) | ✅ Confirmed (Cowork) — **P2 filed** |
| Survey validation error unnamed + misplaced | ✅ Confirmed (Cowork) — **P2 filed** |
| B7a Continue button reachable | ✅ PASS (Audos) — closed |
| Intake Step 1 + required-field gating | ✅ PASS (Audos) — closed |
| Employee login works with ASCII credentials | ✅ PASS (Audos) — closed |

**The survey has already been submitted and verified end-to-end by Cowork.** Do not re-run the direct-URL survey path — it will only reproduce the known P0.

---

## 2. This session — SHORT and targeted (≈15 actions, not 50)

### Task A — Confirm the session-persistence bug (~8 actions) ⭐ run first

This gates everything else. If a tester cannot return to the completion CTA, the campaign collects nothing regardless of the survey fix.

1. Provision at `https://relopass.com/test-drive?campaign=qa-run003d&corridor=FR_NO`. Decline the analytics banner. First name `RunF`.
2. **Capture both credential pairs before navigating away.** Use ASCII-only — if a generated password contains a non-ASCII character, record it and stop; that is a bug in itself.
3. Confirm the page shows: credentials · **I've completed my test** · **Take the survey**.
4. Navigate to `https://relopass.com/hr/welcome`.
5. Navigate **back** to the same test-drive URL.
6. Record which of the three are still present.

**Expected (bug confirmed):** all three gone, page reset to the empty start form.
**If they persist:** the bug is conditional — record exactly what differs from the Cowork run.

### Task B — Completion via the in-page CTA, session intact (~7 actions)

**This is the complement to what Cowork already tested, and the only version still unknown.** Cowork submitted the survey with *no* session context and found it filed to `insead-2026`. Nobody has tested the **happy path**.

- **Do not navigate away.** In the same page load as provisioning, click **I've completed my test**.
- Complete the survey minimally: answer the required segment question (**click by coordinate — a ref-click silently fails on these controls**), name `Run F Tester`, email `runf@probe.test`. Skip everything else.
- Submit. Record whether the thank-you renders.
- **Report the session label to Cowork**, who will verify whether `session_id`, `campaign` and `corridor_id` persisted correctly.

If Task A shows the CTA disappears, Task B may be impossible without keeping the page loaded — **that itself is the finding.** Record it and stop. **Do not route around it via the direct `/test-drive/survey` URL** — that reproduces the known P0 and teaches us nothing.

### Do not attempt this session
Full intake · roadmap · Services · supplier exposure · edge cases. All need the harness in §3 first.

---

## 3. The harness change — highest-leverage item on the testing side

**Ask:** a QA-only fixture that provisions a session **already at a named stage**, so a test starts one action from its assertion instead of sixty.

```
POST /api/test-drive/provision?stage=<stage>&campaign=<c>&corridor=<c>

stage=credentials     current behaviour (default)
stage=case_created    + company, published policy, case created and assigned
stage=intake_complete + intake submitted (bypasses the country-picker trap)
stage=roadmap_ready   + roadmap generated, Services reachable
```

**Constraints:** gated behind `RELOPASS_TEST_DRIVE_ENABLED`, rejected unless the campaign matches `qa-*`, never reachable for `insead-2026` or any real company, and it must reuse the real code paths rather than inserting rows directly — otherwise it tests a fiction.

**What this unlocks immediately:**

| Test | Today | With fixture |
|---|---|---|
| Supplier exposure (do the 9 Norway suppliers render?) | ~45 actions, never completed | **~6** |
| Completion + survey, session intact | ~60 actions | **~8** |
| Over-cap chain (once the fix deploys) | impossible | **~10** |
| RFQ loop end to end | ~50 actions, never attempted | **~15** |
| Any single edge case | full journey each | **~5** |

Every run that has died this week would have finished. **Recommend filing this as P1 on the AI Work Queue** — Layer: API, Task Type: Backend Implementation, 🟡 Yellow.

---

## 4. What is still genuinely untested

| Surface | State |
|---|---|
| Employee roadmap → Services, end to end | **Never completed by anyone** |
| Completion via in-page CTA with session intact | Task B above |
| Do the 9 unvetted Norway suppliers render to a customer? | **Never checked** — they are `approved` with `vetted_by=NULL` and no code filters on `verified` |
| RFQ loop (3 routers, 4 pages, 6 migrations) | **Never QA'd** |
| Cross-persona notifications | Verified 2026-07-19, not since |
| Edge cases E1–E14 | **None run** |
| Over-cap → Policy Exception → HR notification | Blocked on undeployed `3f9ed63a` |

---

## 5. The pattern worth naming

Nearly every defect found this week is the same class: **the system asserts a success it never verified.**

- Survey renders "Thanks — that's genuinely useful" while writing to the wrong campaign
- Suppliers carry `platform_vetting_status='approved'` with `vetted_by = NULL`
- Policy reports "published" on one tab and "no policy" on the next
- Policy resolution appeared healthy but never fired for test cases
- The test-drive policy seed swallowed its own exceptions
- Tasks were reported "finished" that made no changes

The generic fix is cheap: **after any state-changing operation, read the state back and surface any discrepancy.** Applied to the survey submit, the supplier import, and the policy publish, it would have caught four of the seven filed tickets before a human ever looked.

It also explains why "it looked fine" has been unreliable evidence all week — and why every UI assertion in future runs must be paired with a data assertion. Audos drives the browser and reports the session label; Cowork verifies persistence. Neither half is sufficient alone.

---

## 6. Rules

- **≤15 actions this session.** Stop and report rather than pushing on.
- **Capture credentials before navigating away.** Non-ASCII password → record and stop.
- **Click custom controls by coordinate, never by ref** — ref-clicks silently fail on the segment toggle, the consent checkbox and the pilot-interest buttons.
- **Never use `insead-2026`.** Use `qa-run003d`. Report every artifact for purging.
- **Do not route around a blocker.** A blocked path is a finding.
- Report: what was run · what was observed · session label for Cowork · what is blocked. `NONE` is a valid answer.

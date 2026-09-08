# CARD SMOKE-1B — RFQ submit through survey

**Paste this whole message to Audos as text. Do not attach it — the last three attachments failed to fetch.**

---

Yes — pick it up now. This is the fresh-session run that finishes steps 9–12.

Your `qa-smoke2` result was the breakthrough: **Movers (5)** where Q1-C had `Movers (0)`, plus NOK currency, Paris origin, and a shortlist that builds. Two blockers cleared in one run.

Three quick adjudications before you start:

- **The "EU AI Act Art. 14" label is fine.** The compliance guard bans claims of *status* ("ready", "compliant", "certified"). It explicitly permits describing what a control does — "human review on every AI recommendation, the decision/AI-output audit log". That string describes a control. CI passes with it. **No action.** Raising it was still right; the check is cheap.
- **The console 403 is real** — filed P2. It's `POST /api/ai/decisions` via `createAIDecision`. The shortlist updated but the audit write failed, so the UI claimed a record it may not have written.
- **Vendor seeding is intermittent** — filed P1. Only about 5 of 8 post-fix companies get selections. Yours worked; roughly a third don't.

---

## THE CARD

**Campaign:** `qa-smoke3` · **Corridor:** `FR_NO` · **First name:** `Smoke3` · **Budget:** ~40 · **Fresh session.**

**Goal:** submit an RFQ end to end and complete the survey. Nobody has ever done either on this platform.

### Steps

**1.** Go to `https://relopass.com/test-drive?campaign=qa-smoke3&corridor=FR_NO`. Decline the analytics banner (it overlays the page bottom and blocks clicks). Confirm the page reads **Paris → Oslo**.

**2.** Enter first name `Smoke3` and click **Start the test**.
> **Type by keyboard.** Setting the field programmatically does not fire the React handler — provisioning silently fails and no session is created. Click the field, then type.

**3.** Capture both credential pairs immediately, before navigating anywhere.
> If the HR password contains `O`, `I`, `l`, `0` or `1` and sign-in 401s, **re-provision once** rather than concluding the account is broken. That is what last run's 401 turned out to be. Note whether the password contained any of those glyphs.

**4.** Sign in as **HR** at `https://relopass.com/auth?mode=login`.
> ⭐ **Record which landing you get:** *"Set up your company workspace"* (setup-first, 3 numbered steps) or *"Open your first relocation case"* (case-first). Cowork saw the setup-first variant today and suspects a TD-BUG-4 regression. Your observation settles it either way.

**5.** Create a case, assign it to the employee account. **Record both ids, labelled** — the id in the URL (assignment) and any separate case id shown.

**6.** Sign in as the **EMPLOYEE** in a fresh context. Open **Services**. **Do not complete intake.** Select **Movers** → Preferences → **Get recommendations**.
> **If Movers shows (0), stop and report.** That is the seeding intermittency and the run cannot continue. Not your failure.

**7.** ⭐ Add the **TOP-scored provider** to the package — whichever ranks first, likely AGS Movers Norway.
> Deliberately pick the top match this time. It should **not** trigger the justification gate. That isolates whether the 403 fires only on override.
> **Record:** did the justification box appear? Did a console 403 fire?

**8.** Continue to **Review & budget**. Confirm the currency reads **NOK**.

**9.** ⭐ Click **Request quotes** → `/employee/case/{id}/services/rfq/new`. Complete the minimum required fields. **Submit.**
> **This would be the first RFQ ever submitted through this product. Capture everything** — confirmation text, RFQ reference, any error, anything that blocked.

**10.** ⭐ Record whether a **supplier magic link** is visible anywhere in the UI — a copy-link control, an invite list, a dispatch log, a recipient list. **If links are only ever emailed and never shown, say so explicitly.** Cards Q2 and Q3 depend entirely on this answer.

**11.** Return to `https://relopass.com/test-drive?campaign=qa-smoke3&corridor=FR_NO`. Confirm the session survived navigation — credentials, completion CTA and survey link all present.

**12.** Click **I've completed my test** → complete the survey (segment question **by coordinate click**, name `Smoke3`, email `smoke3@probe.test`, skip optionals) → **Submit**. Record the thank-you state.

### Rules

Click custom controls by coordinate, never by element ref — ref-clicks silently fail on the segment toggle, consent checkbox and pilot buttons · type by keyboard, never set fields programmatically · country fields: use the dropdown, never type · never use `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding, not something to route around · stop cleanly before the budget cap rather than dying mid-action.

### Report block — use verbatim

```
CARD: SMOKE-1B         DATE: ____
CAMPAIGN: qa-smoke3    CORRIDOR: FR_NO
SESSION LABEL: ____   ASSIGNMENT ID: ____   CASE ID: ____
BUDGET USED: __/50

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

  3.  Password had ambiguous glyphs? ____   Sign-in worked first try? ____
  4.  HR landing: "Set up your company workspace" / "Open your first relocation case" ____
  6.  Movers count at Recommendations: ____   (0 = stop and report)
  7.  Top provider added — justification gate appeared? YES / NO
      Console 403 on confirm? YES / NO
  8.  Currency at Review & budget: ____
  9. ⭐ RFQ SUBMITTED? ____   Reference: ____   Errors: ____
 10. ⭐ Supplier magic link visible in UI? yes (where: ____) / no — email only
 11.  Session survived navigation? ____
 12.  Survey submitted, thank-you rendered? ____

🔴 CRITICAL (report first, stop the run): ____

FOR COWORK — DB VERIFICATION:
  rfqs / rfq_items / rfq_recipients — expect the write HERE, not rfq_requests
  survey_responses — expect campaign='qa-smoke3', non-null session_id + corridor_id
  company_vendor_selections — confirm seeded for this company
  ai_decisions — confirm whether step 7 wrote a row
  Identifiers: ____

ARTIFACTS TO PURGE (list ALL): ____

BLOCKED BY: ____
```

**After SMOKE-1B, hold.** Cowork runs the database half and makes the cohort go/no-go call. Do not start J1/J2 — they need the staged-provisioning fixture, which does not exist yet.

---

## Why this run matters

If step 9 succeeds, the cohort path is verified from provision to survey and you will have completed the first end-to-end RFQ in the product's history. If step 10 shows a magic link, cards Q2 and Q3 unblock immediately.

Two things about how you have been working that are worth keeping: you stopped at 45/50 rather than dying mid-action, and you told me the "read from the DOM" instruction was unexecutable in your harness instead of silently failing at it. Both are why this batch is moving now.

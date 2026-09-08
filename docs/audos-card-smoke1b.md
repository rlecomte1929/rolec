# Audos — SMOKE-1 breakthrough confirmed · CARD SMOKE-1B (steps 9–12)

---

## 1. Your run broke the deadlock

**Movers (5), not (0).** AGS Movers Norway · Crown Relocations (Norway) · Déménagements Delahaye · Santa Fe Relocation · SIRVA Worldwide — with scores, NOK pricing and "Preferred by your company" badges.

Against Q1-C's `Movers (0)` this morning, that is the vendor-seeding fix working and the entire RFQ half of the product becoming reachable for the first time.

You also re-confirmed three fixes in passing: **NOK** currency (F12), **Paris** origin (AIQ-1649), and HR sign-in.

**And you settled the 401.** Cowork independently provisioned a session and signed in first attempt, so last run's failure was glyph ambiguity on that one password — not a broken auth system. Your instinct to stop rather than route around it was right; a workaround would have buried the real cause.

## 2. On the credential workaround — you were right to push back

You said your harness reads via screenshots and has no DOM-query primitive, so "read from the DOM" wasn't executable. **Correct, and thank you for saying so rather than pretending.**

Your substitute reasoning was also right: a fresh session generates a fresh password, which may simply not contain ambiguous glyphs — and that is exactly what happened. **Keep doing that.** When an instruction doesn't fit your tooling, say so and propose the nearest workable thing.

**Practical rule for future runs:** if a password contains `O`, `I`, `l`, `0` or `1`, expect a possible 401 on retype. Re-provision once and use the new credential rather than assuming the account is broken. The generator is being fixed separately.

## 3. Your two flags, adjudicated

**⚠️ "Logged for human oversight audit · EU AI Act Art. 14" — FALSE POSITIVE, but well raised.**
The compliance guard bans claims of EU AI Act *status* ("ready", "compliant", "certified"). It explicitly **permits** describing what the controls do — *"human review on every AI recommendation, the decision/AI-output audit log."* That string describes a control and cites the Article as its reason. CI passes with it present. No action. Raising it was still correct — that check is cheap and the downside of missing a real one is large.

**🐞 Console 403 on Confirm pick — REAL, filed P2.**
Traced to `POST /api/ai/decisions` via `createAIDecision`. The shortlist updated but the audit write failed — so the UI claimed the reason was logged when it may not have been. Filed, with the note that if the 403 turns out to be a correct authorisation boundary, the fix is to change the copy, not widen the boundary.

**Also filed P1:** vendor seeding is intermittent — only **5 of 8** post-fix companies get selections (63%). When it fires it works, as your run proves. About a third of testers will still see an empty marketplace.

---

## 4. CARD SMOKE-1B — steps 9 through 12

**Campaign:** `qa-smoke3` · **Corridor:** `FR_NO` · **Budget:** ~40 · **Fresh session.**

You stopped cleanly at 45/50 rather than dying mid-submission. This card picks up where that left off, from a fresh provision.

**Goal:** submit an RFQ end to end and complete the survey — the two things nobody has ever done on this platform.

### Steps

1. `https://relopass.com/test-drive?campaign=qa-smoke3&corridor=FR_NO`. Decline the analytics banner. First name `Smoke3`.
   - **Type by keyboard.** `form_input` does not fire the React handler on this form — provisioning silently fails and no session is created.
2. Capture both credential pairs. **If the HR password contains `O`, `I`, `l`, `0` or `1`, note it** — and if sign-in 401s, re-provision once rather than concluding the account is broken.
3. Sign in as **HR** → create case → assign to employee. Record both ids, labelled.
   - **Note which HR landing you get:** *"Set up your company workspace"* (setup-first) or *"Open your first relocation case"* (case-first). Cowork saw the setup-first variant today and suspects a TD-BUG-4 regression — your observation either confirms or clears it.
4. Sign in as **EMPLOYEE**, fresh context → **Services** → select **Movers** → Preferences → **Get recommendations**.
   - Expect `Movers (5)` or similar. **If you get `Movers (0)`, stop and report** — that is the seeding intermittency and the run cannot continue.
5. **Add the TOP-scored provider to the package** (AGS Movers Norway or whichever ranks first).
   - ⭐ Deliberately choose the top match this time — it should **not** trigger the justification gate. That isolates whether the 403 only occurs on override.
6. Continue to **Review & budget**. Confirm currency reads **NOK**.
7. ⭐ **Click Request quotes** → `/employee/case/{id}/services/rfq/new`. Complete the minimum fields. **Submit.**
   - Record: confirmation? RFQ reference? Any error?
   - **This is the first RFQ ever submitted through this product. Capture everything.**
8. ⭐ Record whether a **supplier magic link** is visible anywhere — copy-link control, invite list, dispatch log, recipient list. If links are email-only and never shown, say so explicitly. Q2 depends on this.
9. Return to `/test-drive?campaign=qa-smoke3&corridor=FR_NO`. Confirm the session survived navigation (AIQ-1640) — credentials, completion CTA, survey link present.
10. Click **I've completed my test** → complete the survey (segment question by coordinate click, name `Smoke3`, email `smoke3@probe.test`, skip optionals) → **Submit**. Record the thank-you state.

### Rules

Click custom controls by coordinate, never by ref · type by keyboard, not `form_input` · country fields: use the dropdown · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding.

### Report block

```
CARD: SMOKE-1B         DATE: ____
CAMPAIGN: qa-smoke3    CORRIDOR: FR_NO
SESSION LABEL: ____   ASSIGNMENT ID: ____   CASE ID: ____
BUDGET USED: __/50

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

  2.  HR password contained ambiguous glyphs? ____  Sign-in worked first try? ____
  3.  HR landing: "Set up your company workspace" / "Open your first relocation case" ____
  4.  Movers count at Recommendations: ____   (0 = stop and report)
  5.  Top-scored provider added — justification gate appeared? YES / NO
      Console 403 on confirm? YES / NO
  6.  Currency at Review & budget: ____
  7. ⭐ RFQ SUBMITTED? ____  Reference: ____  Errors: ____
  8. ⭐ Supplier magic link visible in UI? yes (where: ____) / no — email only
  9.  Session survived navigation (AIQ-1640)? ____
 10.  Survey submitted, thank-you rendered? ____

🔴 CRITICAL (report first, stop): ____

FOR COWORK — DB VERIFICATION:
  rfqs / rfq_items / rfq_recipients — expect the write HERE, not rfq_requests
  survey_responses — expect campaign='qa-smoke3', non-null session_id + corridor_id
  company_vendor_selections — confirm seeded for this company
  ai_decisions — confirm whether step 5 wrote a row
  Identifiers: ____

ARTIFACTS TO PURGE (list ALL): ____

BLOCKED BY: ____
```

**After SMOKE-1B, hold.** Cowork runs the DB half and makes the cohort go/no-go call.

---

## 5. What this run is worth

If step 7 succeeds, you will have completed the first end-to-end RFQ in the product's history, and the cohort path will be verified from provision to survey. If step 8 shows a magic link, cards Q2 and Q3 unblock immediately.

Two things worth noting about how you have been working: you stopped at 45/50 rather than dying mid-action, and you told me an instruction was unexecutable instead of silently failing at it. Both of those are why this batch is now moving.

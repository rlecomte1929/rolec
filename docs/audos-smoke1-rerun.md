# Audos — SMOKE-1 resolved · re-run with a workaround

---

## 1. The 401 was a misread — but your caveat was the answer

Cowork provisioned a fresh session and signed in **first attempt**. The accounts are fine: `hr-authchk-ab46@probe.test` exists in `users` with a valid PBKDF2 hash, and authentication succeeded immediately.

**The difference: Cowork took the password from the DOM, not from a screenshot.**

Your caveat — *"I retyped the displayed password; a real tester would use Copy; the harness can't paste"* — was pointing directly at the cause. You just attributed it to the Copy button when it was actually the **read**.

### Why you couldn't catch it

You revealed the password field to verify. But that shows what **you typed**, not what you **should have typed**. You then re-navigated and re-read the panel — and made the same misread a second time, which is exactly what a consistent glyph confusion does. Two consistent observations of the same wrong character look like confirmation.

### The real cause: ambiguous glyphs in generated passwords

| Session | Password | Ambiguous characters |
|---|---|---|
| Yours | `hKLkgRZbqMyW` | **`L`** beside lowercase letters |
| Cowork's | `4wZB8bbOIgKr` | **`O`** (letter o) and **`I`** (letter i) |

`O`/`0`, `I`/`l`/`1` are the classic confusions. Not your error specifically — **the generator should not emit them.** Being filed.

**This is still a real cohort risk.** Most testers will click Copy and be fine. Anyone reading the screen and typing — phone keyboard, second monitor — hits a 401 at step one and abandons before the test begins.

---

## 2. 🔧 Your workaround for every future run

**Never transcribe a credential from a screenshot. Read it from the DOM.**

```
find { query: "HR account password value and its Copy button" }
  → ref_133: generic ""4wZB8bbOIgKr""   ← authoritative, character-exact
  → ref_134: button ""Copy password""
```

Then type that exact string. The `find` and `read_page` tools return the underlying text node, so glyph ambiguity cannot occur. Do the same for the email.

**Add this to your durable notes** — it applies to every provisioned credential from here on, and it would have saved this entire cycle.

---

## 3. ⚠️ What your run indirectly found

While verifying, Cowork hit `/hr/welcome` and found **TD-BUG-4 has regressed.**

It now reads **"Set up your company workspace"** with three numbered setup steps (Configure company → Build policy → Curate providers), and the case entry demoted to *"Ready to open your first case?"* at the bottom.

That is the **pre-fix** behaviour. TD-BUG-4 was fixed specifically to make the landing case-first, because forcing HR through company setup before the case was the biggest friction point in the tester journey. In your RUN 003-C run this morning it correctly read *"Open your first relocation case"* with setup marked *"Optional."*

Something in today's fifteen commits reverted it. Being filed as P1.

**So your blocked run still produced two findings.** Stopping rather than routing around the 401 is what made both discoverable — a workaround would have hidden the glyph problem entirely.

---

## 4. CARD SMOKE-1 — re-run

**Campaign:** `qa-smoke2` · **Corridor:** `FR_NO` · **Budget:** ~35 · **Fresh session.**

Same card as before, with the credential workaround applied.

### Steps

1. `https://relopass.com/test-drive?campaign=qa-smoke2&corridor=FR_NO`. Decline the analytics banner. First name `Smoke2`.
   - **Note:** `form_input` does **not** trigger the React handler on this form — provisioning silently fails and no session is created. **Click the field and type by keyboard.**
2. ⭐ **Capture credentials via `find`, not from a screenshot.** Record the exact DOM strings for both HR and employee email + password.
3. Sign in as **HR**, typing the DOM-read password. If it 401s a second time with a DOM-read value, **that** is a genuine finding — stop and report.
4. Create a case → assign to the employee. **Record both ids, labelled.**
   - ⚠️ Note whether the HR landing shows *"Set up your company workspace"* (the regression) or *"Open your first relocation case"*. Record which, and whether you had to click through setup to reach case creation.
5. Sign in as **EMPLOYEE**, fresh context. Open **Services**. **Do not complete intake.**
6. **Preferences** — confirm: no *"Destination missing"* banner · origin reads **Paris** · **Get recommendations** enabled.
7. ⭐ **Recommendations** — record **every supplier offered by name, per category**, plus the count on each category chip.
   - Watch for: DNB Bank · Nordea Norway · SpareBank1 · Crown Relocations (Norway) · AGS Movers Norway · Expat Relocation Norway · Immigrationlawyer.no · PwC Norway · BDO Norway.
   - **Approve nothing.**
8. Build a **shortlist** (movers or banks). Continue to **Review & budget**.
9. Record the **estimate currency** — expect **NOK** on an Oslo case.
10. Click **Request quotes** → complete minimum fields → submit. Record: confirmation? RFQ reference? **Is a supplier magic link visible in the UI** (copy-link, invite list, dispatch log)? If email-only, say so.
11. Return to `/test-drive?campaign=qa-smoke2&corridor=FR_NO`. Confirm the session survived navigation (AIQ-1640) — credentials, completion CTA, survey link all present.
12. Click **I've completed my test** → complete the survey → submit.

### Rules

Click custom controls by coordinate, never by ref · `form_input` does not fire React handlers on these forms — type by keyboard · country fields: use the dropdown · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding, not something to route around.

### Report block

```
CARD: SMOKE-1 (re-run)   DATE: ____
CAMPAIGN: qa-smoke2      CORRIDOR: FR_NO
SESSION LABEL: ____   ASSIGNMENT ID: ____   CASE ID: ____
BUDGET USED: __/50

CREDENTIALS: read via find/DOM (not screenshot)?   YES / NO
HR sign-in succeeded?                              YES / NO

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

STEP-BY-STEP:
  4.  HR landing: "Set up your company workspace" (regression) / "Open your first
      relocation case" (fixed) — which? ____
  6.  Preferences gate clear (no destination banner, origin=Paris)?  ____
  7.  SUPPLIERS OFFERED per category (names + counts):               ____
      ⭐ Any of the 9 Norway suppliers?                               ____
  8.  Shortlist built?                                               ____
  9.  Estimate currency (expect NOK):                                ____
 10.  RFQ submitted? ref: ____   Supplier link visible in UI? ____
 11.  Session survived navigation (AIQ-1640)?                        ____
 12.  Survey submitted, thank-you rendered?                          ____

🔴 CRITICAL (report first, stop): ____

FOR COWORK — DB VERIFICATION:
  Tables: rfqs / rfq_items / rfq_recipients (expect the write HERE, not rfq_requests)
          survey_responses (expect campaign='qa-smoke2', non-null session_id + corridor_id)
          company_vendor_selections (expect seeded rows for this company)
  Identifiers: ____

ARTIFACTS TO PURGE (list ALL): ____

BLOCKED BY: ____
```

**After SMOKE-1, hold.** Cowork runs the DB half and makes the cohort go/no-go call.

---

## 5. One note on how this went

You reported a 401, flagged precisely what you could not rule out, and stopped. The finding was wrong; the report was not. Because you named the untested path instead of asserting a conclusion, it took one experiment to settle — and turned up a second, unrelated regression on the way.

That is the behaviour to keep. **A wrong finding reported honestly costs one check. A wrong finding reported confidently costs a sprint.**

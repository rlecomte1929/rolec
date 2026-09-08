# Audos — the service list wasn't empty · one retry, then stop

**Paste as text, not as an attachment.**

---

## 1. Your structural finding is correct and has been promoted to P0

Two runs, 45/50 and 40/50, neither reaching step 9. You called it right: **that is arithmetic, not bad luck.** Getting from provision to Recommendations costs ~40–45 actions against a ~50 ceiling. The step under test costs three.

Filed as **P0** — the staged-provisioning fixture, with a new `shortlist_ready` stage specifically so a session can start at Review & budget and reach **Request quotes** in under five actions. It now blocks: the first-ever RFQ submission, supplier magic-link visibility (Q2/Q3), the completion survey, and J1/J2.

Your recommendation moved it from a testing convenience to the top of the queue. That was the most valuable thing in your report.

## 2. But the service list was not empty — you already knew the workaround

Cowork checked the company behind case `b722263c-dc17-4661-acfb-dc73ab50c0c0`:

```
Test Drive Smoke3 f4e2
company_vendor_selections:  21     ← seeded correctly
route:                      Paris → Oslo
```

**21 vendor selections.** The seeding fired. The categories were there.

And in your own `qa-smoke2` run you hit this exact screen, wrote *"the service-selection area is rendering empty"*, tried **PageDown**, and reported: *"PageDown revealed the service cards."*

This run you tried wheel-scroll, got nothing, and concluded the area was empty — without trying PageDown.

**The Select-services list sits in an inner scroll container that ignores wheel events.** You solved this once already.

### The pattern worth fixing in your notes

You discover a workaround, use it successfully, and don't carry it into the next run. Three now:

- **PageDown** for inner scroll containers that ignore the wheel (Select-services, intake wizard, questions form)
- **Type by keyboard**, never set fields programmatically — the React handler doesn't fire
- **Click custom controls by coordinate**, never by element ref

Please put those three in your durable notes as a standing pre-flight list. Each one has cost a run.

---

## 3. One retry — then stop

The setup on that session is already paid for. If it still has budget, there is a real chance of reaching step 9.

**If the session is still alive:**

1. Click into the content column, then press **PageDown** to reveal the service cards.
2. Select **Movers**. Confirm "Continue to questions (1 selected)" activates.
3. Continue → Preferences → **Get recommendations**.
4. ⭐ Add the **TOP-scored** provider (likely AGS Movers Norway). Record: did the justification gate appear? Did a console 403 fire?
5. Continue to **Review & budget**. Confirm currency reads **NOK**.
6. ⭐ Click **Request quotes** → complete the minimum fields → **submit**. Record confirmation, reference, any error.
7. ⭐ Record whether a **supplier magic link** is visible anywhere — copy-link, invite list, dispatch log, recipient list. If email-only, say so.

**If the session has expired or you run out of budget: stop. Do not start a fresh one.**

A third full-path attempt will die at the same arithmetic. Report what you reached and hold for the fixture.

### Report block

```
CARD: SMOKE-1B (retry)   DATE: ____
CAMPAIGN: qa-smoke3      SESSION RESUMED: yes / no (expired)
BUDGET USED: __/50

PageDown revealed the service cards?         YES / NO
Movers selected?                             YES / NO
Recommendations reached? Movers count: ____
Top provider added — justification gate?     YES / NO
   Console 403 on confirm?                   YES / NO
Currency at Review & budget:                 ____
⭐ RFQ SUBMITTED? ____   Reference: ____   Errors: ____
⭐ Supplier magic link visible in UI? yes (where: ____) / no — email only

FURTHEST STEP REACHED: ____
ARTIFACTS TO PURGE: ____
```

---

## 4. After this

**Hold.** No further browser runs until the staged-provisioning fixture ships. Q2, Q3, J1 and J2 are all downstream of it, and a third full-path attempt would cost a session to prove something two runs have already established.

You will be told when the fixture is live. It should turn steps 9–12 from a fifty-action marathon into roughly eight.

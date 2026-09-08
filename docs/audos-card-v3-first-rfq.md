# CARD V3 — the first RFQ, end to end 🎯

**All four launch blockers are live on `main`. Two are already verified in production:**
- ✅ **Provisioning default** — plain-link provisions now land as `unattributed`, not `insead-2026`. Confirmed: 3 unattributed sessions, cohort baseline clean.
- ✅ **Outbox allowlist** — merged (`659a33dd`).
- ✅ **Vendor seeding** — the loud-failure fix shipped (`d7be1663`); V2 will confirm the rate.
- ✅ **Staged fixture** — `POST /api/test-drive/provision-staged`, dual-registered (no 405 trap), gated `qa-*`+`is_test`-only. This card exercises it.

---

## 1. ⚠️ How the fixture is reached — read this first

The fixture is an **API endpoint, not a URL you open in the browser.** Opening `/test-drive?stage=shortlist_ready` just shows the normal start form — the frontend does not read `stage`. Confirmed.

So V3 has a two-part mechanic:

```
STEP 0 (mint — NOT Audos): POST /api/test-drive/provision-staged
        { "first_name": "RfqV3", "campaign": "qa-v3",
          "corridor_id": "FR_NO", "stage": "shortlist_ready" }
   → returns HR + employee credentials for a session already at Review & budget
     with a shortlist built.

STEPS 1+ (Audos): sign in as the returned EMPLOYEE → land at Review & budget →
     click Request quotes → submit. ~5 actions to the first RFQ.
```

**Step 0 must be fired by something that can POST** — Claude Code, a one-line `curl` from Romain's terminal, or the API client. Audos's browser harness cannot POST, so **Romain or Claude Code mints the session and hands Audos the two credential pairs.** Audos starts at Step 1.

**If the minted employee credentials don't arrive, Audos does not run** — there is nothing to sign into. That is a handoff dependency, not a test failure.

---

## 2. STEP 0 — mint the staged session (Romain or Claude Code)

Run one of these. Both return JSON with `hr_email`, `hr_password`, `emp_email`, `emp_password`.

**Claude Code / terminal:**
```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"RfqV3","campaign":"qa-v3","corridor_id":"FR_NO","stage":"shortlist_ready"}'
```

Expected: a 200 with `session_id`, `stage: "shortlist_ready"`, and both credential pairs.
- **404** → `RELOPASS_TEST_DRIVE_ENABLED` is off in prod, or the campaign gate rejected it. Confirm the flag is set.
- **A shortlist-empty error** → the `shortlist_ready` stage couldn't build a shortlist (likely the vendor-seeding intermittency); note the corridor and retry.

**Hand Audos the `emp_email` and `emp_password`.**

---

## 3. STEPS 1–6 — Audos (browser)

**Budget:** ~20 · **Campaign:** `qa-v3`

1. Go to `https://relopass.com/auth?mode=login`. Decline the analytics banner.
2. Sign in as the **employee** credentials handed to you. **Type by keyboard.** If sign-in 401s and the password contains `O`/`I`/`l`/`0`/`1`, re-mint (ask Romain) rather than assuming the account is broken.
3. Record where you land. **Expected: at or near Review & budget with a shortlist already present.** If you land at an empty Services start instead, the fixture didn't advance the session → **stop and report.**
4. Confirm the estimate currency reads **NOK**.
5. ⭐ Click **Request quotes** → `/employee/case/{id}/services/rfq/new`. Complete the minimum fields → **submit.**
   - Record confirmation, RFQ reference, any error. **This is the first RFQ ever submitted through the product — capture everything.**
6. ⭐ Record whether a **supplier magic link** is visible anywhere in the UI — copy-link control, invite list, dispatch log, recipient list. **If email-only, say so explicitly. Cards Q2 and Q3 depend entirely on this answer.**

### Rules
Type by keyboard, never set fields programmatically · PageDown for inner scroll containers that ignore the wheel · click custom controls by coordinate, never by ref · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding · stop before the budget cap.

### Report block
```
CARD V3   DATE ____   CAMPAIGN qa-v3
MINTED BY: Romain / Claude Code   Employee credentials received? ____
BUDGET USED: __/50

Landed at: ____ (expect Review & budget with shortlist)
Currency: ____ (expect NOK)
⭐ RFQ SUBMITTED? ____   Reference: ____   Errors: ____
⭐ Supplier magic link visible? yes (where: ____) / no — email only

🔴 CRITICAL: ____

FOR COWORK — DB VERIFICATION:
  rfqs / rfq_items / rfq_recipients — expect the write HERE, not rfq_requests
  survey_responses — n/a this card (no survey)
  Identifiers: session_id ____, case/assignment id from the RFQ URL ____
ARTIFACTS TO PURGE: qa-v3 session + case + RFQ
BLOCKED BY: ____
```

---

## 4. What a PASS means

- **RFQ row lands in `rfqs`** (not `rfq_requests`) → SMOKE-1 is finally closed and the canonical model is confirmed by a real write.
- **Magic link visible in the UI** → cards Q2 (supplier submits a quote) and Q3 (quote returns to HR) unblock immediately, and we run them next.
- **Fixture lands the employee at Review & budget in one call** → every future card that needs a mid-flow state (J1, J2, Q2, Q3) becomes a ~10-action run instead of a ~50-action marathon. That is the durable win.

After V3, hold for Cowork's DB check before Q2/Q3.

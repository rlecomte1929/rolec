# CARD V3 — first RFQ, end to end (fully self-contained)

**Paste as text. Audos runs the whole thing — mint + browser — in one session.**

---

## Status: all four launch blockers are live and verified

- ✅ Provisioning default — plain-link provisions now land as `unattributed`, not `insead-2026` (3 confirmed, cohort clean).
- ✅ Outbox allowlist merged.
- ✅ Vendor seeding — loud-failure fix shipped.
- ✅ **Staged fixture** — `POST /api/test-drive/provision-staged`, dual-registered (no 405), gated `qa-*` + `is_test` only. **This card exercises it.**

## What this card proves

The staged fixture lets you skip the ~45-action setup marathon that killed the last two runs. One `curl` mints a session already at Review & budget with a shortlist built; you sign in as the employee and reach **the first RFQ ever submitted through this product in ~5 actions.**

---

## STEP 0 — mint the staged session (curl, then parse)

You have shell access — you used `curl` earlier in this thread. Run:

```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"RfqV3","campaign":"qa-v3","corridor_id":"FR_NO","stage":"shortlist_ready"}'
```

**The response is JSON. Extract these exact paths:**
- `employee.email`  → the login you sign in with
- `employee.password`
- `session_id`, `case_id`, `assignment_id` → record for the report
- `stage` → should read `"shortlist_ready"`
- `shortlist` → should be non-empty (this is the built shortlist)

**If the call fails:**
- **HTTP 404** → the test-drive flag is off in prod, or the campaign gate rejected it. Stop and report the exact body — this is a config finding, not a test failure.
- **A shortlist-empty error / `shortlist: []`** → the fixture couldn't build a shortlist for this corridor (likely the vendor-seeding intermittency). Re-run the curl **once** with `"first_name":"RfqV3b"`. If it fails twice, stop and report — that is the seeding intermittency reproduced through the fixture.
- **HR/employee password contains `O`, `I`, `l`, `0` or `1`** → note it; if browser sign-in later 401s, re-run the curl for a fresh credential rather than assuming the account is broken.

Record the raw JSON (minus passwords) in your notes before continuing.

---

## STEPS 1–6 — browser (employee)

**Budget:** ~20 · **Campaign:** `qa-v3`

1. Go to `https://relopass.com/auth?mode=login`. Decline the analytics banner.
2. Sign in with `employee.email` + `employee.password` from Step 0. **Type by keyboard** (setting fields programmatically doesn't fire the React handler).
3. Record where you land. **Expected: at or near Review & budget with a shortlist already present.**
   - If you land at an empty Services start with no shortlist, the fixture minted credentials but did not advance the session → **stop and report.** That is the fixture half-working.
4. Confirm the estimate currency reads **NOK**.
5. ⭐ Click **Request quotes** → `/employee/case/{id}/services/rfq/new`. Complete the minimum required fields → **submit.**
   - Record confirmation text, RFQ reference, any error. **First RFQ ever submitted — capture everything.**
6. ⭐ Record whether a **supplier magic link** is visible anywhere — copy-link control, invite list, dispatch log, recipient list. **If email-only, say so explicitly. Cards Q2 and Q3 depend entirely on this answer.**

### Rules
Type by keyboard, never set fields programmatically · PageDown for inner scroll containers that ignore the wheel · click custom controls by coordinate, never by ref · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding · stop before the budget cap.

### Report block
```
CARD V3   DATE ____   CAMPAIGN qa-v3
STEP 0 mint: HTTP ____   stage returned: ____   shortlist non-empty? ____
  session_id ____   case_id ____   assignment_id ____
BUDGET USED: __/50

Signed in as employee? ____
Landed at: ____ (expect Review & budget with shortlist)
Currency: ____ (expect NOK)
⭐ RFQ SUBMITTED? ____   Reference: ____   Errors: ____
⭐ Supplier magic link visible? yes (where: ____) / no — email only

🔴 CRITICAL: ____

FOR COWORK — DB VERIFICATION:
  rfqs / rfq_items / rfq_recipients — expect the write HERE, not rfq_requests
  Identifiers: session_id ____, case_id ____, assignment_id ____
ARTIFACTS TO PURGE: qa-v3 session + case + RFQ
BLOCKED BY: ____
```

---

## What a PASS unlocks

- **RFQ row in `rfqs`** → SMOKE-1 closed, canonical model confirmed by a real write.
- **Magic link visible** → cards Q2 and Q3 unblock; run them next.
- **Fixture lands you at Review & budget from one curl** → every future mid-flow card (J1, J2, Q2, Q3) becomes a ~10-action run. That is the durable win — the marathon is over.

After V3, hold for Cowork's DB check before Q2/Q3.

# Audos — RUN 004-V item ④ re-run (the RFQ loop, finally end to end)

**Run only AFTER PR #1670 (`fix/hr-rfq-read`, SHA `0cd77a6b`) is merged AND deployed to prod.** If HR still shows "No quote requests," the deploy hasn't landed — stop and say so, don't route around it.

This is the loop we could never complete. The employee write was always correct (RFQ lands in canonical `rfqs`); the HR read was blind. #1668 fixed the list, #1670 fixed the dispatch button (it lived in a second panel with the same wrong id). Now the whole chain should close.

---

## STEP 0 — mint a fresh staged session, capture BOTH credential sets

```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4v4","campaign":"qa-r4v4","corridor_id":"FR_NO","stage":"roadmap_ready"}'
```
Record: `case_id`, `assignment_id`, `employee.email/password`, `hr.email/password`.

## STEP 1 — Employee: build package + submit RFQ (~10 actions)

1. Sign in as **employee** (type by keyboard). Services → select **Movers + Schools** → answer the pre-filled questions → **Get recommendations**.
2. Build a **6-item package** (3 movers + 3 schools) — use PageDown for the inner scroll, click "Add to package" by coordinate.
   - ⚠️ **Ignore the add-to-package 400s** — confirmed non-fatal (separate P2), the data persists anyway. Do NOT stop on them this time.
3. Go to **Request quotes** → confirm all 6 vendors listed → add note `QA R4V4` → **Send quotation requests**. Confirm "Request recorded."

## STEP 2 — ⭐ HR: does the loop now close? (the fix under test)

4. Sign out. Sign in as **HR**.
5. Open the case detail (Mobility command center → the case).
6. ⭐ **Does the "Vendor quote requests" panel now show the 6 picked vendors with status?** (Was "No quote requests from the employee yet." — this is the #1670 fix.)
7. ⭐ Is there a **dispatch / "request quotes from suppliers" control** now visible? (It lives in Provider Coordination — was 404-ing before #1670.) **Dispatch it.**
8. ⭐ After dispatch, is a **supplier magic link surfaced in the inbox** (not "emailed")? Copy it.

## STEP 3 — Supplier + return (~6 actions)

9. Open the magic link in a **clean, signed-out context** → supplier submits a quote (amount `1234`, note `QA R4V4`). Confirm.
10. Back as **HR** → does the **quote appear / link to the quote-review page**?

## Verdict logic
- HR sees the 6 vendors (step 6) = the #1670 read fix works.
- Dispatch control appears and fires (step 7) = the #1670 coordination-id fix works.
- Magic link in inbox, no email (step 8) = inbox-only dispatch holds.
- Supplier quote returns to HR (steps 9-10) = **the full loop is closed** — the first time end to end.
- Any step BLOCKED = report exactly where and stop. BLOCKED ≠ FAIL.

## Rules
Type by keyboard · PageDown for inner scroll · coordinate-clicks not ref · **ignore the add-to-package 400s** · never `insead-2026` · **no real emails** (a hard guard blocks it — if a real outbound email fires, 🔴 stop) · approve no supplier records · never set `OUTBOX_DISPATCH_CRON_ENABLED` · stop before the cap.

## Report block
```
RUN 004-V item ④ RE-RUN · DATE ____ · CAMPAIGN qa-r4v4 · after PR #1670
case_id ____ · assignment_id ____
BUDGET USED __/50

STEP 1 employee: 6-item package built + RFQ submitted? ____  (400s ignored)
STEP 2 HR:
  ⭐ 6 vendors visible in the panel? ____  (was empty — the fix)
  ⭐ dispatch control present + fired? ____
  ⭐ supplier magic link in the inbox (not emailed)? where: ____
STEP 3:
  supplier quote submitted (1234)? ____
  quote returned / visible to HR? ____

VERDICT: loop CLOSED end-to-end / BLOCKED at step ____
🔴 CRITICAL (real email, etc.): ____

FOR COWORK — DB VERIFY:
  rfqs/rfq_items/rfq_recipients for the case · token_hash minted (n/6) after dispatch ·
  quotes/quote_lines on submit · ZERO Resend sends
  Identifiers: case ____ assignment ____
ARTIFACTS TO PURGE: qa-r4v4
BLOCKED BY: ____
```

**After you report, Cowork DB-verifies the same event:** `token_hash` populated on dispatch, `quotes` row on submit, zero Resend. Two means on the last unverified surface — if both agree the loop closed, the RFQ marketplace is proven end to end for the first time.

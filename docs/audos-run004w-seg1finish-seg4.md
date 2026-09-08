# Audos — RUN 004-W: finish Segment 1 (the RFQ loop) + run Segment 4 (services-state)

Two short jobs. Deploy gate already passed (`1ca6061f`) — no need to re-check unless a run behaves oddly. Same hard rules as the campaign: type by keyboard · one fixture per browser session · never `insead-2026` · **no real emails** · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · BLOCKED ≠ FAIL · stop before the cap.

---

## JOB 1 — Finish the RFQ loop (Segment 1, steps 3–4)

**Why this is a re-run, not a new bug:** Cowork DB-verified that your Dispatch *did* work — 6 real supplier magic links were posted. They are NOT in the HR "Vendors mailbox" (that's why it looked empty). They are in the **employee's inbox quote thread**, one message per vendor:
> "Quote request ready for AGS Movers Norway. They can open it and reply with a price — no account needed: https://relopass.com/supplier/quote?token=eyJ…"

So the link is retrievable inbox-only, no cron/email needed — you were just looking at the wrong surface.

### Fastest path — reuse the qa-r4w1 fixture (links already exist)
If you still have the **qa-r4w1 employee** credentials from the earlier mint (case `020fde12-715a-4479-9dc1-de329bc3618d`):

1. Sign in as the **qa-r4w1 employee** (fresh browser, confirm the account label).
2. Go to the **employee Inbox** → open the **quote thread for the RFQ** (RFQ-20260727-7a1665ab). You'll see 6 "Quote request ready for …" messages, each with a `https://relopass.com/supplier/quote?token=…` link.
3. Copy **one** link (e.g. AGS Movers Norway).
4. Open it in a **clean, signed-out context** (new incognito window / no session) → the supplier quote page loads (no account needed) → submit a quote: amount **`1234`**, note **`QA R4W1`**. Confirm the success state.
5. Sign in as the **qa-r4w1 HR** → open the case → **"Review quotes →"** on the RFQ → confirm the **submitted quote (1234) now appears** (was "No quotes yet").

### If you no longer have qa-r4w1 creds
Mint fresh, submit, dispatch, then do steps 2–5 above:
```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4w1b","campaign":"qa-r4w1b","corridor_id":"FR_NO","stage":"shortlist_ready"}'
```
Employee submits the RFQ → HR opens the case → clicks **Dispatch to suppliers** (email OFF) → then switch to the **employee inbox** to grab the link.

### PASS criteria
- Supplier quote page opens from the inbox link in a signed-out context (no account).
- Quote `1234` submits successfully.
- HR's "Review quotes" shows the returned quote.
- **No real email fired** (inbox-only).

### For Cowork (DB): give me the case_id and I'll confirm
`quotes` / `quote_lines` row now exists for the RFQ (was 0), recipient status advanced, and still **zero Resend**.

---

## JOB 2 — Segment 4: services-state persists 6/6, zero 400s (#1682)

**Mint (start pre-shortlist so you exercise the Add-to-package writes):**
```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4w4","campaign":"qa-r4w4","corridor_id":"FR_NO","stage":"roadmap_ready"}'
```

**Browser (employee):**
1. Sign in as employee (confirm label). Services → select **Movers + Schools** → answer the pre-filled questions → **Get recommendations**.
2. Add **6 items** to the package (3 movers + 3 schools) in quick succession — PageDown for the inner scroll, click "Add to package" by coordinate.
3. ⭐ **Watch for 400s on "Add to package."** Expected: **zero 400s**; all 6 persist. (A transient CORS/500 blip that clears on one "Try again" is OK; a persistent 400 is the finding — capture the request URL + body + response.)
4. Go to **Request quotes** → confirm **all 6 vendors** are listed → this proves the shortlist persisted.

### PASS criteria
- 6 "Add to package" clicks → all 6 persist, **zero 400s**.
- "Request quotations" enables and lists all 6 vendors.

### For Cowork (DB): give me the case_id and I'll confirm
`services_state.shortlist` holds **6 item ids** (category-keyed — I count item ids, not categories).

---

## Report block (per job)
```
RUN 004-W · JOB __ · DATE ____ · CAMPAIGN qa-r4w_ · CORRIDOR ____
JOB 1: supplier quote page opened from inbox link? ____ · quote 1234 submitted? ____ · HR sees the quote? ____
JOB 2: 6/6 added, zero 400s? ____ · Request quotations enabled + 6 vendors? ____
🔴 CRITICAL: ____
FOR COWORK — DB: case ____ assignment ____   ARTIFACTS: qa-r4w_
```

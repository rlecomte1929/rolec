# Audos — RFQ test batch (5 cards, dispatch one at a time)

**Date:** 2026-07-21 · **Base:** `main @ ebee2aa1` · **Target:** `relopass.com`
**Hand over ONE card per session.** Each is self-contained and ends with the same report block.

---

## 0. Four cards are already closed — do not run them

Cowork audited these from the code and verified one live. **They are settled. Skip them.**

| Card | Result | Basis |
|---|---|---|
| **S2** — is the RFQ-new route auth-guarded? | ✅ **PASS** | Route has no guard and the component has no self-guard, but a global 401 interceptor (`client.ts:289`) redirects anonymous users. Verified live: anonymous hit on a real case → redirected, zero data rendered |
| **M1** — does the public supplier page leak PII? | ✅ **PASS** | Payload is `rfq_ref` + service key + brief + expectations + date + boolean. Brief is city-level route, date, property, storage, special items, notes. **Zero** name/email/phone/salary/address/passport anywhere in `rfq_brief.py` |
| **M2** — cross-RFQ token access | ✅ **PASS** | Tokens stored hashed; lookup resolves to one recipient; explicit `row["rfq_id"] != claims["rfq_id"]` → 401 |
| **M3** — expiry / reuse / revocation | ✅ **PASS** | `revoked_at`→403, `quote_submitted_at`→409, `expires_at`→403, plus JWT expiry/tamper/replay checks. DB is hit on **every** request so enforcement is real, not recorded |

**The supplier magic-link layer is sound.** You do not need to hunt for leaks in Q2/Q3 — record what you see, but the security question is answered.

**Two small live confirmations are folded into Q2** (steps Q2.5–Q2.6) since you will have a real token by then. That is the only follow-up needed.

---

## 1. Remaining cards and order

| # | Card | Depends on | Budget |
|---|---|---|---|
| 1 | **R1** — RFQ entry-point recon | — | ~12 |
| 2 | **Q1** — HR creates an RFQ ⭐ | R1 | ~15 |
| 3 | **S1** — are unvetted suppliers offered? 🔴 | Q1 | ~10 |
| 4 | **Q2** — supplier submits a quote | Q1 | ~15 |
| 5 | **Q3** — quote returns to the requester | Q2 | ~10 |

**Q1 is the critical unblock** — S1, Q2 and Q3 all reuse the RFQ it creates. If Q1 fails, stop and report; do not improvise around it.

**Universal rules:** decline the analytics banner first · click custom controls by coordinate, never by ref · country fields — use the dropdown, never type (known defect: typing appends to an injected completion) · never use `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · capture credentials before navigating away · a blocked path is a finding, not something to route around.

---

# CARD R1 — RFQ entry-point recon

**Question:** Where can an RFQ actually be started, and what case state does it need?

**Campaign:** `qa-r1` · **Budget:** ~12 · **Submit nothing — map only.**

1. Provision on `?campaign=qa-r1&corridor=FR_NO`. Sign in as HR.
2. Create a case, assign it to the employee. **Record the case ID from the URL.**
3. From the case page, find any RFQ / quote / "request quotes" entry point. Record its **exact label and URL**.
4. Check the HR sidebar — Service providers, Mobility command center — for another entry.
5. Record whether an RFQ can be started **without** the employee completing intake.

**Known from code, confirm in the UI:** `POST /api/hr/rfq-requests` exists, so HR-initiated RFQ should be possible. Note that `POST /api/employee/quote-requests` returns **410 Gone** — the employee-initiated path is deprecated, so do not chase it.

**Record:** every entry point (label, URL, persona) · whether intake is required · whether a service category must be chosen first.

---

# CARD Q1 — HR creates an RFQ ⭐

**Question:** Can HR create an RFQ end to end, and does it persist?

**Campaign:** `qa-q1` · **Budget:** ~15

1. Provision on `?campaign=qa-q1&corridor=FR_NO`. Sign in as HR. Create + assign a case. **Record the case ID.**
2. Start an RFQ via the entry point R1 found.
3. Choose **movers** or **banks** — both have Norway suppliers seeded, which sets up S1.
4. Fill the minimum required fields. Record anything that blocks progress.
5. Submit. Record: confirmation shown? RFQ appears in a list? What status?
6. **Record every recipient supplier by name** — this is S1's input.
7. **Record whether a supplier link is visible anywhere in the UI** (a copy-link control, a dispatch log). If the link is only ever emailed and never shown, say so — Q2 depends on obtaining one.

**Record:** case ID · RFQ ref/ID · the vocabulary the UI uses ("RFQ" vs "quote request") · recipient names · whether a link is obtainable.

**Cowork will verify** which table the write landed in — `rfqs`, `rfq_requests` or `quote_requests`. That settles which of the three parallel models is canonical.

---

# CARD S1 — Are unvetted suppliers offered to a customer? 🔴

**Question:** Do the nine auto-approved Norway suppliers reach a customer-facing surface?

**Campaign:** reuse `qa-q1` · **Budget:** ~10

**Context:** nine suppliers were imported 2026-07-19 with `platform_vetting_status='approved'` and **`vetted_by=NULL`** — auto-approved, never reviewed by a human. Nothing in the code filters on `verified`. Whether they reach a customer has never been checked.

**Watch for:**

| Category | Suppliers |
|---|---|
| banks | DNB Bank · Nordea Norway · SpareBank1 |
| movers | Crown Relocations (Norway) · AGS Movers Norway |
| legal_admin | Expat Relocation Norway · Immigrationlawyer.no |
| tax_finance | PwC Norway (Global Mobility) · BDO Norway (International Tax) |

1. In the Q1 RFQ, open recipient/supplier selection for **banks**. Record every supplier shown.
2. Repeat for **movers**, **legal/immigration**, **tax**.
3. Record whether any "verified" or "vetted" badge appears beside any supplier.
4. Screenshot each list.

**Record:** which of the nine appear and where. **If none appear, record what IS shown** — that means a filter exists somewhere the code trace has not found, which is equally useful.

**Approve nothing. Edit nothing.**

---

# CARD Q2 — Supplier submits a quote

**Question:** Can a supplier submit through the public page?

**Campaign:** reuse `qa-q1` · **Budget:** ~15 · **Needs a supplier link from Q1.**

1. Open the supplier magic link in a **clean, signed-out context**.
2. Record what the brief shows — expect: move from/to (city + country), target date, property, storage, special items, optional notes. **Flag anything beyond that** (a name, an address, a salary would contradict the code audit and is worth reporting).
3. Complete the quote form with obviously synthetic values — amount `1234`, notes `QA test quote — please ignore`.
4. Submit. Record confirmation or error.
5. **[M3 live check]** Re-open the **same link** after submitting. Expected: rejected with *"You have already sent a quote for this request."* Record what actually happens.
6. **[M3 live check]** If HR has a revoke / withdraw control, use it on a second recipient, then open that link. Expected: *"This request has been withdrawn."* Record. Skip if no such control exists.

**Edge cases if budget allows** — one per line, stop on the first error:
- Amount `0` or negative → validated?
- Amount `999999999999` → handled without overflow?
- Notes containing `<script>alert(1)</script>` → stored and rendered **escaped**? 🔴 only if a dialog actually appears.

---

# CARD Q3 — Does the quote return to the requester?

**Question:** Does a submitted quote become visible to HR?

**Campaign:** reuse `qa-q1` · **Budget:** ~10

1. Sign back in as HR. Open the Q1 RFQ.
2. Record whether the quote appears, its status, and roughly how quickly.
3. Record whether a comparison surface exists when multiple quotes are present.
4. Record whether HR is notified — in-app, email, or not at all. **If an email is sent, record it and stop** (external send).

**PASS:** the quote is visible to the requester.
**FAIL:** the quote persists but never surfaces — that is the "written-never-read" silent-failure pattern seen elsewhere in this codebase, and worth catching here.

---

# Report block — identical for every card

```
CARD: ____            DATE: ____
CAMPAIGN: ____        CORRIDOR: FR_NO
SESSION LABEL: ____   CASE ID: ____
BUDGET USED: __/50

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

WHAT I OBSERVED (facts only, no interpretation):
  ____

🔴 CRITICAL (if any — report first, stop the batch):
  ____

FOR COWORK — DB VERIFICATION:
  Tables to check: ____
  Identifiers: ____

ARTIFACTS TO PURGE: ____

BLOCKED BY: ____
```

---

## After all five

Hand every report block over together. Cowork runs the DB half, merges the outcomes into one findings document, files the required actions in the Notion AI Work Queue with Layer / Priority / Autonomy Tier, and sequences the next stage.

**Do not file tickets from individual cards.** Merging first is what resolves duplicates and causal chains — the survey P0 and the session-persistence P1 turned out to be one chain, not two bugs, and that only became visible once the findings sat side by side.

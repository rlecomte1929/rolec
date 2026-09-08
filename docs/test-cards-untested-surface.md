# Test cards — the untested surface, decomposed

**Date:** 2026-07-21 · **Base:** `main @ ebee2aa1` · **Target:** `relopass.com`
**How to use:** hand Audos **one card at a time**. Each is self-contained, fits one session, and ends with an identical report block so the outcomes merge mechanically.

**Do not dispatch more than one card per session.** Overloading is what killed RUN 003-C/D and the RunE/F/G attempts.

---

## Dispatch order

| # | Card | Risk | Harness needed? | Budget |
|---|---|---|---|---|
| 1 | **R1** — RFQ entry-point recon | — | No | ~12 |
| 2 | **S2** — Unguarded RFQ route | 🔴 auth | No | ~8 |
| 3 | **Q1** — HR creates an RFQ | — | No | ~15 |
| 4 | **S1** — Are unvetted suppliers selected as recipients? | 🔴 customer-facing | No (needs Q1) | ~10 |
| 5 | **M1** — PII on the public supplier page | 🔴 highest | No (needs Q1) | ~12 |
| 6 | **M2** — Cross-RFQ token access | 🔴 highest | No (needs Q1) | ~10 |
| 7 | **M3** — Token expiry, reuse, revocation | 🔴 | No (needs Q1) | ~12 |
| 8 | **Q2** — Supplier submits a quote | — | No (needs Q1) | ~15 |
| 9 | **Q3** — Quote returns to the requester | — | No (needs Q2) | ~10 |
| 10 | **J1** — Intake steps 2–5 → roadmap | — | **Yes** | ~40 |
| 11 | **J2** — Services on the same case + supplier rendering | — | **Yes** | ~20 |

**Cards 1–9 are runnable today.** Only J1/J2 wait on the staged-provisioning fixture.

**Universal rules (apply to every card):** decline the analytics banner first · click custom controls by coordinate, never by ref · never use `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding, not something to route around · capture credentials before navigating away · report the session label for Cowork's DB check.

**On 🔴 cards:** you are looking for exposure, not exploiting it. Record what is visible and stop. Never use a finding to reach further data.

---

# CARD R1 — RFQ entry-point recon

**Question:** From where can an RFQ actually be started, and what is the minimum case state required?

**Prerequisite:** none · **Campaign:** `qa-r1` · **Budget:** ~12

**Steps**
1. Provision on `?campaign=qa-r1&corridor=FR_NO`. Sign in as HR.
2. Create a case and assign it to the employee. Record the case ID.
3. From the case page, look for any RFQ / quote / "request quotes" entry point. Record its exact label and URL.
4. Check the HR sidebar (Service providers, Mobility command center) for an RFQ entry.
5. Do **not** submit anything. This card only maps the surface.

**Record**
- Every RFQ entry point found: label, URL, which persona.
- Whether an RFQ can be started **without** the employee completing intake.
- Whether a service category must be chosen first.

**Why this is first:** it determines whether cards Q1/S1/M1–M3 need a completed journey. `POST /api/hr/rfq-requests` exists, so HR-initiated RFQ should be possible — confirm it in the UI.

---

# CARD S2 — Is the RFQ-new route auth-guarded? 🔴

**Question:** Is `ServicesRfqNew` reachable without being signed in?

**Prerequisite:** none · **Campaign:** `qa-s2` · **Budget:** ~8

**Context:** in `frontend/src/App.tsx` line 390, this route is registered **without** a `Require*Route` wrapper, unlike every sibling route. That may be deliberate or a gap.

**Steps**
1. From card R1, note the RFQ-new URL (something like `/case/:caseId/services/rfq/new`).
2. Open it in a **clean context — signed out entirely**.
3. Record exactly what renders: the form, a redirect to sign-in, an error, or a blank page.
4. If a form renders, record whether any **case data** is visible (employee name, destination, dates).
5. Do **not** submit.

**Pass:** redirected to sign-in, or blocked.
**🔴 FAIL:** the form renders with case data visible to an anonymous visitor. **Stop and report immediately.**

---

# CARD Q1 — HR creates an RFQ

**Question:** Can HR create an RFQ end to end, and does it persist?

**Prerequisite:** R1 complete · **Campaign:** `qa-q1` · **Budget:** ~15

**Steps**
1. Provision on `?campaign=qa-q1&corridor=FR_NO`. Sign in as HR. Create + assign a case. **Record the case ID.**
2. Start an RFQ via the entry point R1 found.
3. Choose a service category — prefer **movers** or **banks** (both have Norway suppliers seeded).
4. Complete the minimum required fields. Record any field that blocks progress.
5. Submit.
6. Record: confirmation shown? RFQ visible in a list afterwards? What status?

**Record**
- Case ID · RFQ ID or reference if shown
- The vocabulary the UI uses — "RFQ" vs "quote request" (feeds the canonical-model question)
- Every recipient supplier listed, **by name**

**Cowork will verify:** which table the write landed in — `rfqs`, `rfq_requests`, or `quote_requests`. That settles which of the three parallel models is canonical.

---

# CARD S1 — Are unvetted suppliers selected as recipients? 🔴

**Question:** Do the nine auto-approved Norway suppliers get offered to a customer?

**Prerequisite:** Q1 complete · **Campaign:** reuse `qa-q1` · **Budget:** ~10

**Context:** nine suppliers were imported on 2026-07-19 with `platform_vetting_status='approved'` but `vetted_by=NULL` — auto-approved, never reviewed by a human. Nothing in the code filters on `verified`. Whether they reach a customer has never been checked.

**Watch for these names**

| Category | Suppliers |
|---|---|
| banks | DNB Bank · Nordea Norway · SpareBank1 |
| movers | Crown Relocations (Norway) · AGS Movers Norway |
| legal_admin | Expat Relocation Norway · Immigrationlawyer.no |
| tax_finance | PwC Norway (Global Mobility) · BDO Norway (International Tax) |

**Steps**
1. In the RFQ from Q1, open the recipient/supplier selection for **banks**. Record every supplier shown.
2. Repeat for **movers**, then **legal/immigration**, then **tax**.
3. Record whether any "verified" or "vetted" badge appears next to any supplier.
4. Screenshot each category list.

**Record:** which of the nine appear, and in which category. If none appear, record what **is** shown instead — that tells us a filter exists somewhere the code trace has not found.

---

# CARD M1 — What does the public supplier page expose? 🔴 HIGHEST RISK

**Question:** Does the unauthenticated supplier quote page leak case PII?

**Prerequisite:** Q1 complete, with a supplier magic link obtainable · **Campaign:** reuse `qa-q1` · **Budget:** ~12

**Context:** `App.tsx` line 307 comment: *"AIQ-1521 — supplier magic-link quote page. Public: token in the URL is the only auth."* This is the largest attack surface in the product and has never been examined.

**Steps**
1. Obtain the supplier magic link from Q1 — from the HR RFQ detail page, a copy-link control, or a dispatch record. If it is only ever emailed and never shown in the UI, record that and mark **BLOCKED**.
2. Open it in a **clean context, fully signed out**.
3. Inventory **everything** visible on the page. Specifically check for: employee full name · home or destination address · salary or budget figures · passport or nationality · family details · dates of birth · the HR contact's details.
4. Record what the brief legitimately needs (service category, destination city, rough dates, volumes) versus what exceeds it.
5. Screenshot the full page.

**Pass:** only brief-scoped data — service, destination city, approximate dates, quantities.
**🔴 FAIL:** any employee personal data. **Stop the batch and report immediately.**

**Do not** submit, alter, or probe further. Observe and stop.

---

# CARD M2 — Cross-RFQ token access 🔴

**Question:** Can one supplier's token reach another RFQ's data?

**Prerequisite:** Q1 complete, ≥2 recipients · **Campaign:** reuse `qa-q1` · **Budget:** ~10

**Steps**
1. Obtain the magic link for **supplier A**. Note the URL structure: is the identifier an opaque token, or a guessable id (sequential integer, plain UUID, supplier name)?
2. Record the token format only — **do not** attempt to forge or brute-force one.
3. If the RFQ has a second recipient, obtain **supplier B's** link.
4. Open A's link. Record whether the page shows **only** A's context, or exposes B's quote, B's identity, or a list of all recipients.
5. Record whether A can see any **competing quote amount**.

**Pass:** each token scopes strictly to its own recipient row.
**🔴 FAIL:** a supplier can see another supplier's quote, identity, or pricing. **Stop and report.**

**Boundary:** use only links the product legitimately issued you. Never modify a token to test what happens.

---

# CARD M3 — Token expiry, reuse and revocation 🔴

**Question:** Does a supplier token stop working when it should?

**Prerequisite:** Q1 complete · **Campaign:** reuse `qa-q1` · **Budget:** ~12

**Context:** `rfq_recipients` carries `expires_at`, `revoked_at`, `first_viewed_at`, `quote_submitted_at` — so expiry and revocation are modelled. Whether they are enforced is unknown.

**Steps**
1. Open the supplier link. Record whether the page states an expiry date.
2. Open the **same link a second time**. Does it still work? (Single-use vs reusable — either is valid, but which?)
3. If HR has a "revoke" or "cancel invite" control, use it, then re-open the link. Record whether it is rejected.
4. After submitting a quote (card Q2), re-open the link. Can the quote be edited or re-submitted?

**Record:** reusable or single-use · expiry surfaced to the supplier · revocation enforced · post-submission behaviour.

---

# CARD Q2 — Supplier submits a quote

**Question:** Can a supplier actually submit a quote through the public page?

**Prerequisite:** Q1 + M1 complete · **Campaign:** reuse `qa-q1` · **Budget:** ~15

**Steps**
1. Open the supplier magic link in a clean context.
2. Complete the quote form with obviously synthetic values — amount `1234`, currency as offered, notes `QA test quote — please ignore`.
3. Submit. Record confirmation or error.
4. Record every field that blocked or validated.

**Edge cases if budget allows** — one per line, stop if any errors:
- Amount `0` or negative → validated?
- Amount `999999999999` → handled without overflow?
- Notes containing `<script>alert(1)</script>` → stored and rendered **escaped**? 🔴 if a dialog appears.

---

# CARD Q3 — Does the quote return to the requester?

**Question:** Does a submitted quote become visible to HR, and is it comparable?

**Prerequisite:** Q2 complete · **Campaign:** reuse `qa-q1` · **Budget:** ~10

**Steps**
1. Sign back in as HR. Open the RFQ from Q1.
2. Record whether the quote appears, with what status, and how quickly.
3. Record whether a comparison surface exists when multiple quotes are present.
4. Record whether HR is notified — in-app, email, or not at all. **If an email is sent, record it and stop** (external send).

**Pass:** submitted quote is visible to the requester.
**FAIL:** the quote persists but never surfaces — that is the "written-never-read" silent-failure pattern.

---

# CARD J1 — Intake steps 2–5 → roadmap ⏸ needs harness

**Question:** Does the employee reach a rendered roadmap through the full intake?

**Prerequisite:** staged-provisioning fixture · **Budget:** ~40

Four runs have died before completing this. **Do not attempt without the fixture** (`stage=case_created`).

**Steps:** from a `case_created` session, sign in as employee → intake steps 2–5 → submit → observe the roadmap.
**Country fields: use the dropdown list, never type** (known defect: typing appends to an injected completion).
**Record:** which step each field blocked on · roadmap rendered in-session vs holding state · phase and task counts.

---

# CARD J2 — Services on the same case ⏸ needs harness

**Question:** Does Services open on the intake case, and which suppliers render?

**Prerequisite:** J1, or fixture `stage=roadmap_ready` · **Budget:** ~20

**Steps:** open Services → compare the case ID against intake's → record every supplier shown per category (cross-check against the S1 list) → record the estimate currency (expect USD; correct is NOK).

---

# Report block — identical for every card

Use this verbatim so the outcomes merge without translation.

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

## When all cards are in

Hand every report block to Cowork together. Cowork will run the DB half, merge the outcomes into a single findings document, file the required actions in the Notion AI Work Queue with Layer / Priority / Autonomy Tier, and produce the sequenced plan for the next stage.

**Do not file tickets from individual cards.** Findings are merged first so duplicates and causal chains are resolved before anything reaches the queue.

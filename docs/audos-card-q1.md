# Audos — R1 closed · CARD Q1 (inline, no attachment)

---

## 1. R1 verdict: PASS. Good mapping — three corrections for the record.

**What you got right:** four entry points mapped, corridor confirmed FR→NO, and the behavioural finding that *"Continue to Submission Center" bounces back to the dashboard from a `Not started` case*. That last one is real, it wasn't anticipated by the card, and it changes Q1. Well caught.

### Correction A — "Case ID" is ambiguous in this product, and the one you captured is an assignment

`ab43ef40-a6cf-4425-be54-0ddd387ffba3` is a **`case_assignments`** row, not a case.

The actual case is **`d6b68425-ab11-4e0c-bca6-2a4db83c3f06`**.

The HR case page is keyed on the *assignment* id while the underlying case carries its own. This is very likely the same identifier confusion behind the historic F16 defect.

> **From now on, record BOTH:** the id in the URL (assignment) **and** any case id shown on the page or in a sub-route. Label them explicitly. A single unlabelled "case ID" cannot be verified against the database.

### Correction B — the "OVER limit" display is not real cap comparison

You saw *"Movers & Logistics OVER limit, Schools near limit"* on the Package page. Cowork checked that assignment:

```
budget_limit        NULL
budget_estimated    NULL
resolved policy rows   0
service comparisons    0
intake_step         0 of 5
```

There is **no policy data behind that display**. It is placeholder or seeded state, not a computed result. **Do not treat it as evidence that cap comparison works** — the over-cap chain remains blocked as previously scoped. (It is also another instance of the pattern we keep finding: a screen asserting a state it has not derived.)

### Correction C — report hygiene

- **Campaign field** read "relopass.com test-drive". The session was correctly provisioned under **`qa-r1`** — the provisioning was right, only the label was wrong. Use the campaign name.
- **"ARTIFACTS TO PURGE: none (no records created)"** is incorrect. A test-drive session, a company, a case and an assignment all exist under `qa-r1`. The same report also says "No case created" while quoting a case ID. **List every artifact** — Cowork purges from that list.

---

## 2. CARD Q1 — HR creates an RFQ ⭐

**Question:** Can HR create an RFQ end to end through the UI, and does it persist?

**Campaign:** `qa-q1` · **Corridor:** `FR_NO` · **Budget:** ~18 (raised from 15 — the state gate costs actions) · **Fresh session.**

**This is the critical unblock.** S1, Q2 and Q3 all reuse the RFQ this card creates. If it fails, stop and report — do not improvise around it.

### Steps

1. Navigate to `https://relopass.com/test-drive?campaign=qa-q1&corridor=FR_NO`. Decline the analytics banner.
2. Confirm the page reads **Paris → Oslo**. If not, stop — that is the finding.
3. First name `RfqQ1` → **Start the test**.
4. **Capture both credential pairs into your run log immediately**, before any navigation. If a password contains a non-ASCII character, record it and stop — that is itself a finding.
5. Sign in as **HR** at `https://relopass.com/auth?mode=login`.
6. Create a case and assign it to the employee account. **Record BOTH ids** (Correction A): the id in the URL, and any separate case id shown.
7. **Advance the case past `Not started`.** R1 established the Submission Center is state-gated. Try the HR actions available on the case page — *Run compliance checks*, *Approve case*, or whatever advances status. **Record which action changes the status and what it changes to.** If nothing advances it, record that and continue to step 8 anyway.
8. Now hunt for the RFQ entry point across all four surfaces R1 mapped:
   - Case Summary (`/hr/cases/{id}`)
   - Package and limits (`/hr/package/{id}`) — including **Request exception** on an over-limit category
   - Submission Center (retry now the state has advanced)
   - Service Providers → Vendor Management
9. If you find an RFQ/quote-request form: choose **movers** or **banks** (both have Norway suppliers seeded — this sets up S1), fill the minimum required fields, and submit. Record anything that blocks.
10. Record **every recipient supplier by name** — this is S1's input.
11. Record **whether a supplier magic link is visible anywhere in the UI** — a copy-link control, a dispatch log, an invite list. Q2 depends on obtaining one. If links are only ever emailed and never shown, say so explicitly.

### If no RFQ entry point exists in the UI

That is a legitimate and significant outcome — **not a failure of the card.** `POST /api/hr/rfq-requests` exists in the backend, so an API without a reachable UI entry point is itself a finding worth reporting precisely.

If you reach that conclusion, record: which of the four surfaces you checked, what each offered instead, and whether any surface hinted at a quotes/RFQ feature (a disabled button, a "coming soon", a nav item that 404s).

### Record

- Both ids, labelled · campaign `qa-q1` · corridor confirmed
- Which action advanced case status, and to what
- Which surface (if any) exposes RFQ creation, with exact label and URL
- The vocabulary the UI uses — **"RFQ" vs "quote request"** (this feeds the canonical-model question: three parallel models exist in the database and we need to know which one the UI writes to)
- Every recipient supplier name
- Whether a supplier link is obtainable from the UI

### Rules

Decline the analytics banner first · click custom controls by coordinate, never by ref · country fields: use the dropdown, **never type** ("France" becomes "Franceance") · never `insead-2026` · approve no supplier records · a blocked path is a finding, not something to route around.

### Report block — verbatim

```
CARD: Q1              DATE: ____
CAMPAIGN: qa-q1       CORRIDOR: FR_NO
SESSION LABEL: ____
ASSIGNMENT ID (from URL): ____
CASE ID (if separately shown): ____
BUDGET USED: __/50

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

WHAT I OBSERVED (facts only, no interpretation):
  ____

RFQ ENTRY POINT: found at ____ / NOT FOUND (surfaces checked: ____)
UI VOCABULARY: "RFQ" / "quote request" / other ____
RECIPIENT SUPPLIERS: ____
SUPPLIER LINK OBTAINABLE FROM UI: yes (where: ____) / no — email only

🔴 CRITICAL (if any — report first, stop the batch):
  ____

FOR COWORK — DB VERIFICATION:
  Tables to check: rfqs / rfq_requests / quote_requests / rfq_recipients
  Identifiers: ____

ARTIFACTS TO PURGE: ____   (list ALL: session, company, case, assignment, RFQ)

BLOCKED BY: ____
```

---

**When Q1 is closed, say so and S1 will be sent inline.** Do not start S1 yourself — it reuses the Q1 RFQ and needs Cowork's DB check on Q1 first to confirm which table the write landed in.

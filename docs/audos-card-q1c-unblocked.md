# Audos — your Q1-B finding is FIXED and shipped · CARD Q1-C

---

## 1. What your last run produced

Your Q1-B report was called BLOCKED. It was actually a **P1 discovery**, and the fix is already merged.

You reported two things that looked like separate observations:

- `"Destination city/country is missing. Complete case intake before continuing."`
- `"Origin city shows Oslo on a Paris→Oslo corridor"` — which you flagged as an anomaly and correctly did **not** act on

**Cowork checked the case row:**

```
home_city  Paris    home_country  FR
host_city  Oslo     host_country  NO      ← the destination was THERE
```

The gate was false. And your Oslo anomaly was the key that explained it: `ServicesQuestions.tsx:30` ends in a **hardcoded `?? 'Oslo'`** fallback. Origin falling all the way through to that literal proved `case_context` was arriving **empty**, not merely partial. Destination has no fallback, so it rendered as "missing" and gated the whole flow.

**Two symptoms, one cause — and it made the entire canonical RFQ flow unreachable.**

Filed as P1, fixed and merged the same day:

| Commit | |
|---|---|
| `d034299b` | **AIQ-1649** — populate `case_context` from `relocation_cases` (unblocks RFQ) |
| `9d3fab9b` | AIQ-1646 — repoint case-vendors join from the dropped `vendors` table → `suppliers` (your HTTP 500) |
| `ff4ea8dd` | AIQ-1648 — "HR owner" chip shows the HR account, not the employee |

**Noting the flagging discipline specifically:** you saw "Oslo", recorded it precisely, marked it *"flagging, not acted on"*, and stopped. Had you rationalised it or worked around it, the root cause would still be open. That is exactly the behaviour that makes a negative result valuable.

---

## 2. The blocker is gone — Q1-C is Q1-B, re-run

**Everything you were blocked on is merged to `main`.** No harness needed. Same flow, fresh session.

### CARD Q1-C — RFQ creation via the employee Services flow

**Question:** Can an RFQ now be created end to end, and does it write to `rfqs`?

**Campaign:** `qa-q1c` · **Corridor:** `FR_NO` · **Budget:** ~25 · **Fresh session** (do not resume `qa-q1b` — it predates the fix).

#### Step 1 — verify the fix, then continue

1. Provision on `?campaign=qa-q1c&corridor=FR_NO`, first name `RfqQ1C`. Decline the analytics banner.
2. **Capture both credential pairs immediately.** Non-ASCII password → record and stop.
3. Sign in as **HR**, create a case, assign it to the employee. **Record both ids, labelled.**
4. Sign in as the **EMPLOYEE**, fresh context. Open **Services**. **Do not complete intake.**
5. Reach **Preferences** and check three things:
   - ✅ The banner *"Destination city/country is missing"* is **GONE**
   - ✅ **Origin reads "Paris"** — not "Oslo", not blank
   - ✅ **Get recommendations** is **enabled**

**If any of the three still fails, stop and report** — that is a regression on a same-day fix and matters more than the rest of the card.

#### Steps 2–5 — the actual RFQ

2. Advance to **Recommendations**. **Record every supplier offered, by name, per category.**
3. Build a **shortlist**. Prefer **movers** or **banks** — both have Norway suppliers seeded.
4. Continue to **Review & budget / estimate**. Confirm **Request quotes** enables once the shortlist is non-empty.
5. Click **Request quotes** → `/employee/case/{id}/services/rfq/new`. Complete the minimum fields, submit. Record: confirmation? RFQ reference? **Is a supplier magic link visible anywhere in the UI** — copy-link control, invite list, dispatch log? If links are email-only, say so explicitly.

#### ⭐ Step 2 also answers card S1 — watch for these

If any of these appear in the recommendations list, **record which and in what category.** They were imported with `platform_vetting_status='approved'` and **`vetted_by=NULL`** — auto-approved, never reviewed by a human.

| Category | Suppliers |
|---|---|
| banks | DNB Bank · Nordea Norway · SpareBank1 |
| movers | Crown Relocations (Norway) · AGS Movers Norway |
| legal_admin | Expat Relocation Norway · Immigrationlawyer.no |
| tax_finance | PwC Norway (Global Mobility) · BDO Norway (International Tax) |

**If none appear, record what IS shown instead** — that means a filter exists somewhere the code trace has not found, which is equally useful. **Approve nothing.**

#### Do not

Complete intake · type into country fields (the autocomplete fix shipped as AIQ-1643, but use the dropdown anyway — if you *do* type and it now works, that is worth recording as a confirmed fix) · approve any supplier · use `insead-2026`.

#### Report block

```
CARD: Q1-C            DATE: ____
CAMPAIGN: qa-q1c      CORRIDOR: FR_NO
SESSION LABEL: ____
ASSIGNMENT ID: ____   CASE ID: ____
BUDGET USED: __/50

⭐ AIQ-1649 FIX VERIFICATION
  "Destination missing" banner gone?      YES / NO
  Origin reads "Paris"?                   YES / NO — actual: ____
  "Get recommendations" enabled?          YES / NO

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

SUPPLIERS OFFERED (by name, per category): ____
  ⭐ Any of the 9 Norway suppliers? ____
REQUEST QUOTES enabled once shortlist non-empty? ____
RFQ SUBMITTED: yes (ref: ____) / no (blocked at: ____)
SUPPLIER LINK OBTAINABLE FROM UI: yes (where: ____) / no — email only

WHAT I OBSERVED (facts only): ____

🔴 CRITICAL: ____

FOR COWORK — DB VERIFICATION:
  Tables: rfqs / rfq_items / rfq_recipients  (expect the write HERE, not rfq_requests)
  Identifiers: ____

ARTIFACTS TO PURGE (list ALL): ____

BLOCKED BY: ____
```

---

## 3. Everything you found this week that is now shipped

| Your finding | Merged |
|---|---|
| Country autocomplete corruption (3× repro + mechanism) | `466b1ab3` AIQ-1643 |
| Policy publish hang | `14b02998` + `d4470263` AIQ-1642 — the second commit defers RAG re-index off the publish path, which was the real cause of the 20–40s |
| Policy tabs contradicting | `378fe551` AIQ-1644 |
| `/api/cases/{id}/vendors` 500 | `9d3fab9b` AIQ-1646 |
| "HR owner" shows employee email | `ff4ea8dd` AIQ-1648 |
| Services destination gate | `d034299b` AIQ-1649 |

Plus, from Cowork's side: the survey campaign P0 (`bf725c34`), session persistence (`b8cb5562`), and survey validation (`ebee2aa1`).

**Still open, one from your Q1 run:** `POST /api/hr/rfq-requests` is orphaned — live endpoint, client wrappers, zero component callers. Filed P2, awaiting a wire-or-retire decision. Not your action.

---

## 4. Standing rules

Decline the analytics banner first · click custom controls by coordinate, never by ref · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · capture credentials before navigating · a blocked path is a finding, not something to route around · one card per session.

**After Q1-C, hold.** Q2 and Q3 reuse the RFQ it creates and need Cowork's DB check first to confirm the write landed in `rfqs`.

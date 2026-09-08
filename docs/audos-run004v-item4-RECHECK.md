# Audos — RUN 004-V item ④ RE-CHECK (you looked at the wrong panel)

**Read this before re-running.** Your clean re-run was well executed — steps a and b were correct, the employee write is provably perfect. But the step-c FAIL is a **misread of the HR page, not a broken fix.** Cowork verified the fix end-to-end at the DB + code level. Here's exactly what to look at this time.

---

## What Cowork proved (so you know what "PASS" looks like)

For your own fixture `qa-r4v4` (case `241b8f01…`, assignment `a89b6476…`):

- The employee RFQ landed canonically: **RFQ `RFQ-20260726-b0e66b02`, status `sent`, 6 recipients, all with supplier tokens minted** — the 3 movers + 3 schools you picked. Keyed on the real case id, zero on the assignment id.
- The assignment `a89b6476` **carries `case_id = 241b8f01`**, so the HR page resolves `detail.caseId` correctly.
- The HR reader `GET /api/hr/cases/241b8f01/rfqs` is **registered in the prod entry point** and prod runs the exact SHA (`a8bc353f`) that contains the #1668 read fix.
- Your HR persona `hr-r4v4-58f6@probe.test` is in the **same company** as the case — so the reader's tenant check passes for you. It returns the RFQ with all 6 vendors.

The read is not 404ing. Running that query by hand returns the 6 vendors right now.

---

## Why you saw "empty + 404" — the two panels are different

The HR case detail has **two unrelated cards**:

| Card title | What it is | Correct state for this test |
|---|---|---|
| **"Vendor quote requests"** (subtitle: *"RFQs you've sent to vendors for this case"*, has a **"Find a vendor"** button) | ⭐ **THIS is the RFQ panel — the #1668 fix.** Shows the 6 picked vendors + a **"Review quotes →"** link. | **Should show RFQ-20260726-b0e66b02 with 6 vendors.** |
| **"Provider Coordination"** (*"No providers assigned yet — Use 'Invite Provider'"*) | A **different feature** — HR assigning task-owners to a case. Nothing to do with the employee's RFQ. | **Correctly empty.** This is what you reported — it's a red herring. |

You inspected **Provider Coordination** (legitimately empty) and reported it as the RFQ fix failing. The 3× generic `404`s on the page are the other no-data panels (predictions / immigration / providers-assigned), **not** the RFQ reader.

---

## The re-check (resume from step c only — ~6 actions)

Re-mint a fresh `stage=shortlist_ready` fixture on `qa-r4v5` (FR_NO), submit the RFQ as employee (steps a–b, you nailed these), then as HR:

1. Open the case detail. **Scroll to the card titled exactly "Vendor quote requests"** (not "Provider Coordination").
2. ⭐ **Does it list the RFQ with the 6 picked vendors** (3 movers + 3 schools), each with a status? Screenshot it. **This is the assertion.**
3. If YES → click **"Review quotes →"** on the RFQ → confirms it routes to the quote-review page (`/quotes/rfq/{id}`).
4. Then exercise **dispatch → supplier magic link in the inbox** (no email), supplier submits a quote (`1234`), and confirm it returns to HR.

### If "Vendor quote requests" is STILL empty
Then — and only then — it's a real issue (most likely a lagging frontend deploy). **Capture the exact failing request:** open the network panel, find the call to `/api/hr/cases/{id}/rfqs`, and record **the full URL (which id it used) + the status code + the response body.** That single captured request tells us whether the frontend passed the case id or the assignment id. Do not report "404" without that URL — a generic 404 from another panel is what caused this whole detour.

---

## Rules (unchanged)
One fixture per browser session · type by keyboard · PageDown for inner scroll · never `insead-2026` · no real emails (hard guard) · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · stop before the cap · **BLOCKED ≠ FAIL, and "empty panel" ≠ FAIL until you've named the exact failing request URL.**

## Report block
```
RUN 004-V item ④ RE-CHECK · DATE ____ · qa-r4v5 · after #1668 (prod a8bc353f)
case_id ____ · assignment_id ____   BUDGET __/50

⭐ "Vendor quote requests" card shows the 6 vendors? ____  (screenshot)
   "Review quotes →" routes to /quotes/rfq/{id}? ____
   dispatch → supplier magic link in inbox (not emailed)? ____
   supplier quote (1234) returns to HR? ____

If empty: exact failing request URL + status + which id ____

VERDICT: loop CLOSED / still empty (with captured URL) / BLOCKED at ____
FOR COWORK: case ____ assignment ____   ARTIFACTS: qa-r4v5
```

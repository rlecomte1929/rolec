# Claude Code — fix the HR RFQ read (unblocks the RFQ loop)

Paste from repo root. Base off current `main`. **Own branch off `main`: `fix/hr-rfq-read`. Do NOT use `fix/td-qa-services-batch-0719`.** Read `CLAUDE.md`.

This is the tactical fix that unblocks the RFQ loop for the cohort. It is **deliberately scoped narrow** — the broader case-vs-assignment id class is a separate Red/Needs-Decomposition ticket; do NOT expand into it here. Reuse the reader that already exists.

---

## What's proven (DB + code verified — do not re-investigate)

The employee RFQ flow is **correct end to end**: an employee submits, and the RFQ persists to the canonical `rfqs` table keyed on the real **case id**. Cowork confirmed: for case `27b80b5e-2dea-41ac-a1d0-8048100c8881`, `rfqs` = 1, `case_id = 27b80b5e`.

**The HR side is blind because it reads the wrong table with the wrong id — two bugs stacked:**

1. **Wrong table.** `frontend/src/pages/HrCommandCenterCaseDetail.tsx:122` calls `hrAPI.getQuoteRequests({ case_id: id })` → `backend/app/routers/employee_quotes.py::list_hr_quote_requests` (~line 219-250) → `SELECT ... FROM quote_requests` — the **orphaned** table, not `rfqs`.
2. **Wrong id.** `id` there is the route param = the **assignment** id (`3d55c9ad…`), but the RFQ is keyed on the **case** id (`27b80b5e…`).

**The correct reader already exists:** `backend/app/routers/hr_coordination.py:157` — `GET /api/hr/cases/{case_id}/rfqs` reads `FROM rfqs WHERE case_id = :cid`. The case-detail page just isn't calling it.

---

## The fix (prefer reuse over new code)

1. **Point the HR case-detail quote-requests panel at the canonical reader** — `GET /api/hr/cases/{case_id}/rfqs` (`hr_coordination.py`) — instead of `getQuoteRequests` → `quote_requests`. The panel must render the RFQ's picked vendors from `rfqs` / `rfq_items` / `rfq_recipients`.
2. **Resolve the id.** The page holds the assignment id from the route; resolve it to the canonical `case_id` before querying, using the existing `caseIdForAssignment` (`frontend/src/utils/employeeAssignmentScope.ts`) — the same util AIQ-1691 used. If a resolution miss is possible, fail **closed** (show nothing / a clear "loading" or error), never query with the raw assignment id.
3. **Retire the dead read** if nothing else uses it: if `list_hr_quote_requests` → `quote_requests` has no other caller after step 1, remove it (or leave it clearly marked legacy). Do NOT create a new endpoint — the canonical one exists.

**Do NOT** touch the employee write path (it's correct), the supplier-token/dispatch security (M1/M2/M3 audited it), or attempt the broad structural resolver (separate ticket).

---

## Acceptance (must be demonstrable end to end)

1. Employee submits an RFQ (6 picks) → the HR case detail for that case shows **the 6 picked vendors with status**, not "No quote requests from the employee yet."
2. The panel reads `rfqs`, confirmed — not `quote_requests`.
3. Opening the case detail by its **assignment-id route** still resolves to the right case's RFQ.
4. With HR now able to see the RFQ, the **dispatch → supplier magic link (inbox) → supplier quote → quote-back-to-HR** chain becomes reachable (spot-check it works; the inbox-only dispatch already shipped in `292ba9a0`).
5. A test: employee RFQ on case X → GET the HR quote-requests for X's assignment → returns the RFQ.

---

## Reproduce first, then fix
Provision a staged session (`POST /api/test-drive/provision-staged`, `campaign=qa-hrfix&corridor=FR_NO&stage=roadmap_ready`), employee builds a package + submits an RFQ (ignore the non-fatal add-to-package 400s — separate P2), then sign in as HR and open the case detail. Confirm the empty panel, then confirm which table/id the request uses, then fix.

## Hard rules
- Branch `fix/hr-rfq-read` off `main`, own PR. Never `fix/td-qa-services-batch-0719`, never push `main`.
- Any router change → register in BOTH `backend/main.py` and `backend/app/main.py`; verify with the routes check.
- Reuse the canonical reader and the existing `caseIdForAssignment`; do not create a 4th RFQ model or a parallel resolver (that's the structural ticket's job).
- `cd frontend && npx tsc --noEmit` and `cd backend && pytest` before the PR.

## Report
branch · SHA · PR · which table/id the panel used before vs after · HR now sees the 6 vendors (screenshot or test) · dispatch chain reachable? · test output.

**After this ships, Cowork DB-verifies** (`rfq_recipients.token_hash` on dispatch, `quotes` on supplier submit, zero Resend) and Audos re-runs RUN 004-V item ④ end to end — the loop we could never complete.

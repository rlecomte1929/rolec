# Claude Code — three ready fixes (paste verbatim from repo root)

---

You are working in `rolec` (ReloPass: React/Vite frontend, FastAPI backend, Supabase, deploys to Render from `main`). Base all work off the current `main`.

**Three independent tasks. Each gets its OWN branch off `main` and its OWN PR. Do NOT combine them, and do NOT use `fix/td-qa-services-batch-0719`** — that branch carries ~40 duplicate doc commits and unrelated migrations and is unreviewable. One branch per fix off `main`, exactly like `fix/staged-fixture-currency` (which shipped clean as `4ede38a9`).

Read `CLAUDE.md` before starting. Hard rules that apply:
- Before every PR: `cd frontend && npx tsc --noEmit` and `cd backend && pytest` (or the scoped test file where noted).
- One atomic commit per task. A task is not done without a commit SHA on a named branch.
- Any router change → register in BOTH `backend/main.py` and `backend/app/main.py` (none of these three should need it — flag if one does).

---

## TASK 1 — Merge the staged-fixture currency fix (already built)

**PR #1620 already exists** on branch `fix/staged-fixture-currency` (SHA `4ede38a9`, AIQ-1661). It derives the staged fixture's display currency from the destination country instead of the hardcoded `"EUR"` literal (FR_NO → NOK). Cowork verified the logic: NOK for Norway, USD fallback for SGD/AED corridors (correct — those aren't in the FX map).

**Do:**
1. Confirm the PR still rebases cleanly on current `main`; if not, rebase and push.
2. Confirm CI is green (`test_fx_service.py` + `test_test_drive_provision.py`).
3. Merge it. Report the merge SHA.

Nothing to build — this is a review-and-merge.

---

## TASK 2 — Fix the false RFQ confirmation copy *(Notion: "RFQ confirmation falsely tells the employee 'your HR team can see the providers you picked'")*

**Branch:** `fix/rfq-confirmation-copy`

**Problem:** After an employee submits an RFQ, `frontend/src/pages/services/ServicesRfqNew.tsx:346` shows:
> Request recorded — **your HR team can see the providers you picked and will follow up.** We've added this to your roadmap.

Cowork's DB investigation proved this is false: **no HR surface reads the canonical `rfqs` table** (the HR endpoint reads the orphaned `rfq_requests`; the coordination panel reads a provider table), and Audos confirmed live that HR sees "No providers assigned yet." No supplier was contacted either — `rfq_recipients.token_hash` is NULL for all 6 recipients.

This file already has a remediation history for the same copy — **AIQ-1515** removed "Quotation requests sent" (implied vendors were contacted), **AIQ-1523** noted "creating an RFQ still reached no supplier," and a comment at line 233 says a prior version "was false." This is the next iteration of the same falsehood, now on the HR-visibility claim.

**Do:**
1. In `ServicesRfqNew.tsx` (line ~346 and the sibling branch ~line 334), rewrite the confirmation to state **only what is true today**:
   - ✅ the request is recorded
   - ✅ it's on the roadmap
   - ❌ remove: "your HR team can see the providers you picked", "will follow up", and any implication a supplier was contacted — all three are currently false.
2. Update the assertion in `frontend/src/pages/services/__tests__/ServicesRfqNew.send.test.tsx` (line ~149) to match the honest copy — **update it, don't delete it.** That assertion is the guard that keeps the wording honest.
3. `cd frontend && npx vitest src/pages/services && npx tsc --noEmit`.

**Constraint:** this is honesty-only. Do NOT add any *new* capability claim (that would need the loop fix first). Removing a false claim needs no sign-off; adding one does.

Report: branch · SHA · PR · test output.

---

## TASK 3 — Fix the CI collection landmine *(Notion: "test_budget_summary_honest.py fails collection")*

**Branch:** `fix/budget-summary-test-collection`

**Problem:** `backend/tests/test_budget_summary_honest.py` fails at **collection** (not assertion) with an AttributeError — Claude Code hit it during the AIQ-1661 session and had to run individual test files to work around it. It's a collection-time error, so it aborts pytest for that path. It's currently isolated on the AIQ-1527 branch (`a34a2088`) but will merge and take the breakage to `main`, turning `backend-tests` red for every open PR at once.

**Do:**
1. `cd backend && pytest backend/tests/test_budget_summary_honest.py --collect-only` — read the exact AttributeError and the symbol it can't resolve.
2. That symbol was almost certainly renamed/moved by AIQ-1527 (the "stop reporting within_budget having compared nothing" change). Find its current home in `backend/app/services` (budget-summary path).
3. Update the import/attribute reference in the test so it collects.
4. Run the file — fix any now-visible assertion drift against the current function shape.
5. `cd backend && pytest --collect-only` across the suite → confirm zero collection errors remain.

**Constraint:** do NOT delete the test to make collection pass — it guards the AIQ-1527 `within_budget` regression. Update the reference; preserve the coverage.

Report: branch · SHA · PR · `pytest --collect-only` output (should show zero errors).

---

## Reporting

Per task: `branch · commit SHA · PR URL · tsc/pytest result · anything blocked`.

If a task is blocked, stop and report it — don't work around it. No commit SHA on a named branch = BLOCKED, not done.

**Do NOT touch** — out of scope for all three: the RFQ loop rewire (that's the Red P1, needs decomposition + human gate), the Stripe/paywall branches (separate agent, `feat/stripe-payment-checkout`), and `OUTBOX_DISPATCH_CRON_ENABLED` (leave unset).

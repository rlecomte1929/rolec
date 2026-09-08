# Claude Code — remaining actions (paste verbatim from repo root)

You are in `rolec` (React/Vite + FastAPI + Supabase, deploys to Render from `main`). Base every task off current `main` (`646bd682` or newer).

**Five tasks. Each = its OWN branch off `main` + its OWN PR. Do NOT combine. Do NOT use `fix/td-qa-services-batch-0719`.** Read `CLAUDE.md` first.

Order: **Task 2 first (launch gate), then 1, 3, 4, 5.**

Per-PR: `cd frontend && npx tsc --noEmit` and `cd backend && pytest` (or scoped file). One atomic commit per task via Git Trees API. **No commit SHA on a named branch = BLOCKED, not done.**

---

## TASK 1 — Merge the currency fix (already built)
PR **#1620**, branch `fix/staged-fixture-currency` (`4ede38a9`, AIQ-1661). Confirm it rebases clean on `main`, CI green (`test_fx_service.py` + `test_test_drive_provision.py`), **merge**, report the merge SHA. Nothing to build.

---

## TASK 2 — RFQ confirmation copy (⭐ launch gate) — Notion "RFQ confirmation falsely tells the employee…"
**Branch:** `fix/rfq-confirmation-copy`

`frontend/src/pages/services/ServicesRfqNew.tsx:346` shows: *"Request recorded — your HR team can see the providers you picked and will follow up."* **This is false** — DB-proven: no HR surface reads the canonical `rfqs` table, and `rfq_recipients.token_hash` is NULL for all recipients (no supplier contacted). The file already has two prior honesty fixes to this same string (AIQ-1515, AIQ-1523).

**Do:** rewrite the confirmation (line ~346 + sibling ~334) to say only what's true — *request recorded, on your roadmap*. Remove "your HR team can see the providers you picked," "will follow up," and any implication a supplier was contacted. Update the assertion in `__tests__/ServicesRfqNew.send.test.tsx:~149` to match (update, don't delete). **Do not add any new capability claim.** `npx vitest src/pages/services && npx tsc --noEmit`.

---

## TASK 3 — CI collection landmine — Notion "test_budget_summary_honest.py fails collection"
**Branch:** `fix/budget-summary-test-collection`

`backend/tests/test_budget_summary_honest.py` fails at **collection** (AttributeError) — currently on the AIQ-1527 branch (`a34a2088`), will red-line CI for all PRs when it merges.

**Do:** `pytest backend/tests/test_budget_summary_honest.py --collect-only`, read the unresolved symbol (renamed/moved by AIQ-1527's `within_budget` change), fix the import/attribute reference in the test, fix any assertion drift. **Do not delete the test** (it guards the AIQ-1527 regression). Confirm `pytest --collect-only` shows zero errors suite-wide.

---

## TASK 4 — Taxonomy cleanup — Notion "2 mislabelled living_areas suppliers"
**Branch:** `fix/living-areas-supplier-taxonomy`

Two `directory_import` rows are miscategorised `living_areas` (they dodged `cleanup_la_supplier_shells` by lacking the `la-` id prefix):
- `6236220c-b96a-4e9b-88ba-dcbf4d6ff862` NestFinders Europe
- `a1e80a3f-3049-48a8-80d3-b50d25f9b68a` BerlinReloc GmbH

`living_areas` is advisory (renders from static/geo, not suppliers), so these are invisible to testers — taxonomy hygiene only.

**Do:** write a cleanup **migration** keyed on `service_category='living_areas'` (not the `la-` prefix). Re-categorise both to `housing_agencies` (prefer re-map over delete — preserves the vendor record); BerlinReloc → add `country_code='DE'`. Idempotent DDL, committed. **Never `apply_migration` to prod** — the operator applies out-of-band. Verify: `SELECT count(*) FROM supplier_service_capabilities WHERE service_category='living_areas'` → 0.

---

## TASK 5 — Abandon `feat/housing-neighborhood-p01` (triage pre-done)
**Cowork already verified this branch is fully superseded** — 415 commits stale (base 2026-07-01), and every Phase 0–3 feature it adds is already on `main` via PRs #1604/#1615/#1617/#1618:
- `commute_accuracy_eval.py` — **byte-identical** on main
- `geo.py` — **zero** public functions on the branch that main lacks
- `HousingNeighborhoodMap.tsx`, `schools_nearby.py`, `plugins/living_areas.py` — feature-present on main

**Do:** one confirmation pass — `git log origin/main..origin/feat/housing-neighborhood-p01 --oneline` (the 5 commits) and spot-check that main has the features. If confirmed superseded (expected), **delete the remote branch** and record "abandoned — fully superseded by #1604/#1615/#1617/#1618." **No cherry-pick, no port, no SHA needed.** If — against expectation — you find a genuinely missing capability, stop and report it instead of deleting.

---

## Out of scope (do NOT touch)
- **RFQ loop rewire** — Red, Needs Decomposition, human-gated. Not this batch.
- **Stripe/paywall branches** (`feat/stripe-payment-checkout`, `feat/stripe-payments`) — separate agent, Red.
- `OUTBOX_DISPATCH_CRON_ENABLED` — leave unset.

## Report (all tasks)
Per task: `branch · commit/merge SHA · PR URL · tsc/pytest result · anything blocked`. Task 5 may report "abandoned, no SHA" — that is a valid complete result.

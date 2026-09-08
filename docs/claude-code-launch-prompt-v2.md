# Claude Code — launch prompt (paste verbatim from repo root)

---

You are working in the `rolec` repository (ReloPass: TypeScript/React + Vite frontend, Python/FastAPI backend, Supabase/Postgres, deploys to Render from `main`). Base all work off the current `main`.

There are **four tasks**. Each gets its **own branch and its own PR**. Do **not** combine them. Do them in the order given. Stop and report after each PR rather than chaining.

Read `CLAUDE.md` at the repo root before starting — the hard rules below are summarised from it.

## Non-negotiable repo rules

1. **Dual router registration.** Any new or changed router must be registered in **BOTH** `backend/main.py` AND `backend/app/main.py`. Render boots `uvicorn backend.main:app`; a router registered only in the modular app returns **405 in production** (this has caused three incidents). After any router change, verify:
   ```bash
   python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<prefix>' in r.path))"
   ```
2. **New `public` table** needs `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + at least one policy + `REVOKE ALL ON ... FROM anon`. (SEC-002 exposed 8 tables of PII this way.)
3. **Never apply a migration.** Commit `supabase/migrations/<timestamp>_<name>.sql` with idempotent DDL; the operator applies it out-of-band. Never write to `supabase_migrations.schema_migrations`.
4. **Never log raw user input** — use `safe_log_text()` from `backend/app/services/pii_masker.py`.
5. Before every PR: `cd frontend && npx tsc --noEmit` and `cd backend && pytest`.
6. One atomic commit per task. A task is not done without a real commit SHA on a named branch.

---

## TASK 1 — Merge the outbox recipient allowlist (do this first)

**Branch already exists:** `5f3baf0e` — `safety(outbox): hard recipient allowlist guard on notification_outbox dispatcher`.

Context: `main` has a GitHub Actions cron that drains the notification outbox every 15 minutes and can email HR. On `main`, `notification_outbox_dispatch.py` sends to whatever `to_email` is on the row — no allowlist. The guard on `5f3baf0e` fixes this (fail-closed `@probe.test` default, `@domain` normalisation, skipped rows logged). It just hasn't been merged.

**Do:**
1. Rebase `5f3baf0e` onto current `main`, resolve any conflicts.
2. `cd backend && pytest backend/tests/test_notification_outbox_dispatch.py` — confirm green.
3. Open the PR.
4. **Do NOT set or enable `OUTBOX_DISPATCH_CRON_ENABLED`.** Merging the guard is not the same as enabling the cron — that stays a separate manual decision.
5. Report: branch, commit SHA, PR URL.

---

## TASK 2 — Fix the test-drive provisioning campaign default

**Branch:** `fix/provision-campaign-default`

**Problem:** the SURVEY endpoint was fixed (AIQ-1639, commit `bf725c34`) so an absent campaign no longer defaults to the live cohort — verified working. But the **PROVISION** endpoint has the same hardcoded `insead-2026` fallback and was never touched. Hitting `/test-drive` with no `?campaign=` still creates a `test_session` under `insead-2026`, contaminating the live cohort. This has required three manual purges.

**Do:**
1. In `backend/app/routers/test_drive.py`, find the provision handler (~line 235) and its campaign resolution.
2. When no campaign is supplied, store the session with campaign **NULL** (or an explicit `'unattributed'` value) — never `'insead-2026'`.
3. Keep explicit `?campaign=insead-2026` working — the real cohort link legitimately passes it. **Only the silent fallback changes.**
4. Mirror the exact pattern AIQ-1639 used on the survey handler (`bf725c34`) — read that diff first.
5. Add a regression test asserting the provision path never writes `'insead-2026'` unless explicitly supplied.
6. `grep` the test-drive router — confirm no hardcoded `'insead-2026'` literal remains as a fallback.

**Acceptance:** provision with no campaign → session campaign is NULL/unattributed; provision with `?campaign=insead-2026` → still `insead-2026`; provision with `?campaign=qa-x` → `qa-x`.

Report: branch, SHA, PR, test output.

---

## TASK 3 — Fix vendor-seeding intermittency

**Branch:** `fix/vendor-seeding-intermittency`

**Problem:** AIQ-1651 (commits `1355d7e2` + follow-up `2031a050`) seeds `company_vendor_selections` at test-drive provisioning so testers see a supplier shortlist. But it only fires for ~63% of companies (measured: 5 of 8 post-fix). The other third reach Services and see an empty marketplace.

**Do:**
1. In `backend/app/routers/test_drive.py`, examine the vendor-selection seeding added in AIQ-1651 and its follow-up (`2031a050`, "stamp corridor destination onto wizard_cases so city-scoped recs populate").
2. Diagnose why it fails ~1 in 3. Likely candidates: a race with case/`wizard_cases` creation, a corridor whose destination isn't in the seed set, or an exception being swallowed.
3. **Any seeding failure must emit a structured error** naming company id + corridor + exception — never a swallowed warning. The sibling `_seed_default_published_policy` swallows its exceptions and that silence directly caused a P0 earlier. Do not repeat it.
4. **Do NOT weaken or bypass the `company_vendor_selections` filter in `backend/app/recommendations/router.py`.** That filter is the security control that prevents unvetted suppliers (`platform_vetting_status='approved'`, `vetted_by=NULL`) reaching customers. The defect is that provisioning under-populates the curation, not that the filter exists.
5. Add a test: 10 fresh test-drive provisions → all 10 have `company_vendor_selections` rows for their corridor destination.

**Acceptance:** 10/10 provisioned test-drive companies get vendor selections; a forced failure logs a structured error and provisioning still completes.

Report: branch, SHA, PR, test output.

---

## TASK 4 — Staged-provisioning fixture (P0 — the biggest, do last)

**Branch:** `feat/test-drive-staged-provisioning`

**Problem:** the full cohort path (provision → HR case → assign → employee sign-in → Services → recommendations → shortlist) costs ~40–45 browser actions against a ~50 ceiling, so QA cannot reach the RFQ-submit step at all. Two runs died at 45/50 and 40/50 without ever submitting an RFQ. A QA-only fixture that returns a session already at a named stage fixes this permanently.

**Do:**
1. Add a `stage` parameter to the provision path:
   ```
   POST /api/test-drive/provision?stage=<stage>&campaign=qa-*&corridor=FR_NO
   stage = credentials      (current default — unchanged)
         | case_created     (+ company, published policy, vendor selections, case created + assigned)
         | intake_complete  (+ intake submitted)
         | roadmap_ready    (+ roadmap generated, Services reachable)
         | shortlist_ready  (+ Recommendations loaded, shortlist non-empty)  ← PRIORITY
   ```
2. **`shortlist_ready` is the one that matters most** — it must return credentials for a session whose employee is at Review & budget with a non-empty shortlist, so a tester can click **Request quotes** in under 5 actions.
3. **Reuse the real provisioning/seeding/shortlist code paths.** Do NOT insert rows directly — a fixture that fabricates state tests a fiction and is worse than no fixture. Each stage must call the same code an ordinary session would.
4. **Gate it hard:** only reachable when `RELOPASS_TEST_DRIVE_ENABLED` is truthy AND the campaign matches `qa-*`. It must be rejected for `insead-2026` and for any `is_test=false` company.
5. Register the route in **BOTH** `backend/main.py` and `backend/app/main.py`; verify with the routes check above.
6. Tests: `stage=shortlist_ready` → employee lands at Review & budget with a shortlist; the endpoint is rejected when `RELOPASS_TEST_DRIVE_ENABLED` is false; rejected for a non-`qa-*` campaign; and one seeded vs one manually-walked session produce equivalent DB rows.

**Acceptance:** signing in to a `stage=shortlist_ready` session and clicking Request quotes works in under 5 actions; the gate rejects disabled/non-qa/insead cases.

Report: branch, SHA, PR, test output, and the route-registration check output.

---

## Reporting format (all four)

For each task: `branch · commit SHA · PR URL · tsc/pytest result · route-check output where relevant · anything blocked`.

If any task is blocked (a token scope, a failing precondition), stop and report it — do not work around it. If you cannot produce a commit SHA on a named branch, the task is BLOCKED, not done.

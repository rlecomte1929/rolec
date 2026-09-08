# Next tasks — two prompts, in order

**Base:** `main @ ecdc90a4` · **Date:** 2026-07-21

**Prompt A goes to Claude Code** (repo work — it commits natively; Audos has failed to land commits ~10 times via the workspace mirror).
**Prompt B goes to Audos** (browser work) — **only after A has shipped.**

---
---

# PROMPT A — Claude Code

Copy everything below into Claude Code from the repo root.

---

You are working in `rlecomte1929/rolec`. Base off `main @ ecdc90a4`. Two tasks, **separate branches, separate PRs** — do not combine them.

## Repo rules that bind (violating any of these ships an incident)

- **Routers must be registered in BOTH `backend/main.py` AND `backend/app/main.py`.** Render boots `uvicorn backend.main:app`; registering only in the modular app returns **405 in production**. This has caused three incidents. Verify with:
  `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<prefix>' in r.path))"`
- **Any new `public` table** needs `ENABLE ROW LEVEL SECURITY` + at least one policy + `REVOKE ALL FROM anon`. This caused SEC-002 (8 tables, GDPR-scope PII).
- **Never apply a migration.** Commit the file with idempotent DDL; the operator applies out-of-band. Never write to `supabase_migrations.schema_migrations`.
- **Never log raw user input** — use `safe_log_text()` from `pii_masker.py`.
- Run `cd frontend && npx tsc --noEmit` and `cd backend && pytest` before opening either PR.
- One atomic commit per logical change. Never one file per commit.

---

## TASK A1 — Merge the outbox recipient allowlist ⚠️ do this first

**Branch to merge:** `5f3baf0e` — *"safety(outbox): hard recipient allowlist guard on notification_outbox dispatcher"*

**Why it's first:** `518bf11c` shipped a GitHub Actions cron that drains the notification outbox every 15 minutes and emails HR on policy exceptions. `notification_outbox_dispatch.py` on `main` sends to whatever `to_email` is on the row — **no allowlist, no domain restriction, no dry-run.** The only thing preventing real sends today is that `vars.OUTBOX_DISPATCH_CRON_ENABLED` is unset. A feature flag is not a safety control, and a cohort launch is imminent.

The guard on that branch is already correct — fail-closed `@probe.test` default, empty allowlist skips everything, `@domain` normalisation blocks the `evil@notprobe.test` suffix bypass, skipped rows marked terminal and logged, 86 lines of tests.

**Do:**
1. Rebase `5f3baf0e` onto `main @ ecdc90a4`, resolve any conflicts, open the PR.
2. Confirm `cd backend && pytest backend/tests/test_notification_outbox_dispatch.py` passes.
3. Report the PR URL and the commit SHA.
4. **Do NOT set `OUTBOX_DISPATCH_CRON_ENABLED`.** Merging the guard does not mean enabling the cron — that stays a separate, deliberate decision.

---

## TASK A2 — Seed vendor selections for test-drive companies

**Notion:** *"Test-drive provisioning seeds a policy but no vendor selections"* (P1, Layer: API, 🟡 Yellow)
**Branch:** `feat/test-drive-vendor-seeding` off `main @ ecdc90a4`

**Problem:** Employee Services → Recommendations filters ranked items through HR's `company_vendor_selections` (`backend/app/recommendations/router.py` ~line 320). Test-drive provisioning seeds a published policy via `_seed_default_published_policy` but **never seeds vendor selections**. Measured: of 65 test-drive companies created in 14 days, **exactly 1** has any. So ~98% of testers see `Movers (0)` and a banner reading *"Your HR is finalizing providers for this category."* No suppliers → no shortlist → **Request quotes** never enables → `POST /api/rfqs` is unreachable.

**⚠️ Do NOT weaken or bypass the `company_vendor_selections` filter.** That filter is *correct* — it is the control that stops nine auto-approved suppliers (`platform_vetting_status='approved'`, `vetted_by=NULL`) reaching customers. The defect is that provisioning never populates the curation, not that the curation exists.

**Do:**
1. In `backend/app/routers/test_drive.py`, add vendor-selection seeding alongside `_seed_default_published_policy` (~line 210, called ~line 313). Scope it to the corridor's destination country.
2. Read `backend/app/recommendations/criteria_builder.py:234` first — curation reads `company_vendor_selections` **via `service_catalog_items.supplier_id`**, not the retired `company_preferred_suppliers`. Seed the shape the filter actually reads.
3. **Failures must emit a structured error, never a swallowed warning.** `_seed_default_published_policy` swallows its exceptions today and that silence directly caused a P0 on this same code path. Do not repeat it.
4. Add a test asserting a freshly provisioned test-drive company has `company_vendor_selections` rows for its corridor destination.

**Acceptance:** provision on `?campaign=qa-seed&corridor=FR_NO` → employee opens Services → Preferences → Recommendations **without completing intake** → at least one category shows a non-zero supplier count → a shortlist can be built → **Request quotes** enables → the "HR is finalizing providers" banner does not appear for seeded categories.

**Report:** branch · commit SHA · PR URL · test output · the route-registration check if you touched any router.

---
---

# PROMPT B — Audos (hold until A1 and A2 are merged and deployed)

Copy everything below into Audos **only once vendor seeding is live.**

---

## CARD SMOKE-1 — the cohort path, end to end

**This is the path an INSEAD tester will actually walk.** Nobody has completed it with working vendors. It supersedes cards Q2/Q3 as the next run.

**Campaign:** `qa-smoke1` · **Corridor:** `FR_NO` · **Budget:** ~35 · **Fresh session.**

### Steps

1. `https://relopass.com/test-drive?campaign=qa-smoke1&corridor=FR_NO`. Decline the analytics banner. First name `Smoke1`.
2. **Capture both credential pairs immediately.** Non-ASCII password → record and stop.
3. Sign in as **HR** → create a case → assign to the employee. **Record both ids, labelled** (URL id = assignment; any separate case id).
4. Sign in as **EMPLOYEE**, fresh context. Open **Services**. **Do not complete intake.**
5. **Preferences** — confirm: no *"Destination missing"* banner · origin reads **Paris** · **Get recommendations** enabled.
6. ⭐ **Recommendations** — this is the new part. Record **every supplier offered, by name, per category**, and the count per category chip.
   - **Watch specifically for:** DNB Bank · Nordea Norway · SpareBank1 · Crown Relocations (Norway) · AGS Movers Norway · Expat Relocation Norway · Immigrationlawyer.no · PwC Norway · BDO Norway.
   - **Do not approve anything.**
7. Build a **shortlist** (prefer movers or banks). Continue to **Review & budget**.
8. Record the **estimate currency** — expect **NOK** on an Oslo case (this confirms F12 stays fixed).
9. Click **Request quotes** → complete the minimum fields → submit. Record: confirmation? RFQ reference? **Is a supplier magic link visible anywhere in the UI** (copy-link control, invite list, dispatch log)? If links are email-only, say so explicitly.
10. Return to `/test-drive?campaign=qa-smoke1&corridor=FR_NO`. Confirm the session **survived navigation** (AIQ-1640) — credentials, completion CTA and survey link all present.
11. Click **I've completed my test** → complete the survey → submit. Record the thank-you state.

### Rules

Click custom controls by coordinate, never by ref · country fields: use the dropdown (the autocomplete fix shipped as AIQ-1643 — if typing now works, record that as a confirmed fix) · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding, not something to route around.

### Report block

```
CARD: SMOKE-1         DATE: ____
CAMPAIGN: qa-smoke1   CORRIDOR: FR_NO
SESSION LABEL: ____   ASSIGNMENT ID: ____   CASE ID: ____
BUDGET USED: __/50

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

STEP-BY-STEP:
  5. Preferences gate clear (no destination banner, origin=Paris)?   ____
  6. SUPPLIERS OFFERED per category (names + counts):                ____
     ⭐ Any of the 9 Norway suppliers?                                ____
  7. Shortlist built?                                                ____
  8. Estimate currency (expect NOK):                                 ____
  9. RFQ submitted? ref: ____   Supplier link visible in UI? ____
 10. Session survived navigation (AIQ-1640)?                          ____
 11. Survey submitted, thank-you rendered?                            ____

🔴 CRITICAL (report first, stop): ____

FOR COWORK — DB VERIFICATION:
  Tables: rfqs / rfq_items / rfq_recipients (expect the write HERE, not rfq_requests)
          survey_responses (expect campaign='qa-smoke1', non-null session_id + corridor_id)
          company_vendor_selections (expect seeded rows for this company)
  Identifiers: ____

ARTIFACTS TO PURGE (list ALL): ____

BLOCKED BY: ____
```

**After SMOKE-1, hold.** Cowork runs the DB half and decides whether the cohort is ready to launch.

---
---

## Sequencing

```
A1 merge safety guard  ─┐
A2 vendor seeding      ─┴─►  deploy  ─►  B: SMOKE-1  ─►  Cowork DB check  ─►  cohort go/no-go
```

**Not in this round, deliberately:** the persistence design decision (yours — Option C recommended, gates the over-cap chain), the AIQ-1631 direction call, the staged-provisioning harness, and Stripe. None is cohort-blocking.

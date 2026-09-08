# Claude Code — two P1 launch blockers (paste verbatim from repo root)

You are in `rolec` (React/Vite + FastAPI + Supabase, deploys to Render from `main`). Base off current `main`.

**Two P1s from RUN 004. Each = its OWN branch off `main` + its OWN PR. Do NOT combine. Do NOT use `fix/td-qa-services-batch-0719`.** Read `CLAUDE.md`.

**Both share a discipline rule that is not optional:** these are a production auth path and a revenue gate. **REPRODUCE with the exact request/response captured BEFORE changing code. Do not guess-fix.** Neither Cowork nor the browser lane could see the failing payloads — you must.

Per-PR: `cd frontend && npx tsc --noEmit` and `cd backend && pytest`. One atomic commit. No commit SHA on a named branch = BLOCKED, not done.

---

## TASK 1 — RFQ shortlist persist intermittently 400s
**Notion:** "POST /api/cases/{id}/services-state intermittently 400s on 'Add to package'"
**Branch:** `fix/services-state-persist-400`

### What's proven (DB-verified, do not re-litigate)
Employee builds a 6-item package in the UI → **4 of 6 "Add to package" writes return HTTP 400**; only 2 persisted. Cowork confirmed: `services_state` row exists for the case but `state_json->'shortlist'` has **only 2 entries**. Incomplete shortlist → the "Request quotations" button (gates on `hasShortlist`) never enables → the entire employee-led RFQ loop is unreachable. It's **intermittent** — that's why V3 succeeded (all 6 landed) and RUN 004-B failed (2 of 6). Real cohort users hit this.

### Reproduce first
Provision a staged session (`stage=roadmap_ready&campaign=qa-fix1&corridor=FR_NO` via `POST /api/test-drive/provision-staged`), sign in as employee, add 6 items to the package, and **capture the request URL + body + 400 response** for a failing write. Confirm the count that persists in `services_state`.

### Root-cause candidates (in likely order)
- `put_services_state` (`backend/app/routers/services_state.py`, POST `/api/cases/{case_id}/services-state`) raises **413/404 in its own body but NOT 400** — so the 400 originates *before* the handler: `require_case_access`, `_org_id_for_case`, or Pydantic validation of `ServicesStatePut`.
- ⭐ **Prime suspect — case-vs-assignment id (F16 lineage):** does the frontend (`frontend/src/features/services/ServicesFlowContext.tsx` → `frontend/src/api/servicesState.ts`) POST to `/api/cases/{caseId}/services-state` with the **case id** or the **assignment id**? If some calls pass the wrong id, `require_case_access` rejects *those* while others succeed → exactly this intermittent, partial failure.
- Race: rapid successive saves colliding (the save is debounced/batched of the whole state).

### Fix
Align the caller to send the id `require_case_access` authorises on, and/or make the persist tolerant of concurrent writes. **Do NOT weaken `require_case_access`** to silence the 400 — fix the caller/validation.

### Acceptance
6 rapid "Add to package" clicks → `services_state.shortlist` has **6** entries, **zero 400s** → "Request quotations" enables and routes to `/services/rfq/new`. Add a test persisting a multi-item shortlist and asserting all items land.

### Report
branch · SHA · PR · **the captured 400 request/response** · root cause · shortlist now persists 6/6 · test output.

---

## TASK 2 — Roadmap paywall bypass on direct URL load 🔴 revenue gate
**Notion:** "Roadmap paywall bypass on direct URL load"
**Branch:** `fix/roadmap-paywall-direct-load`

### What's proven (DB-verified)
Unpaid case: **SPA nav gates correctly** (€800 paywall, 402), but a **direct/full-page URL load renders the full roadmap** despite the server returning 402. The server is CORRECT — `access_tier='free'`, no leak, `case_addons=0`. This is a **client render-gate** bug: the page gates on `roadmapUnlocked` from `GET /api/payment/status/{id}` (a separate boolean), **not** on the authoritative roadmap-data 402. On the direct-URL path that boolean came back `true` for the unpaid case.

**Key detail:** the direct URL carried the **assignment id** (`fa6cec1d…`), not the case id (`81682d1b…`). `getPaymentStatus(assignmentId)` most likely can't resolve a paid case and **fails open to `roadmap_unlocked=true`.**

### Reproduce first
Provision `stage=roadmap_ready&campaign=qa-fix2&corridor=FR_NO`, sign in as employee, do **not** pay. Then load `/employee/case/{id}/roadmap` by **direct URL** — once with the case id, once with the assignment id — and **capture the `GET /api/payment/status/{id}` request + response** for each. Confirm which id fails open.

### Fix (must fail CLOSED)
1. Gate the roadmap render on **authoritative server enforcement** — the roadmap-data 402 (or a fail-closed entitlement check) — not the separate `payment/status` boolean. Files: `frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx` (render gate ~lines 164-245).
2. Make `GET /api/payment/status/{id}` (`backend/app/routers/payment.py`) return `roadmap_unlocked=false` for **any id it cannot resolve to a paid case**, including an assignment id. Never fail open. Handle the case-vs-assignment id explicitly.
3. **Err toward showing the paywall on any ambiguity** — a false lock is recoverable, a free €800 roadmap is lost revenue.

### Acceptance
Unpaid case, direct URL load (both case id AND assignment id) → **paywall renders**, not the roadmap. SPA nav still gates. Paid case still unlocks on both paths. `GET /api/payment/status` with an unknown/assignment id → `roadmap_unlocked=false`. Add a test: unpaid case, direct-load render = paywall.

### Report
branch · SHA · PR · **the captured `payment/status` request/response** confirming the fail-open · which id failed · fix now fails closed · test output.

---

## Shared context both tasks should note
Both P1s trace to the **same recurring case-vs-assignment id confusion (F16 lineage)** — a persist call and an entitlement check each behaving differently depending on which id the client passes. Worth checking whether a shared helper should canonicalise "case id vs assignment id" once, rather than each surface handling it ad hoc. Flag it if you see the pattern; don't scope-creep the fix.

## Out of scope (do NOT touch)
- The NL_SG movers-rendering P2 (separate ticket).
- The RFQ HR-loop segment (blocked on Task 1 — will re-test after).
- Stripe checkout / webhook flow itself (works — this is the *client gate* only).
- `OUTBOX_DISPATCH_CRON_ENABLED` (leave unset).

## Reporting
Per task: `branch · SHA · PR · captured request/response · root cause · test output · anything blocked`. Reproduce-with-capture is a required deliverable, not optional — a fix without the captured evidence is not accepted for either of these.

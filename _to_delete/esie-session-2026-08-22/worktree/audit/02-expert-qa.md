# Expert Review — QA (Report-Only)

**Reviewer lens:** QA tester probing the live system + static analysis. **Report-only mode** — no fixes attempted.
**Method:** Live HTTP probes against `localhost:8000`/`:3000`, backend log review, static checks for common bug-class patterns. Full driven walkthroughs per persona (login, complete intake, file upload, etc.) require an authenticated session; flagged as Phase 3 follow-up.

**Composite score: 6.0 / 10**

What would make it a 10:
- Clean startup (no warnings, no aborted transactions)
- All console.log/debug paths removed from production code
- Critical runtime endpoints have explicit auth tests in CI
- Per-persona E2E flow tests in CI (employee intake, HR case creation, admin catalog edit)

---

## Findings (live probes)

### QA-1 [P0] — `InFailedSqlTransaction` warning on every startup
**Source:** `/tmp/relopass-backend.log`, repeated on each reload
```
WARNING:backend.main:startup_step=ensure_initialized status=error elapsed_ms=4160
InternalError: (psycopg2.errors.InFailedSqlTransaction) current transaction is aborted, commands ignored until end of transaction block
[SQL:
    CREATE INDEX IF NOT EXISTS idx_sqlite_pc_benefits_version
    ON policy_config_benefits(policy_config_version_id)
]
```
**Why P0:** An earlier DDL statement in the same transaction failed silently; subsequent statements (CREATE INDEX here) cascade-fail. The app continues because the failure is caught at a higher level (the WARNING — not an ERROR — confirms swallowing). This is exactly the "swallow errors silently" pattern called out elsewhere. Hidden DB-schema drift is the *biggest* operational debt class in this codebase per `MEMORY.md`.
**Reproducer:** `source .venv/bin/activate && uvicorn backend.main:app --reload --port 8000` → warning fires within 4s.
**Fix direction:** identify the earlier failing statement in `db.ensure_initialized` (called from `main.py:324`), surface as ERROR (not WARNING), and either retry on a fresh transaction or fail-fast with a clear message.

### QA-2 [P1] — Backend route table has 1 known latent unauth handler shadowed by compat
**File:** `backend/app/routers/cases.py:101` (`get_case`) — no `Depends(get_current_user)`.
**Why P1 not P0:** Live probe `curl /api/cases/X` returns `401 Not Authenticated`. Investigation shows `backend/routes/compat.py:93` (mounted at `main.py:565`, one line before `cases_router` at `:566`) shadows this route AND enforces auth. So the unguarded handler is **unreachable today** but would become reachable if compat is removed.
**Risk timeline:** depends on compat-layer deprecation roadmap (which is not documented).
**Fix:** Add `Depends(get_current_user)` to `cases.get_case` defensively. Add CI route-enumeration test that asserts every GET handler either declares auth or is on an explicit allowlist.

### QA-3 [P1] — Frontend SPA serves `text/html` to every API-shape URL
Vite dev server's catch-all returns the SPA HTML for any path it doesn't know. This is intentional for client-side routing but creates two QA risks:
- Typos in API URLs return HTTP 200 + HTML rather than 404 — masks failures in tests.
- Backend-only paths accidentally requested from the frontend will succeed with bogus content.

Not a bug in the framework, but a class of QA test (assert content-type matches expected) that should be on the CI list.

### QA-4 [P1] — 19 `console.log/error/debug` paths in production code
Per the full-stack audit. Specific files:
- `HrCaseSummary.tsx:174` — `console.debug('RPC transition_assignment: HR_REOPEN'...)`
- `HrDashboard.tsx:179` — `console.error('[Assign failed]'...)`
- `ProvidersPage.tsx:182, 241` — `console.error('[services] load/save error'...)`
- `AdminMessages.tsx:292, 394, 406` — `console.error(e)` callbacks
- `HrAssignments.tsx:355` — `console.error(e)` in onClick
- `CaseWizardPage.tsx:348` — `console.debug('Wizard defaults...')`

**Why P1:** They leak diagnostic detail to user devtools; they're not wired to a real error-reporting service (Sentry/Datadog/etc.); they're noise during real debug sessions.
**Fix:** Replace each with a structured logger that no-ops in prod or pipes to a real service.

### QA-5 [P2] — Backend warns on every startup about LibreSSL
```
NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'
```
**Why P2:** macOS-Python-3.9 quirk; not production-relevant (Render uses Python 3.11 + OpenSSL). Annoying noise on dev machines.
**Fix:** Either pin urllib3 to a v1.x range for local dev, or document as known-noise in CLAUDE.md.

### QA-6 [P2] — Dead pages routed but never accessible
- `HrCaseReview.tsx`, `HrReviewDashboard.tsx` not referenced in `App.tsx` or `navigation/`.
**Why P2:** Dead code in the page tree. Not a bug, but a maintenance hazard.

## Per-persona QA assessment (static + log-based)

| Persona | Flow status | Notes |
|---|---|---|
| **Employee — intake (legacy)** | Untested live | `EmployeeJourney.tsx` has the W1 UUID surface; static analysis says it will work mechanically. Real failure mode: copy confusion, not crashes. |
| **Employee — intake v2** | Untested live | `features/platform-v2/intake/EmployeeIntakePage.tsx` is 1,439 LOC — needs E2E walkthrough |
| **Employee — Dashboard** | Untested live | `Dashboard.tsx` empty state is bare; tab pattern lacks ARIA |
| **HR — Command Center** | Static read clean | Best-built surface; uses antigravity primitives + hrAPI |
| **HR — Case Detail** | Untested live | Raw status codes leak; icon-only buttons; needs interactive a11y test |
| **HR — Policy management** | Untested | `HrPolicy.tsx` is 1,064 LOC — needs walkthrough |
| **Admin — Catalog** | Untested | 13 admin routers; coverage unclear |
| **Admin — A/B tests** | Bug class | Direct Supabase query bypassing API wrapper — fails if RLS missing |
| **Provider** | Untested | Provider portal UI is in AI Work Queue, not confirmed deployed |

## What this pass DID NOT cover

- Authenticated walkthroughs of any persona. Requires a seeded test user + a test session token. Recommend: create a `relopass-e2e` fixture user with predictable creds for QA runs.
- Mobile-viewport testing (responsive layout breakage)
- Real network conditions (slow 3G, offline)
- File-upload flows (passport, policy doc) — only OCR static analysis done
- Email/notification flows (case invitation, status changes)
- Cross-browser (only Chromium tested implicitly through Vite)

## Recommended next QA actions

1. **Fix QA-1 (InFailedSqlTransaction)** before next deploy — startup warnings indicate hidden DB drift.
2. **Add CI route-enumeration test** that asserts auth presence on GETs.
3. **Strip 19 console.* statements**; route through real logger.
4. **Seed a QA user** with predictable creds; build a smoke-test suite that drives one happy-path per persona.
5. **Add `make e2e` or `npm run e2e:all`** as a single entry for the suite.

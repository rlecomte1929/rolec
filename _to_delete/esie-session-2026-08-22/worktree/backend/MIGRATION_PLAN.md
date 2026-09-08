# Backend Router Migration Plan

> **Audit task**: AUDIT-C2.2
> **Branch**: `audit/stage-1-security`
> **Date**: 2026-05-26
> **Based on**: Router inventory from AUDIT-C2.1 (`backend/docs/router-inventory.md`)

---

## Current State

```
┌──────────────────────────────────────────────────────────────┐
│  Vercel / Railway / Cloud Run                                │
│                                                              │
│  ┌─────────────────────┐    ┌──────────────────────────┐    │
│  │  backend/main.py    │    │  backend/app/main.py     │    │
│  │  (legacy entry)     │    │  (target entry)          │    │
│  │                     │    │                          │    │
│  │  61 include_router  │    │  6 include_router calls  │    │
│  │  249 @app. handlers │    │  (3 exclusive, 3 shared) │    │
│  │                     │    │                          │    │
│  └─────────────────────┘    └──────────────────────────┘    │
│         ↑                              ↑                     │
│  Serving live traffic           Serving live traffic        │
│  (both entry points active simultaneously)                  │
└──────────────────────────────────────────────────────────────┘
```

### Key metrics (as of AUDIT-C2.1)

| Metric | Count |
|--------|-------|
| `include_router` calls in `backend/main.py` | 61 |
| Distinct router files in `backend/main.py` | 55 |
| Inline `@app.` route handlers in `backend/main.py` | 249 |
| Routers already in `backend/app/main.py` | 6 (3 double-mounted, 3 exclusive) |
| Remaining routers to migrate | 55 |
| Inline handlers to extract (post-Month 3) | 249 |

### Double-mounted routers (in both entry points — safe to cut from `backend/main.py` once tested)

| Router file | Domain |
|-------------|--------|
| `backend/app/routers/cases.py` | HR/employee |
| `backend/app/routers/admin.py` | admin |
| `backend/app/routers/employee_quotes.py` | employee |

### Exclusive to `backend/app/main.py` already (never in `backend/main.py`)

| Router file | Domain |
|-------------|--------|
| `backend/app/routers/pets.py` | employee |
| `backend/app/routers/support.py` | util |
| `backend/app/routers/ab_tests.py` | util |

---

## Target End-State

```
┌────────────────────────────────────────────────────────────────┐
│  backend/app/main.py  (single authoritative entry point)      │
│                                                               │
│  All routers (55 files + extracted inline handlers)          │
│  No double-mounting                                           │
│  No legacy SessionLocal usage                                │
│  No circular imports                                          │
└────────────────────────────────────────────────────────────────┘

  backend/main.py  →  empty shim or deleted
  (if kept: thin shim that just imports and re-exports the app
   object from backend.app.main for backwards-compat startup)
```

**Definition of Done**: `grep -c "include_router\|@app\." backend/main.py` returns 0 (or file is deleted). All CI route-auth-check scripts point to `backend/app/main.py`. Import smoke test passes for `backend.app.main`.

---

## Pre-conditions (must be done before Month 1 begins)

| # | Pre-condition | Owner | Status | Ticket |
|---|---------------|-------|--------|--------|
| P1 | AUDIT-A9.3 service tree consolidation complete | Backend | Done / In Progress | AUDIT-A9.3 |
| P2 | Fix circular import: `mobility_context.py` imports `backend.main.get_current_user` → must move `get_current_user` to `backend.app.auth_deps` or a shared module | Backend | **TODO** | Create fix ticket |
| P3 | Extract 4 inline `APIRouter` objects from `backend/main.py` into dedicated files | Backend | TODO | See Month 0 below |
| P4 | Confirm dual-entry deployment config — both `backend/main.py` and `backend/app/main.py` reachable simultaneously | DevOps | TODO | — |

---

## Migration Timeline

### Month 0 — Pre-flight (current sprint)

**Goal**: Unblock Month 1 — no functional routes change, only structural prep.

#### 0.1 — Extract 4 inline `APIRouter` objects from `backend/main.py`

These objects are defined directly inside `backend/main.py` and cannot be imported without importing the whole file:

| Inline router | Approx line | Target file |
|---------------|-------------|-------------|
| `hr_policy_config_router` | ~L13355 | `backend/app/routers/hr_policy_config.py` |
| `admin_policy_config_router` | ~L13356 | `backend/app/routers/admin_policy_config.py` |
| `employee_policy_config_router` | ~L13357 | `backend/app/routers/employee_policy_config.py` |
| `public_policy_config_router` | ~L13358 | `backend/app/routers/public_policy_config.py` |

After extraction: replace the inline definitions in `backend/main.py` with `from backend.app.routers.X import X_router` and keep the `include_router` call unchanged. No route changes.

#### 0.2 — Fix `mobility_context.py` circular import

- Remove `from backend.main import get_current_user` from `backend/app/routers/mobility_context.py`
- Replace with `from backend.app.auth_deps import get_current_user` (or equivalent shared location)
- Verify: `python -c "from backend.app.routers.mobility_context import router"` succeeds without importing `backend.main`

#### 0.3 — Add import smoke test to CI

```yaml
# .github/workflows/backend.yml  (or equivalent)
- name: App entry-point smoke test
  run: python -c "from backend.app.main import app; print('OK')"
```

---

### Month 1 — Auth + Employee + HR (highest churn)

**Goal**: Move the 21 highest-churn and highest-risk routers out of `backend/main.py` into `backend/app/main.py`. These domains change most often and carry the most auth surface area.

#### Routers to add to `backend/app/main.py` this month

**Tier 1 — Highest Impact, Cleanest Migration**

| # | Router file | Domain | Churn | Notes |
|---|-------------|--------|-------|-------|
| 1 | `backend/app/routers/auth.py` | auth | med (7) | Clean — no blockers |
| 2 | `backend/app/routers/cases.py` | HR/employee | high (16) | Already double-mounted — just remove from `backend/main.py`; resolve SessionLocal debt |
| 3 | `backend/app/routers/hr_catalog.py` | HR | high (9) | Clean |
| 4 | `backend/app/routers/hr_coordination.py` | HR | med (4) | Clean |
| 5 | `backend/app/routers/immigration.py` | employee | med (4) | Clean |
| 6 | `backend/app/routers/exception_requests.py` | employee | med (4) | Clean |

**Tier 2 — HR Policy Cluster**

| # | Router file | Domain | Churn | Notes |
|---|-------------|--------|-------|-------|
| 7 | `backend/app/routers/policy_publish.py` | HR | low (1) | Clean |
| 8 | `backend/app/routers/policy_summary.py` | HR | low (2) | Clean |
| 9 | ~~`backend/app/routers/policy_feedback.py`~~ | — | — | ❌ REMOVED — orphaned, no callers |
| 10 | `backend/app/routers/policy_canonical.py` | HR | low (1) | Exposes 2 sub-routers (admin + read) — mount both |
| 11 | `backend/app/routers/policy_templates.py` | HR | low (1) | Clean |
| 12 | `backend/app/routers/hr_analytics.py` | HR | med (3) | Clean |

**Tier 3 — Employee Cluster**

| # | Router file | Domain | Churn | Notes |
|---|-------------|--------|-------|-------|
| 13 | `backend/routes/relocation.py` | employee | med (6) | In `backend/routes/` — consider moving to `backend/app/routers/` or add explicit import path |
| 14 | `backend/routes/relocation_classify.py` | employee | med (3) | Same as above |
| 15 | `backend/app/routers/relocation_profile.py` | employee | low (2) | Clean |
| 16 | `backend/app/routers/marketplace.py` | employee | low (2) | Clean |
| 17 | `backend/app/recommendations/router.py` | employee | med (7) | Non-standard path — add explicit import |
| 18 | `backend/app/routers/advisors.py` | employee | low (1) | Clean |
| 19 | `backend/app/routers/mobility_context.py` | employee | low (2) | **Depends on Month 0 P2 circular import fix** |

**Tier 4 — Extracted Inline Policy Config Routers** (depends on Month 0 P3)

| # | Router file | Domain | Notes |
|---|-------------|--------|-------|
| 20 | `backend/app/routers/hr_policy_config.py` | HR | Extracted in Month 0 |
| 21 | `backend/app/routers/employee_policy_config.py` | employee | Extracted in Month 0 |

**Month 1 total**: 21 routers added to `backend/app/main.py`; same 21 removed from `backend/main.py` (after smoke tests pass).

---

### Month 2 — Providers + Admin + Knowledge

**Goal**: Complete the remaining 29 router files (all ✅ Ready or ⚠️ Dual DB routers in admin/provider domains), and migrate the 2 remaining inline-extracted routers.

#### Routers to add to `backend/app/main.py` this month

**Admin cluster**

| # | Router file | Domain | Notes |
|---|-------------|--------|-------|
| 1 | `backend/app/routers/admin.py` | admin | Already double-mounted — remove from `backend/main.py`; resolve SessionLocal / Database import debt |
| 2 | `backend/app/routers/admin_catalog.py` | admin | Clean |
| 3 | `backend/app/routers/admin_mobility.py` | admin | Clean |
| 4 | `backend/app/routers/admin_resources.py` | admin | Clean |
| 5 | `backend/app/routers/admin_staging.py` | admin | Clean |
| 6 | `backend/app/routers/admin_freshness.py` | admin | Exposes 3 sub-routers — mount all three |
| 7 | `backend/app/routers/admin_review_queue.py` | admin | Clean |
| 8 | `backend/app/routers/admin_notifications.py` | admin | Clean |
| 9 | `backend/app/routers/admin_ops_analytics.py` | admin | Clean |
| 10 | `backend/app/routers/admin_workflow_analytics.py` | admin | Clean |
| 11 | `backend/app/routers/admin_collaboration.py` | admin | Clean |
| 12 | `backend/app/routers/admin_prospects.py` | admin | SessionLocal — resolve dual-DB debt |
| 13 | `backend/app/routers/admin_form_templates.py` | admin | Clean |
| 14 | `backend/app/recommendations/admin_debug.py` | admin | Non-standard path |
| 15 | `backend/app/routers/branding.py` | admin | Lazy DB import — verify works |
| 16 | `backend/app/routers/analytics.py` | admin | Clean |
| 17 | `backend/app/routers/analytics_query.py` | admin | Clean |

**Provider cluster**

| # | Router file | Domain | Notes |
|---|-------------|--------|-------|
| 18 | `backend/app/routers/providers.py` | provider | Lazy DB import |
| 19 | `backend/app/routers/hr_vendors.py` | provider | Clean |
| 20 | `backend/app/routers/suppliers.py` | provider | SessionLocal — resolve dual-DB debt |
| 21 | `backend/app/routers/hr_rfq.py` | HR | Clean |

**Infra / integration cluster**

| # | Router file | Domain | Notes |
|---|-------------|--------|-------|
| 22 | `backend/app/routers/crons.py` | infra | Clean |
| 23 | `backend/app/routers/services_state.py` | infra | Uses `_jb` — verify import |
| 24 | `backend/app/routers/integrations_personio_webhook.py` | infra | Clean |
| 25 | `backend/app/routers/integrations_personio_settings.py` | infra | Clean |
| 26 | `backend/app/routers/integrations_bamboohr.py` | infra | Clean |
| 27 | `backend/app/routers/prescreening.py` | HR | Clean |

**Util cluster**

| # | Router file | Domain | Notes |
|---|-------------|--------|-------|
| 28 | `backend/routes/compat.py` | util | In `backend/routes/` — add explicit import |
| 29 | `backend/routes/resources.py` | util | In `backend/routes/` |
| 30 | `backend/routes/hr_resources.py` | HR | In `backend/routes/` |

**Remaining inline-extracted routers** (extracted in Month 0)

| # | Router file | Domain | Notes |
|---|-------------|--------|-------|
| 31 | `backend/app/routers/admin_policy_config.py` | admin | Extracted in Month 0 |
| 32 | `backend/app/routers/public_policy_config.py` | util | Extracted in Month 0 |

**Also**: `employee_quotes` is already double-mounted — remove from `backend/main.py` this month.

**Month 2 total**: ~33 router mounts cleaned up. After Month 2, `backend/main.py` should have 0 `include_router` calls. Only the 249 inline `@app.` handlers remain.

---

### Month 3 — Inline `@app.` Handler Extraction (policy, HR, employee)

**Goal**: Extract ~155 inline `@app.` route handlers (policy + HR + employee domains) into new router files and mount them in `backend/app/main.py`.

#### Extraction plan by domain

| Domain | URL patterns | Approx count | Target file |
|--------|-------------|-------------|------------|
| policy | `/api/company-policies`, `/api/policy-assistant`, `/api/hr/policy-documents` | ~55 | `backend/app/routers/policy_inline.py` |
| HR | `/api/hr/assignments`, `/api/hr/messages`, `/api/hr/cases`, `/api/hr/policies`, `/api/hr/command-center` | ~55 | `backend/app/routers/hr_inline.py` |
| employee | `/api/employee/assignments`, `/api/employee/journey`, `/api/employee/tasks`, `/api/employee/policy` | ~45 | `backend/app/routers/employee_inline.py` |

> Note: "inline" target files are interim names — rename to domain-appropriate names once scoped (e.g. `policy_documents.py`, `hr_command_center.py`).

**Month 3 total**: ~155 inline handlers extracted. Remaining inline count in `backend/main.py`: ~94 (admin + services/rfq + dossier/infra).

---

### Month 4 — Inline `@app.` Handler Extraction (admin + remaining) + Final Cleanup

**Goal**: Extract remaining ~94 inline handlers, verify full parity, delete or replace `backend/main.py` with empty shim.

#### Extraction plan by domain

| Domain | URL patterns | Approx count | Target file |
|--------|-------------|-------------|------------|
| admin | `/api/admin/companies`, `/api/admin/people`, `/api/admin/assignments`, `/api/admin/policies`, `/api/admin/reconciliation/*` | ~60 | `backend/app/routers/admin_inline.py` |
| services/rfq | `/api/services/*`, `/api/rfqs/*`, `/api/vendor/rfqs/*` | ~20 | `backend/app/routers/services_rfq.py` |
| dossier/guidance | `/api/dossier/*`, `/api/guidance/*` | ~15 | `backend/app/routers/dossier.py` |
| infra/util | `/health`, `/`, `/debug/*`, `/api/notifications`, `/api/resources/country` | ~10 | `backend/app/routers/health.py` + `backend/app/main.py` directly |

#### Final cleanup steps

1. Replace `backend/main.py` with empty shim (or delete):

```python
# backend/main.py — SHIM: do not add routes here
# This file is kept for backwards-compat startup scripts only.
# All routes live in backend/app/main.py.
from backend.app.main import app  # noqa: F401
```

2. Update all deployment start commands from `backend.main:app` to `backend.app.main:app`.
3. Remove shim in the sprint after confirming no deployment scripts reference `backend.main:app`.

**Month 4 total**: `backend/main.py` is empty shim or deleted. Single entry point achieved.

---

## Per-Month Entry/Exit Criteria

| Month | Entry Criteria | Exit Criteria |
|-------|---------------|---------------|
| **Month 0** (Pre-flight) | AUDIT-C2.1 inventory accepted; branch `audit/stage-1-security` green | 4 inline APIRouter objects extracted to files; `mobility_context.py` circular import resolved; import smoke test added to CI; deployment config confirms dual-entry works |
| **Month 1** (Auth + Employee + HR) | Month 0 exit criteria met; `backend/app/main.py` import smoke test passing in CI | 21 routers added to `backend/app/main.py`; same 21 removed from `backend/main.py`; all existing integration tests pass; `grep -c "include_router" backend/main.py` ≤ 40 |
| **Month 2** (Providers + Admin + Knowledge) | Month 1 exit criteria met; all SessionLocal dual-DB debt documented for cleanup | All 55 router files mounted in `backend/app/main.py`; `grep -c "include_router" backend/main.py` = 0; inline `@app.` count still 249 (untouched); dual-DB routers cleaned up or formally deferred with ticket |
| **Month 3** (Inline extraction — policy/HR/employee) | Month 2 exit criteria met; route-coverage baseline captured (`openapi.json` diff) | ~155 inline handlers extracted; `grep -c "@app\." backend/main.py` ≤ 100; all extracted routes covered by smoke tests; OpenAPI spec diff reviewed and approved |
| **Month 4** (Inline extraction — admin + cleanup) | Month 3 exit criteria met; all inline domains scoped | `grep -c "@app\." backend/main.py` = 0 (or file deleted); `backend/main.py` is empty shim; all CI scripts updated; deployment config points to `backend.app.main:app`; smoke test suite green |

---

## Rollback Strategy

### Principle: parallel entry points until Month 4

Both `backend/main.py` and `backend/app/main.py` are served simultaneously throughout Months 1–3. This means rollback at any month is additive-reverse — not a destructive operation.

### Per-phase rollback

| Phase | Rollback action | Risk |
|-------|----------------|------|
| Month 0 — extraction | Revert the 4 new router files; restore inline definitions in `backend/main.py` | Low — no route changes |
| Month 1 — router adds | Remove the 21 new `include_router` calls from `backend/app/main.py`; restore them to `backend/main.py` | Low — traffic still served by `backend/main.py` |
| Month 2 — router adds | Same pattern as Month 1 | Low |
| Month 3 — inline extraction | Revert the new router files; restore inline `@app.` handlers to `backend/main.py`; remove new `include_router` calls from `backend/app/main.py` | Medium — requires coordinated revert |
| Month 4 — shim cutover | Restore full `backend/main.py`; update deployment back to `backend.main:app` | Low if shim kept; Medium if file deleted |

### Emergency rollback (any month)

```bash
# Point all traffic back to backend/main.py
# (update deployment env var or startup command)
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

As long as `backend/main.py` is not deleted, the full legacy routing is available instantly.

---

## CI Changes Required

### 1. Add import smoke test (Month 0)

```yaml
# .github/workflows/backend.yml
- name: App smoke test — backend.app.main
  run: |
    cd backend
    python -c "from backend.app.main import app; print(f'Routes: {len(app.routes)}')"
```

### 2. Update route-auth-check script paths (Month 2, after all routers migrated)

Current scripts likely scan `backend/main.py` for `include_router` to build the route list for auth checking. After Month 2 these must be updated to scan `backend/app/main.py`.

```bash
# Before (Month 0–1)
python scripts/route_auth_check.py --entry backend/main.py

# After (Month 2+)
python scripts/route_auth_check.py --entry backend/app/main.py
```

### 3. OpenAPI snapshot test (Month 3, before inline extraction)

Capture a baseline before extracting inline handlers so diffs are reviewable:

```bash
python -c "
import json
from backend.app.main import app
from fastapi.openapi.utils import get_openapi
spec = get_openapi(title=app.title, version=app.version, routes=app.routes)
print(json.dumps(spec, indent=2))
" > backend/docs/openapi-baseline.json
git add backend/docs/openapi-baseline.json
```

### 4. Update deployment startup command (Month 4)

```bash
# Old
uvicorn backend.main:app

# New
uvicorn backend.app.main:app
```

### 5. `grep` gate in CI (Month 2 onwards, tighten each month)

```bash
# After Month 2: zero include_router calls in backend/main.py
REMAINING=$(grep -c "include_router" backend/main.py || true)
if [ "$REMAINING" -gt 0 ]; then echo "FAIL: $REMAINING include_router calls still in backend/main.py"; exit 1; fi
```

---

## Open Issues / Blockers

| ID | Issue | Severity | Resolution |
|----|-------|----------|-----------|
| B1 | `mobility_context.py` circular import — imports `get_current_user` from `backend.main` directly | **Blocker for Month 1** | Fix in Month 0: move import to `backend.app.auth_deps` |
| B2 | Dual-DB pattern — 5 routers use legacy SQLAlchemy `SessionLocal` (`cases`, `admin`, `admin_prospects`, `suppliers`, and one admin_resources-style) | **Blocker for clean migration** | Schedule SessionLocal cleanup during Month 1 (cases) and Month 2 (admin, admin_prospects, suppliers) |
| B3 | 4 inline `APIRouter` objects defined inside `backend/main.py` — cannot be migrated without extraction | **Blocker for Month 1 Tier 4** | Extract in Month 0 |
| B4 | `backend/routes/` directory — 3 routers live outside `backend/app/routers/` (`compat.py`, `resources.py`, `hr_resources.py`, `relocation.py`, `relocation_classify.py`) | Medium | Move to `backend/app/routers/` or add explicit import paths during Month 1–2 |
| B5 | `backend/app/recommendations/` non-standard path — 2 routers live outside `backend/app/routers/` | Low | Add explicit import paths; optionally move in Month 2 |
| B6 | Deployment config — confirm both entry points are active simultaneously (needed for parallel rollout strategy) | **Prerequisite for Month 0 exit** | Verify with DevOps before Month 1 starts |
| B7 | `services_state.py` uses `_jb` import — verify this dep is available in `backend/app/main.py` context | Low | Check in Month 2 |

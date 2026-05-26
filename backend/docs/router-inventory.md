# Router Inventory — `backend/main.py`

> **Audit task**: AUDIT-C2.1  
> **Branch**: `audit/stage-1-security`  
> **Date**: 2026-05-26  
> **Validation**: `grep -c "include_router\|@app\." backend/main.py` → **314**  
> (61 `app.include_router` calls + 252 inline `@app.` decorators + 1 `app.add_middleware` call)  
> Of the 252 `@app.` decorators: 249 are route handlers, 3 are `exception_handler`/`middleware` decorators.

---

## 1. Summary

| Metric | Count |
|--------|-------|
| Total `app.include_router` calls in `backend/main.py` | **61** |
| Inline `@app.` route handlers in `backend/main.py` | **249** |
| `@app.` middleware/exception decorators | **3** |
| `app.add_middleware` calls | **1** |
| **Total `grep -c "include_router\|@app\."` result** | **314** |
| Routers already in `backend/app/main.py` | **6** |
| Remaining routers to migrate out of `backend/main.py` | **55** |
| Inline route handlers still to extract into router files | **249** |

> The 61 `include_router` calls map to **55 distinct router files** (admin_freshness exposes 3 sub-routers; policy_canonical exposes 2; relocation exposes 2). The inline `@app.` handlers represent ~249 routes that have never been extracted to router files — these are the long-term migration backlog beyond Month-1.

---

## 2. Main Inventory — Routers in `backend/main.py`

Legend:  
- **Churn** = commits touching the file in last 20 git log entries: high ≥ 8, med 3–7, low 0–2  
- **Migration Readiness**: ✅ Ready (uses only `auth_deps`, `database.db`) | ⚠️ Needs work (circular import or SQLAlchemy SessionLocal mix) | 🔴 Blocked (imports from `backend.main` directly)  
- **Month-1**: ⭐ = auth, employee, HR domain targets for Month-1 migration

| # | Import alias | File | Domain | Prefix/Tags | Churn (commits) | Shared Deps | Migration Readiness | Month-1 |
|---|-------------|------|--------|-------------|-----------------|-------------|---------------------|---------|
| 1 | `auth_router` | `backend/app/routers/auth.py` | auth | `tags=["auth"]` | 7 — **med** | `database.db` | ✅ Ready | ⭐ |
| 2 | `compat_router` | `backend/routes/compat.py` | util | `/api` `tags=["compat"]` | 6 — **med** | none | ✅ Ready | |
| 3 | `cases_router` | `backend/app/routers/cases.py` | employee/HR | `/api/cases` `tags=["cases"]` | 16 — **high** | `SessionLocal`, `database.db`, `auth_deps` | ⚠️ Dual DB | ⭐ |
| 4 | `case_form_pdf_router` | `backend/app/routers/case_form_pdf.py` | HR | `/api/cases` `tags=["case-form-pdf"]` | 1 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 5 | `employee_tiers_router` | `backend/app/routers/employee_tiers.py` | employee | `/api/employees` `tags=["employee-tiers"]` | 1 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 6 | `policy_publish_router` | `backend/app/routers/policy_publish.py` | HR | `/api/policy` `tags=["policy-publish"]` | 1 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 7 | `policy_summary_router` | `backend/app/routers/policy_summary.py` | HR | `/api/policy` `tags=["policy-summary"]` | 2 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 8 | `policy_feedback_router` | `backend/app/routers/policy_feedback.py` | HR | `/api/policy` `tags=["policy-feedback"]` | 1 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 9 | `crons_router` | `backend/app/routers/crons.py` | infra | `/api/crons` `tags=["crons"]` | 1 — **low** | none | ✅ Ready | |
| 10 | `exception_requests_router` | `backend/app/routers/exception_requests.py` | employee | `tags=["exception_requests"]` | 4 — **med** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 11 | `services_state_router` | `backend/app/routers/services_state.py` | infra | `tags=["services_state"]` | 2 — **low** | `database.db`, `_jb` | ✅ Ready | |
| 12 | `admin_catalog_router` | `backend/app/routers/admin_catalog.py` | admin | `/api/admin/catalog` `tags=["admin_catalog"]` | 4 — **med** | `database.db` | ✅ Ready | |
| 13 | `hr_catalog_router` | `backend/app/routers/hr_catalog.py` | HR | `/api/hr/catalog` `tags=["hr_catalog"]` | 9 — **high** | `database.db` | ✅ Ready | ⭐ |
| 14 | `providers_router` | `backend/app/routers/providers.py` | provider | `tags=["providers"]` | 2 — **low** | `database.db` (lazy import) | ✅ Ready | |
| 15 | `employee_quotes_router` | `backend/app/routers/employee_quotes.py` | employee | `tags=["quote_requests"]` | 2 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 16 | `hr_vendors_router` | `backend/app/routers/hr_vendors.py` | provider | `tags=["hr_vendors"]` | 1 — **low** | `database.db`, `auth_deps` | ✅ Ready | |
| 17 | `hr_rfq_router` | `backend/app/routers/hr_rfq.py` | HR | `tags=["hr_rfq"]` | 1 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 18 | `immigration_router` | `backend/app/routers/immigration.py` | employee | `/api` `tags=["immigration"]` | 4 — **med** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 19 | `analytics_router` | `backend/app/routers/analytics.py` | admin | `/api` `tags=["analytics"]` | 1 — **low** | `database.db` | ✅ Ready | |
| 20 | `analytics_query_router` | `backend/app/routers/analytics_query.py` | admin | `/api/analytics` `tags=["analytics-query"]` | 1 — **low** | `database.db`, `auth_deps` | ✅ Ready | |
| 21 | `mobility_context_router` | `backend/app/routers/mobility_context.py` | employee | `/api/mobility` `tags=["mobility"]` | 2 — **low** | `database.db`, imports `backend.main.get_current_user` | 🔴 Blocked (circular import) | ⭐ |
| 22 | `admin_mobility_router` | `backend/app/routers/admin_mobility.py` | admin | `/api/admin/mobility` `tags=["admin-mobility"]` | 2 — **low** | `database.db` | ✅ Ready | |
| 23 | `admin_router` | `backend/app/routers/admin.py` | admin | `/api/admin` `tags=["admin"]` | 7 — **med** | `SessionLocal`, `database.db` | ⚠️ Dual DB | |
| 24 | `admin_resources_router` | `backend/app/routers/admin_resources.py` | admin | `prefix=/api/admin` `/resources` `tags=["admin-resources"]` | 1 — **low** | `database.db` | ✅ Ready | |
| 25 | `admin_staging_router` | `backend/app/routers/admin_staging.py` | admin | `prefix=/api/admin` `/staging` `tags=["admin-staging"]` | 1 — **low** | `database.db` | ✅ Ready | |
| 26 | `admin_freshness_router` (`.router`) | `backend/app/routers/admin_freshness.py` | admin | `prefix=/api/admin` `/freshness` `tags=["admin-freshness"]` | 1 — **low** | `database.db` | ✅ Ready | |
| 27 | `admin_freshness_router` (`.crawl_router`) | `backend/app/routers/admin_freshness.py` | admin | `prefix=/api/admin` `/crawl` `tags=["admin-crawl"]` | 1 — **low** | (same file as above) | ✅ Ready | |
| 28 | `admin_freshness_router` (`.changes_router`) | `backend/app/routers/admin_freshness.py` | admin | `prefix=/api/admin` _(changes)_ `tags=["admin-freshness"]` | 1 — **low** | (same file as above) | ✅ Ready | |
| 29 | `admin_review_queue_router` | `backend/app/routers/admin_review_queue.py` | admin | `prefix=/api/admin` `/review-queue` `tags=["admin-review-queue"]` | 1 — **low** | `database.db` | ✅ Ready | |
| 30 | `admin_notifications_router` | `backend/app/routers/admin_notifications.py` | admin | `prefix=/api/admin` `/notifications` `tags=["admin-notifications"]` | 1 — **low** | `database.db` | ✅ Ready | |
| 31 | `admin_ops_analytics_router` | `backend/app/routers/admin_ops_analytics.py` | admin | `prefix=/api/admin` `/ops` `tags=["admin-ops-analytics"]` | 2 — **low** | `database.db` | ✅ Ready | |
| 32 | `admin_workflow_analytics_router` | `backend/app/routers/admin_workflow_analytics.py` | admin | `prefix=/api/admin` `/workflow` `tags=["admin-workflow-analytics"]` | 3 — **med** | `database.db` | ✅ Ready | |
| 33 | `admin_collaboration_router` | `backend/app/routers/admin_collaboration.py` | admin | `prefix=/api/admin` `/collaboration` `tags=["admin-collaboration"]` | 1 — **low** | `database.db` | ✅ Ready | |
| 34 | `admin_prospects_router` | `backend/app/routers/admin_prospects.py` | admin | `prefix=/api/admin` `/prospects` `tags=["admin-prospects"]` | 3 — **med** | `SessionLocal` | ⚠️ Dual DB | |
| 35 | `admin_form_templates_router` | `backend/app/routers/admin_form_templates.py` | admin | `prefix=/api/admin` `/form-templates` `tags=["admin-form-templates"]` | 2 — **low** | `database.db` | ✅ Ready | |
| 36 | `admin_recommendations_debug_router` | `backend/app/recommendations/admin_debug.py` | admin | `tags=["admin-recommendations-debug"]` | 1 — **low** | none | ✅ Ready | |
| 37 | `policy_canonical_router` (`.admin_router`) | `backend/app/routers/policy_canonical.py` | HR | `prefix=/api/admin` `/policy-canonical` `tags=["policy-canonical-admin"]` | 1 — **low** | `database.db` | ✅ Ready | ⭐ |
| 38 | `policy_canonical_router` (`.read_router`) | `backend/app/routers/policy_canonical.py` | HR | `prefix=/api` `/policy-canonical` `tags=["policy-canonical"]` | 1 — **low** | (same file as above) | ✅ Ready | ⭐ |
| 39 | `policy_templates_router` | `backend/app/routers/policy_templates.py` | HR | `/api/policy/templates` `tags=["policy_templates"]` | 1 — **low** | none | ✅ Ready | ⭐ |
| 40 | `suppliers_router` | `backend/app/routers/suppliers.py` | provider | `/api/suppliers` `tags=["suppliers"]` | 5 — **med** | `SessionLocal` | ⚠️ Dual DB | |
| 41 | `resources_router` | `backend/routes/resources.py` | util | `/api/resources` `tags=["resources"]` | 2 — **low** | none | ✅ Ready | |
| 42 | `hr_resources_router` | `backend/routes/hr_resources.py` | HR | `/api/hr/resources` `tags=["hr-resources"]` | 2 — **low** | none | ✅ Ready | ⭐ |
| 43 | `recommendations_router` | `backend/app/recommendations/router.py` | employee | `/api/recommendations` `tags=["recommendations"]` | 7 — **med** | none | ✅ Ready | ⭐ |
| 44 | `relocation_router` (`.router`) | `backend/routes/relocation.py` | employee | `/relocation` `tags=["relocation"]` | 6 — **med** | none | ✅ Ready | ⭐ |
| 45 | `relocation_router` (`.api_router`) | `backend/routes/relocation.py` | employee | `/api/relocation` `tags=["relocation"]` | 6 — **med** | (same file as above) | ✅ Ready | ⭐ |
| 46 | `relocation_classify_router` | `backend/routes/relocation_classify.py` | employee | `/api/relocation` `tags=["relocation"]` | 3 — **med** | none | ✅ Ready | ⭐ |
| 47 | `hr_policy_config_router` | `backend/main.py` (inline, line 13355) | HR | `/api/hr` `tags=["compensation-policy-config"]` | N/A (inline) | `database.db`, `auth_deps` (via main) | ⚠️ Inline — needs extraction | ⭐ |
| 48 | `admin_policy_config_router` | `backend/main.py` (inline, line 13356) | admin | `/api/admin` `tags=["admin-compensation-policy-config"]` | N/A (inline) | `database.db` (via main) | ⚠️ Inline — needs extraction | |
| 49 | `employee_policy_config_router` | `backend/main.py` (inline, line 13357) | employee | `/api/employee` `tags=["employee-compensation-policy-config"]` | N/A (inline) | `database.db` (via main) | ⚠️ Inline — needs extraction | ⭐ |
| 50 | `public_policy_config_router` | `backend/main.py` (inline, line 13358) | util | `/api` `tags=["policy-config-caps"]` | N/A (inline) | `database.db` (via main) | ⚠️ Inline — needs extraction | |
| 51 | `hr_coordination_router` | `backend/app/routers/hr_coordination.py` | HR | `/api/hr` `tags=["hr-coordination"]` | 4 — **med** | `database.db` | ✅ Ready | ⭐ |
| 52 | `prescreening_router` | `backend/app/routers/prescreening.py` | HR | `tags=["prescreening"]` | 1 — **low** | none | ✅ Ready | ⭐ |
| 53 | `personio_webhook_router` | `backend/app/routers/integrations_personio_webhook.py` | infra | `tags=["integrations-personio"]` | 1 — **low** | none | ✅ Ready | |
| 54 | `personio_settings_router` | `backend/app/routers/integrations_personio_settings.py` | infra | `tags=["integrations-personio"]` | 1 — **low** | none | ✅ Ready | |
| 55 | `bamboohr_router` | `backend/app/routers/integrations_bamboohr.py` | infra | `tags=["integrations-bamboohr"]` | 1 — **low** | none | ✅ Ready | |
| 56 | `relocation_profile_router` | `backend/app/routers/relocation_profile.py` | employee | `/api/employee/cases` `tags=["relocation-profile"]` | 2 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 57 | `rules_router` | `backend/app/routers/rules.py` | HR | `/api/rules` `tags=["rules"]` | 2 — **low** | none | ✅ Ready | ⭐ |
| 58 | `marketplace_router` | `backend/app/routers/marketplace.py` | employee | `/api/employee/assignments` `tags=["marketplace"]` | 2 — **low** | `database.db`, `auth_deps` | ✅ Ready | ⭐ |
| 59 | `hr_analytics_router` | `backend/app/routers/hr_analytics.py` | HR | `/api/hr` `tags=["hr-analytics"]` | 3 — **med** | `database.db` (as `main_db`), `auth_deps` | ✅ Ready | ⭐ |
| 60 | `advisors_router` | `backend/app/routers/advisors.py` | employee | `/api/advisors` `tags=["advisors"]` | 1 — **low** | `auth_deps` | ✅ Ready | ⭐ |
| 61 | `branding_router` | `backend/app/routers/branding.py` | admin | `/api/company` `tags=["branding"]` | 2 — **low** | `database.db` (lazy import), `auth_deps` | ✅ Ready | |

**Total `include_router` calls: 61** ✅ matches `grep -c "include_router\|@app\." backend/main.py` (314 = 61 + 249 inline `@app.` + 4 decorators)

---

## 3. Shared Dependencies

### 3a. Core DB Helpers (used across domains)

| Dependency | Import path | Usage count (routers) | Notes |
|------------|-------------|----------------------|-------|
| `db` (async DB helper) | `from ...database import db` | ~40 routers | Primary DB abstraction for all migrated routers |
| `SessionLocal` (SQLAlchemy sync) | `from ..db import SessionLocal` | 5 routers: `cases`, `admin`, `admin_prospects`, `suppliers` + `admin_resources`-style | Legacy sync ORM — dual-DB routers need cleanup before migration |
| `Database` class | `from ...database import db, Database` | 2 routers | Only `admin.py` imports `Database` directly |

### 3b. Auth Dependencies

| Dependency | Import path | Used by |
|------------|-------------|---------|
| `get_current_user` | `from ..auth_deps import get_current_user` | ~20+ routers |
| `require_hr_or_employee` | `from ..auth_deps import require_hr_or_employee` | `employee_quotes`, `exception_requests` |
| `require_admin_or_hr` | `from ..auth_deps import require_admin_or_hr` | `immigration`, `analytics_query`, `hr_analytics` |
| `require_case_access` | `from ..auth_deps import require_case_access` | `exception_requests` |
| `get_org_id_for_hr_user` | `from ..auth_deps import get_org_id_for_hr_user` | `immigration` |
| `main.get_current_user` | `from backend.main import get_current_user` | `mobility_context` (circular — must be fixed before migration) |

### 3c. Middleware (in `backend/main.py`)

| Middleware | Line | Description |
|------------|------|-------------|
| `CORSMiddleware` | ~395 | Allow all origins — shared by both main.py and app/main.py |
| `RateLimitExceeded` handler | 398 | slowapi rate limiter |
| HTTP middleware | 511 | Request logging / PII filter |
| Global exception handler | 482 | Catch-all 500 formatter |

---

## 4. Already Migrated — `backend/app/main.py`

These 6 routers are already wired into `backend/app/main.py` (the target):

| Router file | Domain | Notes |
|-------------|--------|-------|
| `backend/app/routers/cases.py` | HR/employee | High churn (16), dual DB — also still mounted in `backend/main.py` |
| `backend/app/routers/admin.py` | admin | Dual DB — also still mounted in `backend/main.py` |
| `backend/app/routers/employee_quotes.py` | employee | Also still mounted in `backend/main.py` |
| `backend/app/routers/pets.py` | employee | Not in `backend/main.py` — already exclusive to `app/main.py` |
| `backend/app/routers/support.py` | util | Not in `backend/main.py` — already exclusive |
| `backend/app/routers/ab_tests.py` | util | Not in `backend/main.py` — already exclusive |

> **Note**: `cases`, `admin`, and `employee_quotes` are double-mounted (both `backend/main.py` and `backend/app/main.py`). `pets`, `support`, and `ab_tests` are exclusive to `app/main.py` already.

---

## 5. Month-1 Migration Order (auth, employee, HR)

Ranked by: domain priority → migration readiness → churn (high churn = extract sooner)

### Tier 1 — Highest Impact, Cleanest Migration
| Priority | Router file | Domain | Churn | Blocker |
|----------|-------------|--------|-------|---------|
| 1 | `backend/app/routers/auth.py` | auth | med (7) | None |
| 2 | `backend/app/routers/cases.py` | HR/employee | high (16) | Dual DB (SessionLocal) |
| 3 | `backend/app/routers/hr_catalog.py` | HR | high (9) | None |
| 4 | `backend/app/routers/hr_coordination.py` | HR | med (4) | None |
| 5 | `backend/app/routers/immigration.py` | employee | med (4) | None |
| 6 | `backend/app/routers/exception_requests.py` | employee | med (4) | None |

### Tier 2 — HR Policy Cluster (related, extract together)
| Priority | Router file | Domain | Churn | Blocker |
|----------|-------------|--------|-------|---------|
| 7 | `backend/app/routers/policy_publish.py` | HR | low (1) | None |
| 8 | `backend/app/routers/policy_summary.py` | HR | low (2) | None |
| 9 | `backend/app/routers/policy_feedback.py` | HR | low (1) | None |
| 10 | `backend/app/routers/policy_canonical.py` | HR | low (1) | None |
| 11 | `backend/app/routers/policy_templates.py` | HR | low (1) | None |
| 12 | `backend/app/routers/hr_analytics.py` | HR | med (3) | None |

### Tier 3 — Employee Cluster
| Priority | Router file | Domain | Churn | Blocker |
|----------|-------------|--------|-------|---------|
| 13 | `backend/routes/relocation.py` | employee | med (6) | In `backend/routes/` — needs move |
| 14 | `backend/routes/relocation_classify.py` | employee | med (3) | In `backend/routes/` — needs move |
| 15 | `backend/app/routers/relocation_profile.py` | employee | low (2) | None |
| 16 | `backend/app/routers/marketplace.py` | employee | low (2) | None |
| 17 | `backend/app/recommendations/router.py` | employee | med (7) | Non-standard path |
| 18 | `backend/app/routers/advisors.py` | employee | low (1) | None |
| 19 | `backend/app/routers/mobility_context.py` | employee | low (2) | **Circular import** — fix `backend.main.get_current_user` import first |

### Tier 4 — Inline Policy Config Routers (extract first, then migrate)
| Priority | Router file | Domain | Blocker |
|----------|-------------|--------|---------|
| 20 | `hr_policy_config_router` (inline ~L13355) | HR | Extract to `backend/app/routers/hr_policy_config.py` |
| 21 | `employee_policy_config_router` (inline ~L13357) | employee | Extract to `backend/app/routers/employee_policy_config.py` |

---

## 6. Inline Routes Still in `backend/main.py` (backlog, post-Month-1)

These 249 inline `@app.` handlers need extraction into router files in a future sprint:

| Domain | URL pattern examples | Approx count |
|--------|---------------------|-------------|
| admin | `/api/admin/companies`, `/api/admin/people`, `/api/admin/assignments`, `/api/admin/policies`, `/api/admin/reconciliation/*` | ~60 |
| HR | `/api/hr/assignments`, `/api/hr/messages`, `/api/hr/cases`, `/api/hr/policies`, `/api/hr/command-center` | ~55 |
| employee | `/api/employee/assignments`, `/api/employee/journey`, `/api/employee/tasks`, `/api/employee/policy` | ~45 |
| policy | `/api/company-policies`, `/api/policy-assistant`, `/api/hr/policy-documents` | ~55 |
| services/rfq | `/api/services/*`, `/api/rfqs/*`, `/api/vendor/rfqs/*` | ~20 |
| dossier/guidance | `/api/dossier/*`, `/api/guidance/*` | ~15 |
| infra/util | `/health`, `/`, `/debug/*`, `/api/notifications`, `/api/resources/country` | ~10 |

> These are tracked as the Month-2/3 extraction backlog. The inline `admin_policy_config_router` and `public_policy_config_router` (already using `APIRouter`) are the easiest to extract first.

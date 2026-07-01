# Admin route & endpoint inventory

Classification of the ReloPass ADMIN surface as of `origin/main @ 0f14c760` (2026-06-30). Static read of code. Status legend: **LIVE** (reachable + API-wired), **LEGACY** (rollback-only `-legacy` route), **DEAD** (built but unreachable / 0 importers), **DUP** (duplicate of a live page), **UNGUARDED** (no `RequireAdminRoute`), **WIP** (uncommitted/orphan).

## 1. Frontend admin routes (`frontend/src/navigation/routes.ts` + `App.tsx`, guard `features/admin/RequireAdminRoute.tsx`)

| Route | Component | Status | Notes |
|---|---|---|---|
| `/admin` | `AdminOverviewPage` | LIVE | landing; 4 StatCards (System SLA = hard-null) + 8 ModuleCards |
| `/admin/rag-quality` | `AdminRagQualityPage` | LIVE | sidebar-absent; backend mock until reports land |
| `/admin/catalog-queue` | `AdminCatalogQueuePage` | LIVE | sidebar (count badge) |
| `/admin/requirement-facts` | `AdminRequirementFactsPage` | LIVE | sidebar |
| `/admin/research-requests` | `AdminResearchRequestsPage` | LIVE | sidebar |
| `/admin/companies` | `AdminCompaniesV2` | LIVE | sidebar |
| `/admin/companies-v2` | `AdminCompaniesV2` | DUP | same component |
| `/admin/companies-legacy` | `pages/admin/AdminCompanies` | LEGACY | |
| `/admin/companies/:id` (+`/profile`) | `AdminCompanyDetail` / `AdminCompanyProfilePage` | LIVE | |
| `/admin/people` | `AdminUsers` | LIVE | |
| `/admin/users` | → redirect `/admin/people` | LIVE | |
| `/admin/assignments` | `AdminAssignments` | LIVE | buried |
| `/admin/relocations` | → redirect `/admin/assignments` | LIVE | |
| `/admin/mobility/cases(/:caseId)` | `AdminMobilityCaseInspectPage` | LIVE | per-case audit view |
| `/admin/policies` | `AdminPoliciesPage` → policy-workspace | LIVE | buried |
| `/admin/messages` | `AdminMessages` | LIVE | |
| `/admin/support` | → redirect `/admin/messages` | LIVE | |
| `/admin/research` | → redirect `/admin` | LIVE | |
| `/admin/errors` | `AdminErrors`→`ErrorTicketsTab` | LIVE | **buried** (prod FE errors by fingerprint) |
| `/admin/feedback` | `AdminFeedback`→`FeedbackTab` | LIVE | **buried** (product feedback triage) |
| `/admin/suppliers(/new,/:id)` | `AdminSuppliers*` | LIVE | sidebar-absent (overview card) |
| `/admin/prompts` | `AdminPrompts` | LIVE | **buried** (LLM prompt registry) |
| `/admin/prospects` | `AdminProspects` | LIVE | sidebar |
| `/admin/resources(/*)` | `AdminResources*`/taxonomy | LIVE | sidebar |
| `/admin/ab-tests` | `AdminAbTestsPage` | LIVE | buried |
| `/admin/corrections/trends` | `AdminCorrectionsTrends` | LIVE | buried |
| `/admin/form-templates(/*)` | `AdminFormTemplates*` | LIVE | sidebar |
| `/admin/events(/:id)` | `AdminEvents*` | LIVE | buried |
| `/admin/staging(/*)` | `AdminStaging*` | LIVE | buried |
| `/admin/freshness(/*)` + `/crawl/*` + `/source-monitor` + `/source-change-reviews` | `AdminFreshness*`/`AdminCrawl*`/`AdminSourceMonitor`/`AdminSourceChangeReviewsPage` | LIVE | buried; content/source ops |
| `/admin/review-queue` | `AdminReviewQueueV2Page` | LIVE | sidebar |
| `/admin/review-queue-v2` | same | DUP | |
| `/admin/review-queue-legacy` | `review-queue/AdminReviewQueuePage` | LEGACY | |
| `/admin/review-queue/workload` + `/:id` | workload / detail | LIVE | |
| `/admin/ops` + `/ops/{sla,queue,reviewers,destinations,notifications}` | `OpsAnalyticsV2Page` / `AdminOps*` | LIVE | sidebar |
| `/admin/specialist-review/:case_id` | `AdminSpecialistReviewPage` | LIVE | HITL release gate UI |
| `/admin/countries(/:cc)` | `CountriesPage`/`CountryDetailPage` | **UNGUARDED** | declared in `routes.ts` (not `navigation/`); renders `AppShell`, no `RequireAdminRoute` |
| `/dev/data-table-demo` | `DataTableDemo` | LIVE | admin-guarded dev demo |

**Dead / decoy / orphan (frontend):** `pages/admin/AdminResearch.tsx`, `AdminRelocations.tsx`, `AdminSupport.tsx` (DEAD, route-redirected); `pages/admin/AdminDashboard.tsx` ↔ `features/platform-v2/admin/AdminDashboard.tsx` (mutually-importing DEAD orphans); `features/platform-v2/admin/AdminExceptions.tsx` (DEAD, 0 importers); `pages/admin/AdminTabLayout.tsx` (WIP orphan, 0 importers); 3 dead sidebars (`platform-v2/shell/Sidebar.tsx`, `platform-v2/sidebar/PlatformSidebar.tsx` + `PlatformSidebarPreview.tsx`). Live sidebar = `components/PlatformShellSidebar.tsx` (10 admin items). Inconsistent tab layouts: `AdminOpsLayout`/`AdminReviewQueueLayout`/`AdminFreshnessLayout` (the WIP `AdminTabLayout` was meant to unify them).

**Discoverability:** ~30+ LIVE admin pages; only 10 in the sidebar + 8 overview cards. Buried (deep-link only): Errors, Feedback, Prompts, RAG-quality, A/B-tests, Corrections-trends, Policies, Assignments, People, Messages, Mobility, Suppliers, Events, Staging, Freshness/Crawl, Source-monitor, Source-change-reviews, Specialist-review, Countries DB, all Ops sub-pages.

## 2. Backend admin endpoints

> The live ASGI app is `backend/main.py` (mounts the full admin surface, ~60 inline `@app` admin routes + the routers below). `backend/app/main.py` mounts only ~12 admin routers — do not trust it for the admin list.

| Router / area | Prefix | Mutates | Audited? |
|---|---|---|---|
| `routers/admin.py` (research/ingest/requirements) | `/api/admin` | approve/reject facts, ingest URLs, reconcile | **YES** (`_audit_postgres`→`audit_logs`) |
| `routers/admin_catalog.py` | `/api/admin/catalog` | destinations, demand-gaps, promote-vendors | **NO** (silent) |
| `routers/admin_prospects.py` | `/api/admin/prospects` | full CRUD + delete + CSV | **NO** |
| `routers/admin_staging.py` | `/api/admin/staging` | approve/merge/reject/dup | **NO** |
| `routers/admin_freshness.py` | `/api/admin/{freshness,crawl,changes}` | crawl-schedule CRUD, scans | **NO** |
| `routers/admin_review_queue.py` | `/api/admin/review-queue` | assign/claim/status/resolve | **NO** |
| `routers/admin_resources.py` | `/api/admin/resources` | publish pipeline + taxonomy | app-level (`/audit-log`) |
| `routers/admin_notifications.py` | `/api/admin/notifications` | ack/resolve/suppress | **NO** |
| `routers/admin_source_change_review.py` | `/api/admin` | approve/reject source changes (HITL) | partial |
| `routers/admin_prompts.py` | `/api/admin/prompts` | create/promote prompt versions, canary | **NO** (prompt promotion unaudited) |
| `routers/specialist_review.py` | (admin) | release AI roadmap steps (HITL) | `specialist_review_events` |
| `routers/admin_ops_analytics.py` | `/api/admin/ops` | read-only | n/a |
| `routers/admin_workflow_analytics.py` | `/api/admin/workflow` | read-only; **own local `_require_admin`** | n/a |
| `routers/admin_rag_eval.py` | `/api/admin/rag-eval/metrics` | read-only; **mock until reports land** | n/a |
| `routers/admin_ai_unit_economics.py`, `admin_ocr_shadow.py`, `admin_corrections.py`, `admin_mobility.py`, `admin_collaboration.py`, `recommendations/admin_debug.py` | `/api/admin*` | read/ops | mixed |
| inline `/api/admin/*` in `backend/main.py` | — | impersonate, companies/people/assignments CRUD, data-integrity/reconciliation, policies, support, `/actions/*` (purge-cases, override-eligibility, unlock-case, …) | `/actions/*` → legacy `audit_log`; CRUD mostly silent |
| `routers/policy_publish.py`, `policy_config.py` | `/api/policy/publish` | publish | **YES** (`audit_logs`) |
| `routers/hr_analytics.py` | `/answer-provenance` | read (gate-impact rollup) | **company-scoped, not fleet** |

**Uncontrollable from any endpoint (env/code only):** `POLICY_RAG_GROUNDEDNESS_GATE`, `POLICY_RAG_GROUNDEDNESS_MIN_SCORE`, `POLICY_RAG_RERANK`, `SUPPLIER_LEARNED_WEIGHTS`, `recommendations/weights.py::WEIGHTS`, all `rag_eval_reports.py` `MetricSpec` thresholds, model/temperature/embeddings env vars, `CRON_SECRET` (root-admin bypass).

**Access control:** `admin_allowlist` + `is_admin()` (SQL) / `auth_deps._is_admin_user()` (app). **No endpoint to add/remove an admin** (SQL only; no remove/disable function exists). `CRON_SECRET == Authorization` → synthetic full-ADMIN user (root bypass outside allowlist).

**Audit logging:** 3 disjoint mechanisms / 2 tables — `audit_logs` (trigger on only `mobility_cases`/`case_people`/`case_documents` + 6 app writers), legacy `audit_log` (operator `/actions/*`), module-local (`admin_resources`). Many mutating routers write nothing. **No platform-wide admin audit browser** (only per-case/per-request scoped reads).

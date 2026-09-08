# Audos Dashboard Concepts vs. ReloPass — Evaluation & Build Plan

**Date:** 2026-07-01
**Author:** Claude (Cowork), reviewed against the live `rolec` codebase
**Source:** 6 screenshots of Audos's auto-generated app dashboards (Database Explorer, Analytics Dashboard, CRM Dashboard, Human Help), seen in the "ReloPass" and "GlobeIQ" Audos workspaces

## Framing

Audos gives every app built on its platform four generic dashboards for free: a raw schema/SQL browser, a generic event funnel (`landing_page_view → cta_click → email_submit → pricing_view → checkout → purchase`), a flat contacts table, and a pay-per-task human queue with a wallet. They're built for early-stage prototypes that have no backend of their own yet.

ReloPass isn't that. It's a mature FastAPI + Supabase app with its own admin CMS, RLS-scoped multi-tenant data model, and an existing analytics pipeline. So the real question per dashboard isn't "should we copy this UI" — it's "does the underlying capability already exist, is the Audos version actually a fit for our B2B model, and if there's a genuine gap, what's the smallest correct extension of what we've already built."

Verdict up front: **2 of the 4 concepts are worth building, as targeted extensions of existing infrastructure — not new systems. 2 are not worth building**, one because it's already covered and the other because it's a security anti-pattern for this codebase.

| # | Concept | Verdict | Effort |
|---|---|---|---|
| P1 | CRM / lead contacts | **Build** — extend `admin_prospects` | Medium |
| P2 | Marketing/acquisition analytics | **Build** — extend `admin_workflow_analytics` | Low |
| P3 | Human Help / approval queue | **Already covered** — no build | — |
| P4 | Database Explorer | **Don't build** | — |

---

## What already exists today (grounded in the repo)

| Audos concept | ReloPass equivalent | Key files | Gap vs. Audos |
|---|---|---|---|
| Database Explorer | *(none — by design)* | — | No in-app raw table/SQL browser. Supabase Studio + the Supabase MCP (`list_tables`, `execute_sql`, `get_advisors`, `list_migrations`) already give the engineering team this, without bypassing RLS. |
| Analytics Dashboard | In-product workflow funnel | `backend/app/routers/admin_workflow_analytics.py` (`GET /admin/workflow/overview`, `GET /admin/workflow/events`), `backend/app/services/analytics_service.py` (`emit_event`), `analytics_events` table (`supabase/migrations/20260326000000_analytics_events.sql`), client emitter `frontend/src/analytics.ts` (PostHog, `track()`) | Covers `case_created → services_selected → recommendations_generated → supplier_viewed/selected → rfq_created → quote_received/compared/accepted` (documented in `docs/OBSERVABILITY_ANALYTICS.md`). Nothing covers the pre-signup marketing funnel (landing page → CTA → lead capture) that the Audos screenshot shows. |
| CRM Dashboard | Outbound prospect pipeline | `backend/app/routers/admin_prospects.py`, `ProspectCandidate` model (`backend/app/models.py:352`), page `frontend/src/pages/admin/AdminProspects.tsx`, route `/admin/prospects` | `prospect_candidates` is **company-level**, sourced for outbound LLM enrichment/triage. There is no **person-level** lead table — no record of who actually submitted an email on the marketing site, no tags/status/"new this week" for individual contacts. |
| Human Help | Ops review queue + AI oversight ledger | `backend/app/routers/admin_review_queue.py` (16 endpoints: claim/assign/defer/resolve/bulk-status/backfill), `backend/app/routers/ai_decisions.py`, migration `20260527000000_ai_decisions_human_oversight.sql`, pages under `frontend/src/pages/admin/review-queue/`, routes `/admin/review-queue*` | Functionally superset of Audos's version — richer states, bulk actions, per-item activity log, and a separate EU AI Act Art. 14 audit trail (`ai_decisions`). The only thing genuinely missing is the wallet/spend ledger, which doesn't map to ReloPass's model (see P3 below). |

---

## P1 — Lead CRM (extend `admin_prospects`, don't replace it)

### Goal
Give GTM/sales one place to see **inbound** leads (marketing-site email captures, demo requests) next to **outbound** prospect companies already tracked in `prospect_candidates`, so pipeline conversion (lead → qualified → customer) is measurable instead of scattered across PostHog and someone's inbox.

### Why it matters
Right now an email submitted on the marketing site produces a PostHog event and nothing else — no ReloPass record, no way to triage it, no link to the outbound-prospecting list. If a lead's company is already in `prospect_candidates`, nobody currently sees that overlap.

### Spec
- **New table `leads`** (person-level, GTM-internal — not customer/tenant data, so no `company_id` tenant scoping is needed, but RLS is still mandatory per the repo's hard gate):
  - `id, email, first_name, last_name, company_domain (nullable, FK-by-value to prospect_candidates.company_domain), source (marketing_site | manual | referral), status (new | contacted | qualified | converted | lost), tags text[], utm_source, utm_campaign, created_at, updated_at`
  - Migration file: `supabase/migrations/<timestamp>_create_leads_table.sql`, must include (per `CLAUDE.md` hard gate): `ENABLE ROW LEVEL SECURITY`, a policy scoping reads/writes to `is_admin()`, and `REVOKE ALL ON public.leads FROM anon`.
- **New router** `backend/app/routers/admin_leads.py`:
  - `GET /admin/leads` (filter by status/tag/search), `GET /admin/leads/{id}`, `PATCH /admin/leads/{id}` (status/tags), `POST /admin/leads/ingest` (marketing-site webhook or PostHog export), `GET /admin/leads/stats` (total, new this week, avg `analytics_events` per contact — join against the existing `analytics_events` table, reusing the query pattern already in `admin_workflow_analytics.py`).
  - **Mandatory per `CLAUDE.md`:** register in *both* `backend/app/main.py` and `backend/main.py` (import + `include_router`, matching the existing block around line 580/710). Skipping the second registration is exactly the AI-002 v2 failure mode documented in the repo — verify with:
    `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'leads' in r.path))"`
- **Frontend**: `frontend/src/pages/admin/AdminLeads.tsx`, modeled directly on `AdminProspects.tsx` (reuse the same antigravity table/badge/filter components), route `/admin/leads`. Surface a "matched prospect" badge when `leads.company_domain` matches an existing `prospect_candidates.company_domain`.
- **PII note**: if any lead free-text field (notes, form message) is ever passed to an LLM for auto-enrichment, it must go through `mask_pii()` first, per the repo's Data Minimisation rule — flag this in the ticket so it isn't missed the way it nearly was elsewhere.

### Verification
1. `cd frontend && npx tsc --noEmit` clean.
2. `cd backend && pytest` — new tests import `get_current_user`/`require_admin` from `backend.app.auth_deps` (not `backend.main`), per the documented gotcha, or `dependency_overrides` silently won't fire.
3. Route-visibility check (the one-liner above) confirms the router is live in the prod app instance, not just the modular one.
4. Supabase migration-drift CI check green; `get_advisors` (Supabase MCP) shows no RLS/anon-exposure warnings on `leads`.
5. Manual QA: submit a test email on staging marketing site → confirm it lands in `/admin/leads` within expected latency, and that a domain match against an existing prospect surfaces correctly.

### Success metrics
- **Adoption**: leads triaged/week by GTM (target: 100% triaged within 5 business days).
- **Pipeline signal**: lead → qualified rate, lead → prospect-domain-match rate.
- **Security health**: `get_advisors` clean (0 RLS/anon findings) — this is the metric that actually matters most given SEC-002 history.

---

## P2 — Marketing/Acquisition Analytics (extend `admin_workflow_analytics`)

### Goal
Surface the pre-signup funnel (`landing_page_view → cta_click → email_submit`) that PostHog is already capturing via `frontend/src/analytics.ts`, but that no admin screen currently shows — `admin_workflow_analytics.py` only covers the post-signup product funnel.

### Why it matters
This is the cheapest of the four builds: no new table, no new tracking code — `analytics_events` already exists and `track()` is already wired up. The gap is purely a missing aggregation endpoint + page. Pairing it with P1 lets GTM see the full funnel (impression → click → lead → qualified) in one place instead of two.

### Spec
- Confirm first (don't assume) that the marketing site emits into the **same** `analytics_events`/PostHog project as the app — grep `frontend/src/analytics.ts` callers and the marketing site's own tracking snippet for matching event names before writing the aggregation query, since names must match exactly.
- **New router** `backend/app/routers/admin_marketing_analytics.py`: `GET /admin/marketing-analytics/funnel` — counts of `landing_page_view`, `landing_page_cta_click`, `email_submit` (or whatever the real event names turn out to be), grouped by day and UTM source, unique-visitor and total-event variants, following the same query style already used in `admin_workflow_analytics.py` for consistency.
  - Same dual-registration requirement as P1 (`backend/app/main.py` **and** `backend/main.py`).
- **Frontend**: `frontend/src/pages/admin/ops/AdminMarketingAnalyticsPage.tsx`, reusing whichever chart library the existing `AdminOps*Page.tsx` files already import — don't introduce a new charting dependency for this.

### Verification
Same pattern as P1 (tsc, pytest, dual-registration route check) plus one extra step specific to this ticket: before merging, diff the event names used in the query against what `track()` calls actually emit in the marketing site's source — a silent name mismatch would make the dashboard render zeros without erroring.

### Success metrics
- CTA click-through rate, email-capture rate, week-over-week trend.
- Once P1 ships: lead-to-pipeline conversion, closing the loop from "marketing event" to "qualified lead."

---

## P3 — Human Help / Approval Queue: no build needed

`admin_review_queue.py` (claim/assign/defer/resolve/bulk actions, per-item activity log) and `ai_decisions.py` (EU AI Act Art. 14 human-oversight ledger — accept/override/reject with mandatory reason) already exceed what the Audos template shows. The one thing Audos has that ReloPass doesn't — a wallet/spend ledger for paying humans per task — doesn't map to ReloPass's model, where reviewers are internal employees, not a pay-per-task marketplace. Building it would be solving a problem the business doesn't have.

If there's an appetite for a small enhancement: `admin_ai_unit_economics.py` already exists and could get a cost rollup cross-referencing `ai_decisions` review volume — a minor addition to an existing router, not a new dashboard.

**Success metric, if tracked at all:** reviewer SLA, which `admin_ops_analytics.py`'s `/ops/sla/overview` already reports.

---

## P4 — Database Explorer: don't build

A generic raw-table/SQL browser is the wrong tool for a codebase whose hardest security rule is RLS-scoped tenant isolation (SEC-002 — 8 tables, GDPR-scope PII exposure — happened because a table was reachable outside its RLS policy). A generic browser either respects RLS (in which case it's strictly worse than the domain-specific Admin CMS pages that already exist for companies/policies/suppliers/catalog) or bypasses it (in which case it's a standing risk of repeating SEC-002).

The underlying need — engineers being able to inspect schema, run queries, check backups/usage — is already met by Supabase Studio and the Supabase MCP tools (`list_tables`, `execute_sql`, `get_advisors`, `list_migrations`, `get_logs`) available directly in this session. No gap to close.

---

## Full current admin surface (for reference)

**Backend routers** (`backend/app/routers/`): `admin.py`, `admin_ai_unit_economics.py`, `admin_catalog.py`, `admin_collaboration.py`, `admin_corrections.py`, `admin_form_templates.py`, `admin_freshness.py`, `admin_mobility.py`, `admin_notifications.py`, `admin_ocr_shadow.py`, `admin_ops_analytics.py`, `admin_prompts.py`, `admin_prospects.py`, `admin_rag_eval.py`, `admin_resources.py`, `admin_review_queue.py`, `admin_source_change_review.py`, `admin_staging.py`, `admin_workflow_analytics.py`, `ai_decisions.py`, `cases_admin.py`.

**Frontend admin routes**: `/admin`, `/admin/catalog-queue`, `/admin/companies`, `/admin/people`, `/admin/assignments`, `/admin/policies`, `/admin/suppliers`, `/admin/prompts`, `/admin/rag-quality`, `/admin/prospects`, `/admin/messages`, `/admin/resources`, `/admin/research`, `/admin/users`, `/admin/relocations`, `/admin/support`, `/admin/errors`, `/admin/feedback`, `/admin/freshness`, `/admin/staging`, `/admin/review-queue` (+ `/detail`, `/workload`), `/admin/source-monitor`, `/admin/source-change-reviews`.

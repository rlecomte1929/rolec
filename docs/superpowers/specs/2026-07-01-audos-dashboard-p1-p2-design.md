# Design Spec — Lead CRM (P1) + Marketing/Acquisition Analytics (P2)

**Date:** 2026-07-01
**Source evaluation:** `docs/dashboard/audos-dashboard-evaluation.md`
**Status:** Approved design → ready for implementation-plan authoring
**Scope:** Build P1 + P2. P3 (Human Help) already covered; P4 (DB Explorer) is an RLS anti-pattern — both skipped per the eval verdict.

---

## Context

The Audos evaluation identified two genuine gaps in ReloPass's admin surface, framed as *targeted extensions of existing infrastructure, not new systems*:

- **P1 — Lead CRM:** an email submitted on the marketing site today produces a PostHog event and nothing else. There is no person-level lead record, no triage/status, and no link to the company-level outbound pipeline (`prospect_candidates`). GTM/sales pipeline (lead → qualified → customer) is unmeasurable.
- **P2 — Marketing/Acquisition Analytics:** no admin screen shows the pre-signup funnel. `admin_workflow_analytics.py` only covers the post-signup product funnel.

### Corrections to the eval doc (verified against the live codebase)

1. **P2 is not "no new tracking code."** The frontend emits **zero** pre-signup funnel events. `frontend/src/pages/Landing.tsx` has no analytics calls; the only top-of-funnel signals that exist are `demo_modal_opened` and `demo_request_submitted`. A funnel dashboard renders zeros unless the landing page is instrumented. **Decision: instrument `Landing.tsx` as part of P2.** The repo ships **no charting library** by design — reuse the hand-rolled SVG chart `frontend/src/pages/admin/MetricTimeSeriesChart.tsx`. `analytics_events` is a minimal `event_name` + `payload_json` (jsonb) + `created_at` table (`supabase/migrations/20260326000000_analytics_events.sql`); UTM/session data rides inside `payload_json`.
2. **P1 ingest was undefined.** The demo forms (`frontend/src/components/marketing/BookDemoModal.tsx:144`, `InlineDemoForm.tsx:84`) only fire PostHog. **Decision: wire them to also POST to a public lead-capture endpoint** so real leads flow day one. These forms are unauthenticated, so the capture endpoint is **public + rate-limited**, separate from the admin-gated CRUD router.
3. **Registration nuance.** `admin_prospects` is registered in `backend/main.py` only (import ~line 163, `include_router(..., prefix="/api/admin")` ~line 804), *not* in `backend/app/main.py`. Per `CLAUDE.md`'s hard rule, new routers must be registered in **both** files — `backend/main.py` (serves prod) is mandatory; `backend/app/main.py` is required for the modular app + tests. We follow the rule, not the `admin_prospects` precedent.

### Confirmed reusable infrastructure

- Auth: `require_admin`, `get_current_user` in `backend/app/auth_deps.py` (require_admin @ line 133).
- `ProspectCandidate` model in `backend/app/models.py:352`, has `company_domain` (the join key).
- Analytics aggregation pattern: `backend/app/routers/admin_workflow_analytics.py` reads via `db.count_analytics_events_by_name` / `db.list_analytics_events` (raw SQL lives in `backend/app/database.py`, not the router). `emit_event` in `backend/app/services/analytics_service.py:46` is the only writer to `analytics_events`.
- Admin page pattern: `frontend/src/pages/admin/AdminProspects.tsx` — hand-rolls table/filters from antigravity `Badge`/`Button`/`Card`/`Checkbox`/`Alert` (no dedicated Table/Filter component). Data via `adminProspectsAPI` in `frontend/src/api/client.ts`. Route in `frontend/src/navigation/routes.ts` + lazy `<RequireAdminRoute>` in `frontend/src/App.tsx`.
- `mask_pii()` in `backend/app/services/pii_masker.py:203`.

---

## Goals & Success Criteria

| # | Goal | Verifiable success criterion |
|---|------|------------------------------|
| G1 | Every marketing-site email/demo submission becomes a triageable ReloPass record | Submitting the demo form on staging creates a row in `leads` visible at `/admin/leads` within seconds |
| G2 | GTM can triage leads and see overlap with the outbound prospect list | Lead whose `company_domain` matches a `prospect_candidates.company_domain` shows a "matched prospect" badge; status editable new→contacted→qualified→converted→lost |
| G3 | The pre-signup funnel (view → CTA → capture) is visible in admin | `/admin/marketing-analytics` renders real, non-zero counts for landing view, CTA click, and demo/email capture, by day and UTM source |
| G4 | Zero security regressions | `get_advisors` (Supabase MCP) reports 0 RLS/anon findings on `leads`; no unauthenticated read path to lead PII |
| G5 | No new frontend dependencies, no new backend patterns | `package.json` unchanged; new routers/pages reuse existing db-layer, antigravity components, and the hand-rolled SVG chart |

---

## P1 — Lead CRM

**P1.1 — Migration** `supabase/migrations/<ts>_create_leads_table.sql` (person-level, GTM-internal; no `company_id` tenant scoping, RLS still mandatory). Columns: `id uuid pk`, `email text not null`, `first_name`, `last_name`, `company_domain text` (nullable; FK-by-value to `prospect_candidates.company_domain`), `source text` (`marketing_site|manual|referral`), `status text default 'new'` (`new|contacted|qualified|converted|lost`), `tags text[]`, `message text`, `utm_source`, `utm_campaign`, `created_at timestamptz default now()`, `updated_at`. Indexes on `email`, `status`, `company_domain`. **Hard gate:** `ENABLE ROW LEVEL SECURITY`, `CREATE POLICY "leads admin all" ... FOR ALL USING (is_admin()) WITH CHECK (is_admin())`, `REVOKE ALL ON public.leads FROM anon`. Backend writes via service role. Timestamp `>` true dir max. Applied out-of-band; ledger reconciled after.

**P1.2 — ORM model** — add `Lead` to `backend/app/models.py` (mirror `ProspectCandidate`).

**P1.3 — Public capture endpoint** — `backend/app/routers/lead_capture.py`: `POST /api/public/lead-capture`, unauthenticated + slowapi rate-limited, inserts a `leads` row via service role, derives `company_domain` from email when absent. PII note in code: any future LLM enrichment of `message` must pass `mask_pii()` first.

**P1.4 — Admin CRUD router** — `backend/app/routers/admin_leads.py`, all `Depends(require_admin)`: `GET /admin/leads` (filter status/tag/search), `GET /admin/leads/{id}`, `PATCH /admin/leads/{id}`, `GET /admin/leads/stats`. Queries added to `backend/app/database.py`. **Dual-register** both routers in `backend/main.py` and `backend/app/main.py`; verify with `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'lead' in r.path))"`.

**P1.5 — Wire demo forms** — in `BookDemoModal.tsx` and `InlineDemoForm.tsx`, after `track('demo_request_submitted', …)`, best-effort non-blocking POST to `/api/public/lead-capture` (`source: 'marketing_site'`). Wrapper added to `frontend/src/api/client.ts`.

**P1.6 — Admin page** — `frontend/src/pages/admin/AdminLeads.tsx` modeled on `AdminProspects.tsx`; `adminLeadsAPI` in client; route in `routes.ts` + `App.tsx`. "matched prospect" badge on `company_domain` match.

---

## P2 — Marketing/Acquisition Analytics

**P2.1 — Instrument landing** — add `track()` (via `frontend/src/analytics.ts`) to `Landing.tsx`: `landing_page_view` on mount, `landing_cta_click` on primary CTAs with `{cta, utm_source, utm_campaign}`. **These must also reach `analytics_events`** (client PostHog does not) — see Open Detail.

**P2.2 — Aggregation endpoint** — `backend/app/routers/admin_marketing_analytics.py`: `GET /admin/marketing-analytics/funnel`, counts of `landing_page_view`/`landing_cta_click`/`demo_request_submitted` grouped by day + UTM, unique + total variants. Reuse `db.count_analytics_events_by_name`/`db.list_analytics_events`; add a UTM/day grouping method to `database.py` if needed. Admin-gated, dual-registered. Verify route one-liner (`'marketing'`).

**P2.3 — Admin page** — `frontend/src/pages/admin/ops/AdminMarketingAnalyticsPage.tsx` (match ops layout convention), reusing `MetricTimeSeriesChart.tsx` (no charting dep). Route in `routes.ts` + `App.tsx`.

### Open detail to resolve first (P2.1)
Client PostHog `track()` events do not reach `analytics_events` (only server-side `emit_event` writes there). **Recommendation (a):** landing events POST to a lightweight public `/api/public/track` that calls `emit_event` — keeps `analytics_events` the single source of truth and matches the `admin_workflow_analytics` query pattern. Alternative (b): funnel reads from PostHog's API. Resolve before building P2.2's query.

---

## Metrics (post-ship)

**GTM outcome:** P1 — leads triaged/week (target 100% within 5 business days), lead→qualified rate, lead→prospect-domain-match rate, time-to-first-touch. P2 — CTA click-through rate, email/demo-capture rate, WoW funnel trend; once P1 lands, lead→pipeline conversion.

**Delivery/health (merge gates):** `get_advisors` on `leads` = 0 RLS/anon findings; route one-liner lists new paths on `backend.main:app`; `package.json` diff empty; demo-form capture success rate ≥ current demo-submit success rate.

---

## Validation (per ticket, before merge)

1. `cd frontend && npx tsc --noEmit` clean.
2. `cd backend && pytest` — tests mount `from backend.main import app`, override `get_current_user`/`require_admin` from **`backend.app.auth_deps`**, `RELOPASS_QUERY_COUNTER_OFF=1`. Cover public capture insert, admin list/patch/stats, and RLS (anon cannot read `leads`).
3. Route-visibility one-liner (P1 `'lead'`, P2 `'marketing'`) confirms live on prod app instance.
4. Supabase `migration-drift` CI green; `get_advisors` clean on `leads`.
5. P2 name-match: diff query event-name strings against what `track()`/`emit_event` emit (silent mismatch → zeros).
6. Manual staging QA: demo submit → row in `/admin/leads` + correct match badge; landing view + CTA click → `/admin/marketing-analytics` increments.
7. `frontend/` build passes (pre-push hook / CI `frontend-build`).

---

## Sequencing

1. **PR 1 — P1 Lead CRM** (`feat/lead-crm`): migration → model → db methods → capture + admin routers (dual-reg) → demo-form wiring → admin page.
2. **PR 2 — P2 Marketing Analytics** (`feat/marketing-analytics`): resolve P2.1 ingestion path → landing instrumentation → aggregation endpoint (dual-reg) → page reusing `MetricTimeSeriesChart`.

Commit after each numbered sub-step. Feature branch → PR → CI green → merge; never direct-to-main.

## Out of scope
- P3 Human Help wallet/spend ledger (doesn't map to internal-reviewer model).
- P4 Database Explorer (Supabase Studio + MCP cover it; raw browser is an RLS anti-pattern).
- LLM auto-enrichment of leads (deferred; `message` must go through `mask_pii()` when added).

# AIQ-2326 — Admin KPI source-of-truth (ADMIN-IA-0a) — implementation plan

Card: https://app.notion.com/p/7bf3de833cb54a5a8cdf70e0aaf242cb
Branch: `feat/admin-metrics-sot` · Date: 2026-09-12

> Lightweight plan (the full `/autoplan` gstack multi-agent review was not run in this
> batched dev-queue execution; recon + the decisions below stand in for it).

## Approach

One backend service (`admin_metrics_service`) owns the definition of every admin KPI and
returns each as `{value, definition, source, as_of}`. Every consumer — Executive, the new
`/companies/overview`, and the frontend surfaces — reads from it instead of computing its
own count, so a "tenant" is one number everywhere and cannot drift again.

Consistency is by construction: tenant/people counts **reuse** the same
`get_admin_company_index` / `get_admin_people_index` the Companies and People lists use
(identical is_test + synthetic-name filtering); destinations reuse `coverage_service`.

## Files

- CREATED `backend/app/services/admin_metrics_service.py` — metric functions + `build_metrics_summary` / `build_companies_overview`.
- CREATED `backend/app/routers/admin_metrics.py` — `GET /api/admin/metrics/summary` (registered in **both** `backend/app/main.py` and `backend/main.py`).
- MODIFIED `backend/main.py` — new `GET /api/admin/companies/overview` **before** `/companies/{company_id}` (fixes the prod 500) + the dual-layer registration.
- MODIFIED `backend/app/services/exec_overview_service.py` — `_growth`/`_funnel` read counts from the SoT.
- CREATED `backend/tests/test_admin_metrics.py` — envelope shape, graceful degrade, exec+companies-overview mock-spy, prod-app route registration.
- Frontend: CREATED `api/adminMetrics.ts` (+ `useAdminMetrics`); `definition` tooltip prop on both StatCards (`antigravity/` + `admin/overview/`); wired Coverage ("Destinations with data"), Countries ("Curated countries"), Companies KPI strip; static definition tooltips on Today + Executive tiles.

## Decisions for review (UNRESOLVED DECISIONS → Romain / Cursor)

1. **The card's file locations were wrong** (Aside recon). companies/people/users handlers
   live in `backend/main.py`, **not** `backend/app/routers/admin.py`; the rendered StatCard on
   Today/Executive is `components/admin/overview/StatCard.tsx`, **not** the antigravity one.
   Implemented against the real files; `definition` added to **both** StatCards.
2. **`tenants_active`** = real tenants with ≥1 case assignment (companies has no `status`
   column, per Aside). Wording is a user-visible tooltip — confirm in Cursor.
3. **Today + Executive tenant tiles** already show the unified number purely from the backend
   change (all three funnel through `get_admin_company_index(include_test=false)`), so those
   tiles carry **static** definition tooltips rather than an extra `/metrics/summary` fetch —
   this keeps their pinned unit tests intact. Coverage/Countries/Companies read the live hook.
4. **No migration.** Read-only definition layer; old endpoints keep their response shape.

## Verification (Test Command — all green 2026-09-12)

`pytest backend/tests/test_admin_metrics.py backend/tests -k "exec_overview or companies" -q`
→ 21 passed. `npx tsc --noEmit` → clean. `npx vitest run …AdminOverviewPage… executive …antigravity`
→ 83 passed.

# Mobility Command Center — Widget Data-Source Audit

**Task:** AIQ-1104 — Audit and wire Mobility Command Center data widgets
**Date:** 2026-06-16
**Auditor:** Claude Code (relopass-dev-queue)
**Component:** `frontend/src/features/platform-v2/mobility-control/MobilityControlCenterV2Page.tsx`
**Route:** `/hr/command-center` (V2, feature-flag gated) and `/hr/command-center-v2`, both behind `RequireHrRoute`

---

## Verdict

**The page is already correctly wired.** Every data widget fetches from a real,
tenant-scoped API endpoint (or is derived client-side from real scoped case data),
and every widget renders a proper empty state rather than a fake value. The task's
premise — that widgets "may be backed by stub or placeholder data" — is **disproven**
by this audit. No widget silently shows a hardcoded or never-resolving value.

Two non-data-widget elements remain as honest stubs (see Follow-ups): the header
**filter buttons** and the **Visa/Household** table columns (a documented schema gap,
shown as an intentional "Not set" empty state, not fake data).

---

## Widget-by-widget verification

| # | Widget | Frontend source | Backend endpoint | Tenant scoping | Status |
|---|--------|-----------------|------------------|----------------|--------|
| 1 | **Active cases** KPI | `kpis.activeCases` via `hrAPI.getCommandCenterKPIs()` | `GET /api/hr/command-center/kpis` → `db.get_command_center_kpis()` (real SQL on `case_assignments` ⋈ `relocation_cases`) | `_command_center_scope()` → `company_id`; `_command_center_company_where()`; HR-without-company fallback guarded by `NOT EXISTS (SELECT 1 FROM hr_users …)` to prevent cross-company leakage | ✅ Wired |
| 2 | **At risk** KPI | `kpis.atRiskCount` | same endpoint | same | ✅ Wired |
| 3 | **Completed YTD** KPI | `kpis.completedCount` | same endpoint | same | ✅ Wired |
| 4 | **Mobility spend** KPI | derived: `sum(cases[].budgetEstimated)` / `sum(cases[].budgetLimit)` | derived from `GET /api/hr/command-center/cases` | inherits the scoped case list | ✅ Wired (derived) |
| 5 | **Executive summary** | `fetchExecSummary(companyId)` | `GET /api/hr/{companyId}/exec-summary` → data-to-text over `load_company_kpis()` (LLM-free, env-flag gated) | `_authorize_company(user, company_id)` | ✅ Wired |
| 6 | **All relocation cases** table | `hrAPI.listCommandCenterCases({page,limit})` | `GET /api/hr/command-center/cases` → `db.list_command_center_cases()` | `_command_center_scope()` (same as KPIs) | ✅ Wired |
| 7 | **Corridor mix** sidebar | `corridorMix` (client aggregate by ISO-2 origin→dest) | derived from cases | inherits scoped cases | ✅ Wired (derived) |
| 8 | **Risk feed** sidebar | `riskFeed` (cases where `riskStatus != green`) | derived from cases | inherits scoped cases | ✅ Wired (derived) |
| 9 | **Pending approvals** sidebar | `api.get('/api/exception-requests', {status:'pending'})` | `GET /api/exception-requests` → `list_exception_requests_for_company()` | `_caller_company_id(user)` → `WHERE pcr.organization_id = :org`; HR/Admin only (403 otherwise) | ✅ Wired |

### Empty / degraded states (all present)
- **Cases table:** `"No active relocations yet. Cases created on the Assignments page appear here."` (and `"Loading cases…"` while pending).
- **Corridor mix:** `"Corridors appear once a case has an origin and destination country."`
- **Risk feed:** `"All cases on track."`
- **Pending approvals:** `"No pending approvals."`
- **Executive summary:** hidden entirely when null or when all KPIs are zero (avoids all-zero noise on a fresh tenant).
- **Backend-degraded banner:** `Promise.allSettled` keeps partial data; a dismissable amber banner with a **Retry** action appears when KPIs or cases fail to load.
- **Per-cell empty states:** the `NotLinked` component renders a muted `"Not set"` with an engineer-facing tooltip (the backing-data gap) — never a `"tbd"` dev flag or a fabricated value.

---

## Findings (stubs — not data widgets showing fake values)

### F1 — Header filter buttons are non-functional stubs
`MobilityControlCenterV2Page.tsx` lines ~531–544: the **"All corridors"** and
**"Current quarter"** buttons call `alert('… — wire in follow-up')`. These are filter
*controls*, not data widgets — they do not display fabricated data; they simply don't
filter yet. Wiring them requires tenant-safe query params (a `risk_filter` param
already exists on `list_command_center_cases`; corridor + period filters do not) and
must not alter aggregation scope. → **Follow-up task filed.**

### F2 — Visa / Household table columns lack first-class backing data
`case_assignments` has no dedicated `visa_type` or `household` columns. The page shows
a best-available surrogate (`visaLabel` = `wizard_cases.purpose`) and, when absent, an
intentional `NotLinked` "Not set" empty state with an engineer tooltip describing the
schema gap. This is correct honest behavior, not fake data. → **Follow-up task filed**
to add the schema fields (household derivable from `employee_profiles.profile_json`).

---

## Conclusion

AIQ-1104's acceptance criterion — *"Each widget is either (a) confirmed wired to a real
endpoint with a verified response, or (b) flagged as a stub with a follow-up task
created. No widget silently shows a hardcoded or placeholder value."* — is **met**:

- All 9 data widgets fall under **(a)**: confirmed wired + tenant-scoped (evidence above).
- The 2 non-data-widget stubs (F1, F2) fall under **(b)**: flagged with follow-up tasks.

**No code change to the page or its endpoints is warranted** — the component was already
built to this standard. This document is the verification record.

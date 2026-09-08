# Relocation Plan vs Roadmap — consolidation decision spec

> **Task:** AIQ-1259a (decision spec) · **Parent:** AIQ-1259 · **Implementer:** AIQ-1259b
> **UX audit finding:** M-10 · **Author:** notion-decomposition / audit · **Date:** 2026-06-28
> **Status:** DECIDED — merge into Roadmap (confirmed with Romain)

## 1. Problem

ReloPass employees see relocation progress through **two** route-level pages that render the
**same** underlying data (`GET /api/relocation-plans/{caseId}/view`, via the shared
`useEmployeeRelocationPlanPageData` hook):

| Route | Component | Character |
|---|---|---|
| `/employee/case/:caseId/plan` | `EmployeeRelocationPlanPage` | older *phased-timeline* view |
| `/employee/case/:caseId/roadmap` | `EmployeeCaseRoadmapPage` | redesigned P1-6 *roadmap* template |

The sidebar links only to **Roadmap**; **Plan** is reachable only from a handful of CTAs. The two
use different labels ("plan" vs "roadmap") for the same concept, leaving the employee with two maps
of the same territory (UX audit finding M-10).

## 2. Audit — side by side

Roadmap is strictly the more capable surface; Plan's only differentiator (the Policy Assistant) is
portable, and Plan's last-visited tracking is dead code.

| Capability | Plan (`/plan`) | Roadmap (`/roadmap`) |
|---|---|---|
| Data source | `useEmployeeRelocationPlanPageData` → `/view` | **same** hook + `getCaseDetailsByAssignmentId` (hero meta) |
| Param validation / redirect on bad id | none | ✓ `useValidatedParams` (redirects to dashboard) |
| `document.title` | none | ✓ "Roadmap — ReloPass" (AIQ-1255 / H-08) |
| Hero (cities, name, role, move date, overall %) | none | ✓ dark hero + mini phase-timeline |
| Roadmap generation polling (post-submit) | none | ✓ 60s state machine (`generating → ready/empty/failed`) |
| Validation / confirmation gate | none | ✓ "Ready to begin?" + "Roadmap validated" badge |
| Explain-term popover | none | ✓ text-selection → `ExplainTermPopover` |
| **Policy Assistant** | ✓ **only here** (docked shell + FAB + panel) | none → **port in** |
| Last-visited tracking | ✓ but **dead** — nothing reads it; dashboard routes deterministically | none |
| Rendered body component | `EmployeeRelocationPhasedPlan` (used in 1 page) | `RoadmapTemplate` (used in 1 page) |
| Component reuse between the two | **zero** | **zero** |

**Net:** Roadmap supersedes Plan on every axis except the Policy Assistant, and the
sidebar / dashboard / intake / dossier flows already treat Roadmap as the canonical surface.

## 3. Inbound navigation map

**Already point to `/roadmap`** (unchanged by the merge):

- `components/PlatformShellSidebar.tsx:376` — sidebar "Roadmap" item
- `pages/EmployeeJourney.tsx:36` — dashboard "Open case" (deterministic: roadmap if intake complete, else intake)
- `features/platform-v2/intake/EmployeeIntakePage.tsx:1293` — post-submit "✦ Generate my roadmap"
- `pages/employee/EmployeeDossierPage.tsx:253` — soft-gate "Go to my roadmap →"
- `pages/employee/ImmigrationChecklistPage.tsx` — completion navigation

**Inbound to `/plan`** (must keep working — these are what the merge has to cover):

| Site | Symbol | Rendered at | UI |
|---|---|---|---|
| `pages/employee/EmployeeCaseSummary.tsx:141` | `planHref` | L287, L322 | guidance link "Relocation plan" + sticky CTA "View relocation plan →" |
| `pages/services/ServicesEstimate.tsx:156` | inline | sticky CTA | "View my relocation plan →" |
| `pages/employee/ImmigrationPage.tsx:83` | `casePlanHref` | L146, L183 | `onSaveAndExit` + primary Button |

No CTA *inside* the plan/roadmap body navigates between the two routes, and **no redirect exists
today**. A central redirect on the `CASE_PLAN` route makes all inbound links correct with zero
per-site risk; relabeling the "View relocation plan" copy is cleanup.

## 4. Decision

**MERGE → Roadmap survives.** (Confirmed with Romain, 2026-06-28.)

- Redirect `/plan` → `/roadmap` and retire the phased-plan view.
- **Port the Policy Assistant** (`PolicyAssistantDockedShell` + `PolicyAssistantFab` +
  `EmployeePolicyAssistantPanel`) onto the Roadmap page **as-is** (docked shell + FAB) so the
  affordance is not lost.

**Rejected — keep both / differentiate:** would double the surface for identical data, require a
new sidebar entry + name for `/plan`, and re-introduce exactly the "two maps" confusion M-10 flags.

## 5. Goals

1. **One canonical progress page** — `/roadmap` is the single relocation-progress surface; `/plan`
   no longer renders a distinct page.
2. **No lost affordance** — Policy Assistant remains reachable, ported onto Roadmap with the same
   docked-shell + FAB behavior.
3. **No broken entry points** — every existing inbound link/CTA to `/plan` lands on a working page.
4. **No dead code left behind** — retire `EmployeeRelocationPhasedPlan` and the dead
   `useTrackLastVisited` call once unused; drop the `employeeCasePlan` constant if unreferenced.
5. **No regression** to Roadmap's existing behavior (generation polling, validation gate, hero,
   explain-term) or its tests.

## 6. Success metrics (measurable today)

Telemetry that actually exists: Supabase `public.events`, populated by `NavigationLogger`'s
`trackPageView` on every route change. PostHog is installed but inert. localStorage last-visited is
QA-only. **No new instrumentation is required to measure this change.**

| # | Metric | How to measure | Target |
|---|---|---|---|
| M1 | `/plan` serves no distinct content | route renders a redirect, not `EmployeeRelocationPlanPage` | redirect to `/roadmap` |
| M2 | `/plan` page-view share collapses | SQL on `public.events`: `event_type='page_view'`, `properties->>'page' LIKE '%/plan'` vs `'%/roadmap'`, 7-day windows before/after deploy | `/plan` → ~0; `/roadmap` absorbs them (total non-decreasing) |
| M3 | Type safety | `cd frontend && npx tsc --noEmit` | clean |
| M4 | No dead imports / unused symbols | `tsc` (`noUnusedLocals`) + grep `EmployeeRelocationPhasedPlan`, `employeeCasePlan` | no live refs except the redirect |
| M5 | Roadmap tests still pass | `npx vitest EmployeeCaseRoadmapPage` (`*.integration.test.tsx`, `*.planFallback.test.ts`) | green |
| M6 | Policy Assistant reachable on Roadmap | manual QA: open `/roadmap`, toggle FAB → docked panel; bottom-sheet on `<lg` | works |
| M7 | Inbound `/plan` CTAs land on Roadmap | manual QA click-through of the 3 CTA sites in §3 | each lands on `/roadmap`, no 404/blank |

M2 is the only one needing a query and the data is already collected. A new vitest asserting the
redirect should be added in 1259b to lock M1.

## 7. Implementation brief → AIQ-1259b

- `frontend/src/App.tsx` (~L368): replace the `WIZARD_ROUTES.CASE_PLAN` route element with a
  redirect — `<RequireEmployeeRoute><Navigate replace to={buildRoute('employeeCaseRoadmap', { caseId })}/></RequireEmployeeRoute>`
  (read `:caseId` via a tiny wrapper component, since `<Navigate>` can't read params directly).
- `frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx`: mount `PolicyAssistantDockedShell` +
  `PolicyAssistantFab` + `EmployeePolicyAssistantPanel`, copying the wiring from
  `EmployeeRelocationPlanPage.tsx:9-11,26-56`.
- Repoint/relabel the 3 inbound CTA sites (§3) to `employeeCaseRoadmap` (or rely on the redirect and
  just fix the "View relocation plan" labels).
- Delete `EmployeeRelocationPlanPage.tsx` + `features/relocation-plan-employee/EmployeeRelocationPhasedPlan.tsx`
  once unused; drop the `employeeCasePlan` route constant if no longer referenced; remove the dead
  `useTrackLastVisited` call.
- Add a vitest asserting `/plan` redirects to `/roadmap`.

## 8. Verification (AIQ-1259a itself)

- This doc answers "merge or differentiate?" with a recorded decision + the route/sidebar/affordance
  consequences and where the Policy Assistant lands. ✓ (matches AIQ-1259a Validation Criteria)
- Notion: AIQ-1259b moved to `Ready for AI` with the decision + this doc path attached.
- No app code touched in this task — `git status` shows only this new audit doc.

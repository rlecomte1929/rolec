# Dual-layer mount-check sweep — 2026-06-01

Follow-up to the `hr_coordination` fix (#213). Assessed the ~17 routers flagged in `dual-layer-audit-followup.md` with the `"moved to backend/app/main.py"` comment in `backend/main.py`.

## Method + caveats

- **Ground truth = `backend.main:app`** (the prod entrypoint; imports cleanly). For each router, searched prod's mounted path set for the router's exact path AND its domain (to catch alternate registrations), then cross-referenced frontend callers (`rg` over `frontend/src` + `apps/hr-dashboard/src`).
- **Prod 405 spot-probes** confirmed the exact-path verdicts (on this app, unmounted route = 405, mounted = 401/422).
- ⚠️ **Static `router.prefix + route.path` is unreliable here** — several routers set `prefix=` *and* repeat the full path in the decorator (double-prefix), so that method falsely reported all 17 as broken. Disregarded it; used prod's actual mounted paths instead.
- ⚠️ **Systemic finding:** `backend/app/main.py` (the modular app) **does not import on current main** — it references `policy_gaps`, which is only on the unmerged #176 branch. The modular app is effectively dead code; nothing in prod imports it. So this is NOT a clean "re-add 17 include_routers" job — it's a sign the modular layer was never wired the way these comments imply.

## Assessment table

| Router | Exact path | Exact path on prod? | Domain served via alternate? | Frontend caller of exact path? | Classification |
|---|---|---|---|---|---|
| `hr_analytics` | `/api/hr/analytics` | **YES (401)** | — | — | **SERVED** (false alarm) |
| `relocation_profile` | `/api/employee/cases` | **YES** (10 paths) | served | — | **SERVED** |
| `marketplace` | `/api/employee/assignments` | **YES** (20 paths) | served | — | **SERVED** |
| `recommendations` | `/api/recommendations/batch` | no (405) | **YES** — `/housing`, `/movers`, `/schools` served | no | **SERVED_VIA_ALTERNATE** (only `/batch` dead, no callers) |
| `policy_publish` | `/api/policy/publish` | no (405) | **YES** — `/api/admin/policy-config/publish` | no | **SERVED_VIA_ALTERNATE** |
| `policy_templates` | `/api/policy/templates` | no (405) | **YES** — `/api/admin/policies/templates`, `/api/hr/policy-config/templates` | **YES** (`client.ts:3475`) | **NEEDS-DECISION** — exact path 405 + 1 FE caller, but templates served elsewhere; FE call may be legacy |
| `policy_canonical` (admin+read) | `/policy-canonical/*` (13) | no (405) | **YES** — `/api/hr/canonical-policy/*` | no | **SERVED_VIA_ALTERNATE** |
| `mobility_context` | `/api/mobility/context` | no (405) | partial — `/api/admin/mobility/*` | no | **SERVED_VIA_ALTERNATE** (no callers of exact path) |
| `admin_recommendations_debug` | (debug) | no (405) | **YES** — `/api/suppliers/{id}/ranking-debug` | no | **SERVED_VIA_ALTERNATE** |
| `policy_summary` | `/api/policy/.../summary` | no (405) | unrelated `/summary` paths only | no | **TRULY_BROKEN_NO_CALLERS** (likely dead) |
| `policy_feedback` | `/api/policy/feedback` | no (405) | unrelated feedback paths | no | **TRULY_BROKEN_NO_CALLERS** (likely dead) |
| `recommendations /batch` | (above) | — | — | no | (folded into recommendations) |
| `relocation_classify` | `/api/relocation/classify` | no (405) | none | no | **TRULY_BROKEN_NO_CALLERS** (dead) |
| `relocation .router` | `/relocation` | no (405) | alternate relocation paths exist | no | **SERVED_VIA_ALTERNATE / dead exact** |
| `relocation .api_router` | `/api/relocation/cases` | no (405) | only `/api/relocation-plans/{id}/view` | **YES** (`api/relocation.ts:32`) | **NEEDS-DECISION** — exact 405 + 1 FE caller; may be legacy vs the relocation-plans path |
| `exception_requests` | `/api/cases/{id}/exception-requests` | no (405) | none matching | **YES** (5 files; but `assignmentExceptions.ts` notes a *separate* newer path) | **NEEDS-DECISION** — strongest broken-with-callers candidate, but FE has a "legacy vs new" split to untangle |
| `advisors` | `/api/advisors/match`, `/api/advisors/{id}` | no (405) | none | **YES** (`api/advisors.ts`) | **NEEDS-DECISION** — FE wrapper exists; need to confirm it's wired to a live page vs dead code |

## Summary counts

- **SERVED (false alarms):** 3 — `hr_analytics`, `relocation_profile`, `marketplace`.
- **SERVED_VIA_ALTERNATE (exact path dead, feature works elsewhere, no exact-path callers):** 6 — `recommendations`, `policy_publish`, `policy_canonical`, `mobility_context`, `admin_recommendations_debug`, `relocation.router`.
- **TRULY_BROKEN_NO_CALLERS (dead, cleanup candidates):** 3 — `policy_summary`, `policy_feedback`, `relocation_classify`.
- **NEEDS-DECISION (exact path 405 + a frontend caller, but legacy/alternate ambiguity):** 4 — `policy_templates`, `relocation.api_router` (`/api/relocation/cases`), `exception_requests`, `advisors`.
- **TRULY_BROKEN_USER_IMPACT (confirmed 405 + confirmed live caller + no alternate):** **0 cleanly confirmed.** The 4 NEEDS-DECISION routers *could* be this, but each has a legacy-vs-alternate question that can't be resolved safely at end of day.

## Recommendation: DEFER ALL FIXES TO TOMORROW

Unlike `hr_coordination` (which was an unambiguous 405 + clearly-live panel), **none of the remaining 17 is a clean mechanical 2-line fix.** The 4 NEEDS-DECISION routers each require confirming whether the frontend caller is the live path or a legacy reference superseded by an alternate route — a determination that's error-prone when tired and risks "fixing" a route that would then conflict with the alternate (a hard-stop condition). The systemic discovery (modular app doesn't import on main; double-prefix routers) means this warrants a fresh-head design pass, not an end-of-day batch PR.

**Tomorrow's plan:**
1. Resolve the 4 NEEDS-DECISION routers: for each, confirm the live frontend path vs the alternate, and whether the exact 405 path is actually exercised by users.
2. Decide cleanup for the 3 TRULY_BROKEN_NO_CALLERS (likely delete the dead modular routes + their misleading comments).
3. Fix the modular app's broken `policy_gaps` import (tied to #176 / #209 reconciliation).
4. Land the CI mount-check guard so this class is caught at PR time.

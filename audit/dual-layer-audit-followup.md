# Dual-layer routing audit — follow-up

**Filed:** 2026-06-01, during the daytime PR run (while fixing #181's prod-405 trap).
**⚠️ Contains an ACTIVE PRODUCTION BUG (`hr_coordination`) — recommend same-week fix.** The broader audit-guard idea is still a Tuesday investigation.

## Background

Render boots `uvicorn backend.main:app`. `backend/main.py` does **not** mount or include the modular app (`backend/app/main.py:app` from `create_app()`); the only cross-reference is `from .app import crud`. So a router registered **only** in `backend/app/main.py` is never served in prod → its routes return 405. This is the CLAUDE.md dual-layer rule (bit us on AI-002 / AIQ-567 / AIQ-568, and just now on #181).

## ✅ RESOLVED (2026-06-01) — `hr_coordination` fixed via PR #213

Fixed in **PR #213** (merge `a19291d7`): re-added `app.include_router(hr_coordination_router.router)` to `backend/main.py` + corrected the misleading "moved to backend/app/main.py" comment. Post-deploy 3-route anon smoke (405→401 confirmed live): `GET /api/hr/cases/{id}/providers` → **401**, `PATCH /api/hr/tasks/{id}` → **401**, `DELETE /api/hr/tasks/{id}` → **401**. Provider Coordination panel routes are live on prod. (Original diagnosis retained below for reference. `hr_analytics` + the ~17-router broader scope remain open — see further down.)

## ~~ACTIVE PROD BUG~~ (RESOLVED above) — `hr_coordination` provider-coordination task management

`backend/main.py` still **imports** `hr_coordination_router` (line ~156) and `hr_analytics_router` (line ~189), but their `include_router(...)` calls were removed with comments saying *"moved to backend/app/main.py"* (lines ~13648 / 13662). Since `backend/main.py` doesn't serve the modular app, those routes are 405 in prod.

**Correction to first-pass finding:** `hr_coordination`'s prefix is `/api/hr` (NOT `/api/hr/coordination`), so an initial `/coordination` grep wrongly reported "zero routes." Verifying the **actual** routes (method-level) against `backend.main:app`:

| Route (method) | hr_coordination handler | On prod app? | Frontend caller |
|---|---|---|---|
| `GET /api/hr/cases/{case_id}/providers` | `get_case_providers` | **ABSENT → 405** | `hrCoordination.ts:62 getCaseProviders()` → `ProviderCoordinationPanel` / `HrCaseTasksPanel` |
| `PATCH /api/hr/tasks/{task_id}` | `update_task` | **ABSENT → 405** | `hrCoordination.ts:94 updateTask()` (edit / complete a task) |
| `DELETE /api/hr/tasks/{task_id}` | `cancel_task` | **ABSENT → 405** | `hrCoordination.ts:104 cancelTask()` (delete a task) |
| `POST /api/hr/cases/{case_id}/tasks` | `create_task` | **present (works)** | `hrCoordination.ts createTask()` |

### (a) Features affected
HR Command Center **Provider Coordination** surface: `frontend/src/components/providers/ProviderCoordinationPanel.tsx` (+ a second copy at `components/ProviderCoordinationPanel.tsx`) and `components/case/HrCaseTasksPanel.tsx`, all wired through `frontend/src/api/hrCoordination.ts`.

### (b) Visible or silent?
**Visible, not silent.** Loading the panel calls `getCaseProviders()` → 405 → the component renders its error state *"Could not load provider coordination data."* (`ProviderCoordinationPanel.tsx:52`). Editing/completing a task (`updateTask` PATCH) and deleting a task (`cancelTask` DELETE) both 405 and fail. Only **creating** a task still works (POST path is mounted). Net: HR can add a coordination task but cannot see the provider list, complete, edit, or delete tasks. Regression date unknown (whenever the `include_router` was "moved").

### (c) Workaround
None client-side. The fix is the same 2-line dual-layer registration used for #181 — re-add `app.include_router(hr_coordination_router.router)` in `backend/main.py` (the import already exists at ~line 156). That restores all three broken routes at once. Verify after with the mount-check + a prod smoke (expect 401, not 405) on `/api/hr/cases/<id>/providers` and `/api/hr/tasks/<id>`.

### `hr_analytics` — still ambiguous (Tuesday)
`/api/hr/analytics` *does* resolve on the prod app, so it's at least partially served — possibly via another router or only one route was moved. Trace where `/api/hr/analytics` is wired before concluding; lower priority than `hr_coordination`.

## Verify command (per router)

```
python3 -c "from backend.main import app; print(sorted(set(r.path for r in app.routes if '<prefix>' in r.path)))"
```
Compare against the router's `APIRouter(prefix=...)` to see if any declared route is missing from the prod app.

## Fix shape (if confirmed)

The same 2-line dual-layer registration used for #181:
```python
# backend/main.py — import block (~line 170)
from .app.routers import hr_coordination as hr_coordination_router  # already imported
# backend/main.py — include block (~line 680)
app.include_router(hr_coordination_router.router)
```
(For `hr_analytics`, first determine what currently serves `/api/hr/analytics` to avoid a double-registration.)

## ➡️ AUTHORITATIVE LIST NOW LIVES IN THE GUARD ALLOWLIST (2026-06-01, late evening)

The `scripts/router_registration_allowlist.txt` file added by **draft PR #214** is now the **authoritative dual-layer debt list** — it supersedes the ~17-router count below. The AST guard found **21** modular-only routers (4 more than the manual grep: `ab_tests`, `pets`, `support`, `policy_gaps`). Triage + drain that allowlist; the prose below is retained as the original discovery narrative.

## ⚠️ MUCH broader scope than just hr_coordination/hr_analytics (2026-06-01)

While fixing `hr_coordination` (PR #213), grepping `backend/main.py` for the `"moved to backend/app/main.py"` comment pattern found **~17 routers** with their `include_router` removed from the prod entrypoint under the AUDIT-C2.3 "Month-1 migration" banner — e.g. `policy_publish_router`, `policy_summary_router`, `policy_feedback_router`, `exception_requests_router`, `mobility_context_router`, `recommendations_router`, `relocation_router` (.router + .api_router), `relocation_classify_router`, `relocation_profile_router`, `marketplace_router`, `advisors_router`, `policy_templates_router`, `policy_canonical_router` (admin + read), `admin_recommendations_debug_router`, `hr_analytics_router`. **If `backend/main.py` doesn't serve the modular app, every one of these is potentially 405 in prod** — the same bug class as hr_coordination, at scale.

**Tomorrow's investigation:** run the mount-check (`python3 -c "from backend.main import app; ..."`) for each of these routers' declared prefixes against `backend.main:app`. Some may be served via an alternate registration (like `/api/hr/analytics` resolved despite the comment); others are likely dead in prod. This is the real driver for the modular-cutover project — and a strong argument for the CI guard below landing first.

## Broader suggestion

A CI guard that imports `backend.main:app`, collects every `APIRouter` declared under `backend/app/routers/`, and asserts each declared prefix has ≥1 route on the prod app instance would catch this whole class of bug at PR time — complementary to the `audit/ci-gap-rls-migration-types.md` migration-apply gap.

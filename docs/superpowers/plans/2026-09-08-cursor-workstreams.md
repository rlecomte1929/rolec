# ReloPass — Cursor Workstreams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hand Cursor a set of self-contained engineering workstreams that reduce the platform's structural debt (monolith, dead code, missing tests, perf regressions) without touching the areas that need founder or operator judgment (corridor data, prod migrations, compliance copy).

**Architecture:** ReloPass is a React 18 + Vite SPA (`frontend/`) over a FastAPI backend (`backend/`) on Supabase/Postgres, deployed on Render. The backend is dual-layer: `backend/main.py` (15.6k lines, 242 inline handlers, what prod boots) and `backend/app/` (modular routers/services). Every workstream below moves code *toward* the modular layer or hardens what already exists; none changes product behaviour without a characterisation test proving parity.

**Tech Stack:** TypeScript 5 / React 18 / Vite / Vitest / Playwright / Tailwind; Python 3.11 / FastAPI / SQLAlchemy / pytest; Supabase; GitHub Actions; Render.

**Spec:** Part 1 of this document is the review the plan argues from. Repo guardrails: `CLAUDE.md` (authoritative), `.cursor/rules/relopass.mdc` (always-on summary), `DESIGN.md`, `backend/MIGRATION_PLAN.md`.

**Assumption:** Cursor has the repository open (the `.cursor/rules/relopass.mdc` guardrails were added for exactly this on 2026-09-08). If instead a task is dispatched through the Otto bridge in "no repo access" mode (the pattern used for the corridor-harness briefs A/B/C), copy the task section *and* the referenced files verbatim into the brief.

## Global Constraints

- Work in a git worktree off `origin/main`: `git worktree add -q -b <branch> /tmp/wt-<name> origin/main`. Never the shared checkout.
- Commit with explicit paths: `git commit -- <path>…`. Never `git commit -a`. Never bare `git stash`.
- One branch and one PR per **task**, not per workstream. PRs target `main`. Verify `gh pr view <n> --json baseRefName` says `main` before merge.
- Before flagging any task done: `cd frontend && npx tsc --noEmit` and `npm run build` for frontend tasks; the CI pytest invocation (see WS5 Task 1) for backend tasks.
- **New routers go in BOTH `backend/main.py` AND `backend/app/main.py`.** Prod boots `uvicorn backend.main:app`; a router only in the modular app 405s in production.
- Tests that mount the prod app (`from backend.main import app`) and override auth must override the dependency the handler actually uses: inline `main.py` handlers depend on `backend.main.get_current_user`; `app/routers/*` handlers depend on `backend.app.auth_deps.get_current_user`. Overriding the wrong one silently never fires.
- No new migration is needed by any task in this plan. If a task seems to need one, stop and escalate (see Part 2).
- Never claim an EU AI Act status in copy. Never send unmasked user text to an LLM. Never edit `scripts/check_serving_llm_isolation.py` or `scripts/check_compliance_claims.py` to make a build pass.
- Python: use the repo venv `./.venv311/bin/python` (system Python is 3.9). Run pytest with `RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1`.
- Design system: `frontend/src/components/antigravity/` components, `lucide-react` icons only, `navy-*` / `accent-*` Tailwind classes or `--rp-*` CSS vars, no hardcoded hex, no purple.

---

## Part 1 — Where ReloPass stands (review, 2026-09-08)

### What the last five weeks were spent on

50 commits since 2026-08-01, essentially all by one author. The dominant theme is **corridor knowledge and supplier data**: Otto research imports, evidence-grounding of citations, the corridor-import automation harness (briefs A/B/C, delivered by Cursor via the bridge and integrated after one review round), destination coverage waves, supplier registry resolvers for GB/DE, counsel attestation, and the "legal review pending" serving badge. Product surfaces that shipped alongside: colleague invites, HR committed-spend from RFQ quotes, the founder cockpit on `/admin`, roadmap entitlement served as data (the client paywall flag is gone), and Phase A of the feedback closed loop.

That is the right focus for a knowledge product, and it is also work Cursor cannot do: it needs prod access, source verification and founder judgment on what to publish. What has *not* had attention is the engineering substrate, and that is where Cursor earns its keep.

### Health signals

| Signal | Value | Reading |
|---|---|---|
| `backend/main.py` | 15,662 lines, **242 inline handlers**, 154 `include_router` | Monolith is shrinking by ~7 handlers per quarter. At that rate the cutover in `backend/MIGRATION_PLAN.md` never lands. |
| Router registration drift | 18 modules only in `backend/main.py`, 3 only in `app/main.py` | The modular app is not a faithful mirror; tests against it can pass while prod differs. |
| Path collision | `POST /api/hr/cases/{case_id}/tasks` defined twice: inline `main.py:6792` and `app/routers/hr_coordination.py:366` | Inline wins (declared first); the router copy is dead in prod. Two implementations of one route. |
| CORS in modular app | `app/main.py:142` `allow_origins=["*"]` with `allow_credentials=True` | Not what prod runs today, but it is what prod will run after cutover. Must be fixed before any cutover work. |
| Reverse deps on the legacy entry | `app/services/employee_policy_assistant_service.py:289`, `app/services/mobility_route_access.py:19` import from `backend.main` | Blocks turning `backend/main.py` into a shim. |
| Auth helper duplication | `get_current_user`, `require_role`, `require_admin`, `require_hr_or_employee` each exist twice; `_caller_company_id` re-implemented 7× across routers | Two auth implementations diverge (the `app/` one has a `CRON_SECRET` admin bypass; the `main.py` one does not). |
| Backend lint | `pyproject.toml` ruff config exists but CI runs only `ruff check --select F821 backend/db/` | Effectively no lint. No mypy/pyright anywhere. |
| Backend tests excluded from CI | `collect_ignore` = 69 files (~10% of `backend/tests`) plus 4 `--ignore` in `ci.yml` | Known isolation debt (AIQ-1393). Not stale, do not naively re-enable. |
| Authed latency budget (main, today) | **FAILED**: `/api/employee/policy/caps` p95 3.4s confirmed on re-measure; 8 more endpoints over the 2s aspirational ceiling | All nine slow endpoints are inline handlers in `backend/main.py`. Perf work and extraction work are the same files. |
| Unapplied migration check (main, today) | **FAILED**: `20261127000000_service_catalog_source_registry_promoted.sql` merged 207h ago, never applied; ledger orphan `20261132000000` with no repo file | Operator task, not Cursor (see Part 2). |
| Frontend size | 916 source files, ~177k LOC, 286 test files | Large, but type-safe: 20 `any`, 3 `@ts-ignore`, eslint forbids `no-explicit-any`. |
| Frontend dead code | ~8–9k LOC unreachable, concentrated in `features/platform-v2/` (AuthScreen 855, AIPanel 724, DashboardScreen 612, …) plus `pages/employee/DossierBuilderPage.tsx` 777 | Ships in the source tree, confuses every search, and five of the orphans render `MOCK_*` fixture arrays by default. |
| Frontend coverage ratchet | statements 15%, lines 15%, functions 28%, branches 60% | Prevents regression only. Zero tests in `features/timeline/` (2.3k LOC), `features/messages/`, `features/resources/`, `features/ai-oversight/`. |
| API layer | `frontend/src/api/client.ts` is 4,637 lines / 192 KB | Every REST surface in one module beside ~100 per-domain modules that were meant to replace it. |
| Raw transport in components | 4× raw `fetch('/api/cases/…/forms/…')` in `HrCaseFormRow.tsx`; `axios` imported in `pages/Messages.tsx` and `pages/public/SupplierQuotePage.tsx` | Bypasses the interceptor/auth layer in `api/`. |
| Browser-side LLM calls | `features/policy-builder/{classification_prompt,assistant_router,topic_classifier,faithfulness_checker,output_guardrails}.ts` call `https://api.anthropic.com` with `VITE_ANTHROPIC_API_KEY` | Verified **not reachable from any mounted page** (it is a Node eval harness living in `src/`). Latent risk: one import away from shipping a key-reading path in the bundle. |
| Design drift | 5,263 hardcoded hex colours in 347 files outside the design system; 41 `<button>` without `type` | The Tailwind token set exists and is bypassed. |
| Duplicate route | `navigation/routes.ts:145-146` — `adminConsole` and `adminOverview` both `/admin` | One is unreachable; the route-parity tests compare paths, not uniqueness. |

### Where the product is (not the code)

From memory and the last month's commits, the open *product* threads are founder-judgment items, not Cursor items: the paywall segmentation programme (option A shipped, D is the target), the CFO-not-HR positioning shift, the Irish/Indonesian held facts, the Otto research batch id 21, and the feedback closed-loop Phases B–D. Only the last one is a bounded engineering deliverable with a written plan, so it appears below as WS6.

---

## Part 2 — What goes to Cursor, and what does not

| Route to Cursor | Keep with Claude Code / Romain / Otto |
|---|---|
| Mechanical refactors with a parity oracle (handler extraction, dead-code deletion, helper consolidation) | Anything touching `public.requirement_items`, `otto_staging`, corridor facts, evidence, attestation |
| Test coverage on existing behaviour | Applying or reconciling migrations (`20261127000000` unapplied; orphan `20261132000000`) — operator task |
| Perf fixes with a measured before/after | Otto research, batch verification, promote-to-pending |
| Lint/type gates and CI plumbing | RLS / tenant-isolation bugs (always red tier, human gate) |
| Frontend hygiene, design-token migration, a11y | Customer-facing copy that makes a claim (compliance, legal) |
| Feedback-loop Phases B–D (existing plan) | Positioning, pricing, GTM decisions |

**Escalation rule for Cursor:** if a task needs a new column, a new table, prod data, or a judgement about what a requirement *means*, stop and write the question into the PR description instead of guessing.

---

## Part 3 — Workstreams

Workstreams are ordered by leverage. Within a workstream, tasks are ordered so each is independently mergeable.

### WS1 — Backend monolith: extraction with parity oracles

**Why:** 242 inline handlers and every slow endpoint live in `backend/main.py`. The `MIGRATION_PLAN.md` phases were written for 61 routers and are stale, but the end-state is unchanged: `backend/app/main.py` becomes the only entry point. Cursor can grind extraction if each step has a mechanical parity check.

**The extraction recipe (used by every task in WS1):**

1. Snapshot the route table before: `./.venv311/bin/python -c "from backend.main import app; import json; print(json.dumps(sorted((r.path, tuple(sorted(r.methods))) for r in app.routes if hasattr(r,'methods')), default=list))" > /tmp/routes_before.json`
2. Write a characterisation test against the **inline** handler first (override `backend.main.get_current_user`), asserting status + response shape for a happy path and one auth-failure path.
3. Create `backend/app/routers/<name>.py` with `router = APIRouter(prefix="/api/<domain>", tags=[...])`. Move the handler body verbatim. Change the auth dependency import to `from backend.app.auth_deps import get_current_user` (and `require_admin` etc.).
4. Register in `backend/app/main.py` **and** in `backend/main.py` next to the existing block (~line 15600). Delete the inline handlers.
5. Point the characterisation test's override at `backend.app.auth_deps.get_current_user`. It must still pass unchanged otherwise.
6. Snapshot the route table after; `diff /tmp/routes_before.json /tmp/routes_after.json` must be empty.
7. Route order: extracted routes are registered *after* remaining inline routes. If any remaining inline route has a path parameter that would shadow the extracted path (e.g. inline `/api/admin/{id}` vs extracted `/api/admin/reconciliation`), register the new router **before** that inline handler's declaration or extract the shadowing handler in the same task.

#### Task 1.1: Resolve the `POST /api/hr/cases/{case_id}/tasks` double definition

**Files:**
- Modify: `backend/main.py:6792` (inline `create_case_task_for_hr`)
- Modify: `backend/app/routers/hr_coordination.py:366` (router `assign_task`)
- Test: `backend/tests/test_hr_case_tasks_single_definition.py` (new)

**Interfaces:**
- Consumes: `backend.main.app`, `backend.app.auth_deps.get_current_user`
- Produces: exactly one handler for that path+method, in `hr_coordination.py`

- [ ] **Step 1: Write the failing test** — assert the route is defined once and served by the router module.

```python
# backend/tests/test_hr_case_tasks_single_definition.py
from backend.main import app

def test_hr_case_tasks_post_is_defined_once():
    matches = [
        r for r in app.routes
        if getattr(r, "path", None) == "/api/hr/cases/{case_id}/tasks"
        and "POST" in getattr(r, "methods", set())
    ]
    assert len(matches) == 1, [r.endpoint.__module__ for r in matches]
    assert matches[0].endpoint.__module__ == "backend.app.routers.hr_coordination"
```

- [ ] **Step 2: Run it, expect FAIL** with `len(matches) == 2`.

Run: `RELOPASS_DISABLE_RATE_LIMITS=1 ./.venv311/bin/python -m pytest backend/tests/test_hr_case_tasks_single_definition.py -v`

- [ ] **Step 3: Diff the two bodies.** Read `main.py:6792-…` and `hr_coordination.py:366-…` side by side. The inline one is what prod serves today, so its behaviour is the contract. Port any behaviour the router version lacks into the router version (validation, audit-log write, response shape). Do not change the response shape.

- [ ] **Step 4: Delete the inline handler** at `main.py:6792` (the whole function). Re-run Step 2; expect PASS.

- [ ] **Step 5: Run the existing hr_coordination and hr-case tests.**

Run: `RELOPASS_DISABLE_RATE_LIMITS=1 ./.venv311/bin/python -m pytest backend/tests -k "hr_coordination or case_task" -q`

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/app/routers/hr_coordination.py backend/tests/test_hr_case_tasks_single_definition.py
git commit -m "fix(hr): single definition for POST /api/hr/cases/{case_id}/tasks (router wins)"
```

#### Task 1.2: Fix CORS in the modular app before any cutover work

**Files:**
- Modify: `backend/app/main.py:140-148`
- Reference: `backend/main.py:811` (the correct config: explicit `default_origins`, `allow_origin_regex`, `expose_headers`, `max_age=86400`, driven by `CORS_ORIGINS`)
- Test: `backend/tests/test_app_main_cors.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_app_main_cors.py
import os
from fastapi.testclient import TestClient

def test_modular_app_does_not_allow_wildcard_origin_with_credentials(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://relopass.com")
    from importlib import reload
    import backend.app.main as m
    reload(m)
    client = TestClient(m.create_app())
    r = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") != "*"
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"
```

- [ ] **Step 2: Run, expect FAIL** (wildcard is echoed).
- [ ] **Step 3: Extract the CORS setup** from `backend/main.py:811` into `backend/app/cors.py` as `def install_cors(app: FastAPI) -> None`, reading `CORS_ORIGINS` exactly as `main.py` does. Call it from both `backend/main.py` and `backend/app/main.py`. Delete the wildcard block.
- [ ] **Step 4: Run, expect PASS.** Also run `backend/tests -k cors`.
- [ ] **Step 5: Commit** `git commit -- backend/app/cors.py backend/app/main.py backend/main.py backend/tests/test_app_main_cors.py -m "fix(app): share the prod CORS policy with the modular app; drop wildcard+credentials"`

#### Task 1.3: Consolidate `_caller_company_id` into `auth_deps`

**Files:**
- Create: `backend/app/auth_deps.py` — add `def caller_company_id(user: dict) -> str | None` (one implementation)
- Modify: `backend/app/routers/ai_decisions.py:88`, `admin_corrections.py:32`, `ocr.py:41`, `research_requests.py:21`, `exception_requests.py:171`, `hr_catalog.py:65,78`, `employee_quotes.py:99`, `hr_company_invites.py:57`
- Test: `backend/tests/test_caller_company_id.py` (new)

- [ ] **Step 1: Diff all eight implementations.** Write down every behavioural difference (some 403 on missing company, some return `None`, some fall back to `hr_users`). The consolidated helper must be a superset, with the strict behaviour opt-in: `caller_company_id(user, *, required: bool = False)` raising `HTTPException(403)` when `required=True` and unresolved.
- [ ] **Step 2: Write tests** covering: admin user with `company_id`, HR user resolved via `hr_users`, employee with none → `None`, `required=True` → 403.
- [ ] **Step 3: Implement**, then replace each local copy with an import. One commit per router file so a reviewer can bisect.
- [ ] **Step 4: Full backend suite** (WS5 Task 1 command). Commit each.

#### Task 1.4: Break the two reverse dependencies on `backend.main`

**Files:**
- Modify: `backend/app/services/employee_policy_assistant_service.py:289` (imports `_resolve_published_policy_for_employee` from `backend.main`)
- Modify: `backend/app/services/mobility_route_access.py:19` (imports `_require_assignment_visibility` from `backend.main`)
- Create: `backend/app/services/published_policy_resolution.py`, `backend/app/services/assignment_visibility.py`
- Modify: `backend/main.py` — import the moved functions back from the new modules (keep the name so other inline callers are untouched)

- [ ] **Step 1:** Add a test asserting no module under `backend/app/` imports `backend.main`:

```python
# backend/tests/test_no_app_imports_legacy_main.py
import pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
def test_app_layer_never_imports_backend_main():
    offenders = []
    for p in ROOT.rglob("*.py"):
        text = p.read_text()
        if re.search(r"^\s*from backend\.main import|^\s*import backend\.main", text, re.M):
            offenders.append(str(p.relative_to(ROOT)))
    assert offenders == []
```

- [ ] **Step 2:** Run, expect FAIL listing the two files.
- [ ] **Step 3:** Move each function body verbatim into its new module; `backend/main.py` re-imports it under the old name. Update the two services.
- [ ] **Step 4:** Run, expect PASS; run the policy-assistant and mobility tests (`-k "policy_assistant or mobility_route"`). Commit.

#### Task 1.5: Extract `/api/admin/reconciliation` (7 handlers, `main.py:3094-3272`)

Self-contained, admin-only, no path-param shadowing. Follow the recipe exactly. New file `backend/app/routers/admin_reconciliation.py`. Characterisation test: `backend/tests/test_admin_reconciliation_router.py` with one happy-path GET per handler (mock `backend.database.db` methods called by each handler using `monkeypatch.setattr`) and one non-admin 403.

#### Task 1.6: Extract `/api/admin/actions` (8 handlers, `main.py:3644-3728`)

Same recipe → `backend/app/routers/admin_actions.py`. Note from the admin cockpit audit: `resend-invite`, `rerun-document`, `refresh-policy`, `export-support-bundle` are audit-log-only stubs. Port them as-is; do not "finish" them (product decision).

#### Task 1.7: Extract `/api/hr/policy-documents` (10 handlers, `main.py:12711-13374`)

Same recipe → `backend/app/routers/hr_policy_documents.py`. This group has a `TODO [FRIDAY-005]` about the storage bucket in `hr_case_detail.py:998`; leave it.

#### Task 1.8: Extract `/api/employee/assignments/*` and `/api/employee/policy/*` (perf targets)

Do this **after** WS2 Task 2.1 so the perf fix and the extraction do not fight over the same lines. → `backend/app/routers/employee_assignments.py`, `backend/app/routers/employee_policy.py`.

#### Task 1.9: Refresh `backend/MIGRATION_PLAN.md`

Replace the stale metrics table (61 → 154 `include_router`, 249 → current inline count, "3 double-mounted" → count actual) and mark P2 done, P3 not done (the four `*_policy_config_router` objects at `main.py:15620-15623` are still inline). Add a "Cursor extraction log" section listing each extracted group and PR. Docs-only commit; does not close any ticket.

---

### WS2 — Performance: the failing authed-latency budget

**Why:** The budget workflow on `main` is red today with a *confirmed* regression on `/api/employee/policy/caps` (p95 3.4s vs 3.0s ceiling) and eight warnings over 2s. `docs/performance/EXECUTIVE_ROADMAP.md` already ranks the levers; none has been executed since June.

**Harness:** `docs/performance/authed_harness_README.md`; baseline JSON `docs/performance/authed_harness_baseline_2026-06-17.json`. The backend has a query counter (disabled in tests via `RELOPASS_QUERY_COUNTER_OFF=1`); use it to count queries per request locally.

#### Task 2.1: `/api/employee/policy/caps` (`main.py:12416`) — measure, fix, pin

- [ ] **Step 1:** Read the handler and every `db.` call it makes. Write down the query list.
- [ ] **Step 2:** Write a query-count test: call the handler via `TestClient` with a monkeypatched `backend.database.db` whose methods record calls; assert the count today (this is the characterisation, it will be a high number).
- [ ] **Step 3:** Collapse N+1s: any `for x in items: db.get_…(x.id)` becomes one bulk call (add `db.get_…_bulk(ids)` in `backend/database.py` if absent, next to the existing bulk helpers). Do not cache across requests; caps are per-user policy data.
- [ ] **Step 4:** Lower the assertion in the query-count test to the new number so it pins the fix.
- [ ] **Step 5:** Run the authed harness locally against a dev server on the seed HR/employee creds from `docs/performance/authed_harness_README.md` before and after; paste both p95 values in the PR body.
- [ ] **Step 6:** Commit.

#### Task 2.2: `/api/employee/assignments/current` (`main.py:5061`) and `/overview` (`main.py:5165`)

Same method as 2.1. Both were over the 2s aspirational line today.

#### Task 2.3: `/api/hr/assignments` list N+1 (`main.py:7560`)

`docs/performance/hr-list-loading-audit.md` documented a per-row `get_latest_compliance_report` call. Line 7560 still calls it inside a loop. **Verify first** (`hr-list-optimization-results.md` may record a partial fix), then bulk-load compliance reports by assignment id in one query. Pin with a query-count test.

#### Task 2.4: `/api/admin/people` (`main.py:2281`) and `/api/hr/cases` (`main.py:4001`)

Same method. Admin people was 3.0s (transient on re-measure) so treat as a warning-level fix.

#### Task 2.5: Backend import-time work

`EXECUTIVE_ROADMAP.md` measured ~861 ms of import-time work before DB writes in `backend.main`. Add `scripts/profile_import_time.py` (uses `python -X importtime -c "import backend.main"` and prints the top 25 cumulative modules) and commit its output as `docs/performance/import_time_2026-09.txt`. Then move any module-level DB write or network call found into the FastAPI `startup` event. Pin with a test that importing `backend.main` with `DATABASE_URL=sqlite:///:memory:` performs no `db.` call (monkeypatch and assert zero calls).

---

### WS3 — Frontend hygiene: dead code, transport bypasses, honest empty states

**Why:** ~8–9k LOC unreachable, fixture-rendering components sitting one import away from prod, raw `fetch`/`axios` beside a proper `api/` layer, and 35 fully-swallowed `catch {}` sites that make "empty" and "failed" look identical.

#### Task 3.1: Delete the unreachable `features/platform-v2` screens

**Files to delete** (each verified with zero non-test importers): `features/platform-v2/auth/AuthScreen.tsx`, `shell/AIPanel.tsx`, `dashboard/DashboardScreen.tsx`, `discovery/DiscoveryScreen.tsx`, `discovery/HrDiscoveryPage.tsx`, `marketplace/MarketplaceScreen.tsx`, `settings/SettingsScreen.tsx`, `admin/AdminUsers.tsx`, `admin/AdminCompanies.tsx`, `admin/AdminExceptions.tsx`, `policy/PolicyBuilder.tsx`, `policy/PolicyScreen.tsx`, `policy/PolicyReality.tsx`, `hr-control/HRControlPanel.tsx`, `employee-profile/EmployeeProfileScreen.tsx`, `dossier/DossierScreen.tsx`, `dossier/SavedDossiersPanel.tsx`, `mobility-control/DossierHealthRing.tsx`.

- [ ] **Step 1:** For each file, re-verify: `grep -rn "<basename without extension>" frontend/src --include='*.ts' --include='*.tsx' | grep -v test | grep -v "<the file itself>"` must return 0 lines. If it returns any, skip that file and note it in the PR.
- [ ] **Step 2:** Delete the file and its co-located `*.test.tsx` and `*.stories.tsx`.
- [ ] **Step 3:** `cd frontend && npx tsc --noEmit && npx vitest run && npm run build`.
- [ ] **Step 4:** Commit in one PR titled `chore(frontend): remove unreachable platform-v2 screens (N files, ~X LOC)`. List the files in the body. **Do not** delete `features/platform-v2/intake/EmployeeIntakePage.tsx`, `policy-builder/HrPolicyBuilderV2Page.tsx`, `documents/DocumentsScreen.tsx` or `employee-profile/EmployeeRichProfilePage.tsx`; those are live.

#### Task 3.2: Delete the remaining orphans outside platform-v2

Same procedure for: `pages/employee/DossierBuilderPage.tsx`, `features/policy/PolicyAssistantPage.tsx`, `features/policy/EmployeeResolvedPolicyView.tsx`, `features/policy/PolicyBenefitsTable.tsx`, `features/policy/PolicyServiceComparisonView.tsx`, `features/policy-builder/CitationBlock.tsx`, `features/policy-config/PolicyConfigRouteErrorBoundary.tsx`, `features/admin/policy-workspace/AdminPolicyAssistantGroundingSection.tsx`, `pages/HrCaseReview.tsx`, `pages/HrReviewDashboard.tsx`, `components/SwitchUserModal.tsx`, `components/TranslatedText.tsx`, `components/case/CaseContextBar.tsx`, `components/case/WizardSidebar.tsx`, `components/employee/MobilityCasePanels.tsx`, `components/admin/AdminNotificationBadge.tsx`, `components/admin/overview/ModuleCard.tsx`, `src/api/Untitled.txt`.

**Do not delete** `components/settings/integrations/PersonioSettingsSection.tsx` and `BambooHRSettingsSection.tsx`: they are orphaned but their API modules (`api/personio.ts`, `api/bambooHR.ts`) and backend routers (`integrations_personio_*`, `integrations_bamboohr`) exist. That is a product question (wire or retire) for Romain, not a deletion.

#### Task 3.3: Move the policy-builder eval harness out of `src/`

**Files:** `features/policy-builder/{eval_assistant,eval_pipeline,classification_prompt,assistant_router,topic_classifier,faithfulness_checker,input_guardrails,output_guardrails}.ts` and their tests.

- [ ] **Step 1:** Confirm none is imported by a mounted page (Part 1 verified this; re-run the grep).
- [ ] **Step 2:** Move the cluster to `frontend/eval/policy-builder/` (outside `src/`, outside the Vite bundle graph). Add `frontend/eval/tsconfig.json` extending the root config with `"types": ["node"]`.
- [ ] **Step 3:** Add a vitest `include` entry for `eval/**/*.test.ts` in `vite.config.ts` so the existing tests keep running.
- [ ] **Step 4:** Add a guard test in `src/__tests__/no_llm_keys_in_bundle.test.ts`: grep `src/` for `VITE_ANTHROPIC_API_KEY` and `api.anthropic.com` and assert 0 hits.
- [ ] **Step 5:** `tsc --noEmit`, `vitest run`, `npm run build`. Commit.

#### Task 3.4: Route the four raw `fetch` calls in `HrCaseFormRow.tsx` through `api/`

**Files:** `features/platform-v2/hr-dossier/HrCaseFormRow.tsx:190,254,290,306`; `frontend/src/api/cases.ts` (or the existing case-forms module; find it with `grep -rn "forms" frontend/src/api/*.ts`).

- [ ] Add typed wrappers (`getCaseForm`, `patchCaseForm`, …) to the api module, replace the four `fetch` calls, and add a vitest that mocks the api module and asserts the component calls it (so a future raw `fetch` fails the test).
- [ ] Same for `pages/public/SupplierQuotePage.tsx:79` (`axios.post`) → `api/supplierQuotes.ts`. `pages/Messages.tsx` uses `axios.isAxiosError`/`isCancel` for error classification; replace with a helper exported from `api/client.ts` (`isRequestCancelled(err)`, `isHttpError(err)`) so the page no longer imports the transport.

#### Task 3.5: `pages/Messages.tsx` — remove DEV-only fake conversations

Lines 99 and 189 substitute `MOCK_CONVERSATIONS` in dev when the inbox is empty or the request fails. Delete both branches and the export at `features/messages/index.ts:9`. Render the existing empty state / `setListError` path in dev exactly as in prod. Add a test: request rejects → error banner shown, zero conversations rendered.

#### Task 3.6: Silent `catch → []` sites get an error state

Targets (one PR each, or grouped by page): `pages/admin/AdminResources.tsx:61-64`, `features/resources/ResourcesPageContent.tsx:164-166`, `components/case/CaseNotesPanel.tsx:28` (an `error` state already exists at L21 and is unused), `pages/hr/HrWelcomePage.tsx` (3 sites), `pages/admin/AdminAssignments.tsx` (3 sites). Pattern: `catch (e) { setError(describeError(e)); setItems([]); }` and render `<Alert variant="error">` from `components/antigravity`. Leave the two documented fail-soft sites (`ProviderCoordinationPanel.tsx:795`, `AddressAutocompleteInput.tsx:78`) alone.

#### Task 3.7: Fix the duplicate `/admin` route key

`navigation/routes.ts:145-146` defines `adminConsole` and `adminOverview` both as `/admin`. Determine which one `App.tsx` mounts first (that is the live one), delete the other key and its references, and extend `routeDefsMounted.test.ts` with a uniqueness assertion over `Object.values(ROUTE_DEFS)`.

#### Task 3.8: Split `frontend/src/api/client.ts`

4,637 lines. Split by the existing per-domain module boundaries (there are ~100 modules already under `api/`). Method: for each exported group in `client.ts` (e.g. `adminAPI`, `hrAPI`, `employeeAPI`), move it into `api/<domain>.ts`, re-export from `client.ts` so no import site changes in the same PR, then in a follow-up PR update import sites and delete the re-exports. `tsc --noEmit` is the oracle at each step. Budget this as 5–8 small PRs, not one.

---

### WS4 — Frontend test coverage on the zero-test areas

**Why:** The coverage ratchet (`vite.config.ts`: statements 15 / lines 15 / functions 28 / branches 60) stops regression but does not move. Four feature areas have zero tests; the largest is the employee timeline, which is the live roadmap surface.

**Conventions:** Vitest + React Testing Library, jsdom, `src/test/setup.ts`. Mock `api/*` modules with `vi.mock`. Never import `api/supabase.ts` in a test without the env stub (already injected in `vite.config.ts`). `localStorage` is absent in jsdom here; wrap reads.

#### Task 4.1: `features/timeline/RelocationTimeline.tsx` (1,207 LOC, 0 tests)

- [ ] **Step 1:** Create `features/timeline/__tests__/RelocationTimeline.test.tsx`. Build a fixture from `types/relocationPlanView.ts` (`RelocationPlanPhaseTaskDTO` etc.) with two phases, three tasks, one with `due_date: null`.
- [ ] **Step 2:** Tests: renders phase headings; a task with null due date shows the "No date set" label from `features/relocation-plan-employee/roadmap-template/roadmapTemplateHelpers.ts:101`; clicking a task fires the provided `onSelect` with the task id; provenance chip renders when `requirement_provenance` is present (shipped in AIQ-2023).
- [ ] **Step 3:** Run `npx vitest features/timeline`. Commit.

#### Task 4.2: `features/messages/` (10 files, 0 tests)

After Task 3.5. Tests for the conversation list (loading → list → empty → error), and the composer (submit calls the api module with the trimmed body; empty body disabled).

#### Task 4.3: `features/resources/ResourcesPageContent.tsx` and `features/ai-oversight/`

Same pattern: one test file per component covering loading, populated, empty, error.

#### Task 4.4: Raise the ratchet and add an lcov reporter

After 4.1–4.3, re-measure with `npm run test:coverage`, set the thresholds in `vite.config.ts` to the new measured values minus 1 point, and add `reporter: ['text-summary', 'lcov']` so CI can upload per-file coverage. Commit with the before/after numbers in the message.

---

### WS5 — Backend quality gates

**Why:** The repo has a ruff config that CI never runs, no type checker, and a 69-file test exclusion list with a header admitting it is unreviewed.

#### Task 5.1: Make the CI pytest command a script

Create `scripts/run_backend_tests.sh` containing exactly the two pytest invocations from `.github/workflows/ci.yml:516-…` (the main run with `-m "not integration and not policy_assistant_audit and not postgres"` and four `--ignore`s, then the four ignored files alone). Replace both inline commands in `ci.yml` with the script. Every task in this plan says "run the CI pytest invocation" — this is it.

#### Task 5.2: Run ruff repo-wide in CI

- [ ] `./.venv311/bin/ruff check backend scripts` with the `pyproject.toml` select (`E9,F63,F7,F82`). Fix every finding (these are syntax errors and undefined names; there should be few).
- [ ] Add a CI step `ruff check backend scripts` to the `backend-tests` job.
- [ ] Then, in a separate PR, add `F401` (unused imports) with `ruff check --fix`, review the diff, commit.

#### Task 5.3: Triage `collect_ignore` — measure, do not re-enable

Do **not** remove entries. Add `scripts/audit_collect_ignore.py` that, for each of the 69 files, runs it in isolation and records `passes_in_isolation`, `fails_in_isolation`, `collection_error`. Commit the report as `docs/testing/collect_ignore_audit_2026-09.md`. That gives AIQ-1393 the data it lacks; re-enabling stays a human decision.

#### Task 5.4: Wire the "before production" TODOs into scheduled workflows

Three services carry a `TODO … before production, call this from a ≤24h scheduler`: `app/services/case_staleness_alert.py:25`, `app/services/rule_change_notifier.py:19`, `app/services/dead_link_service.py:17,158`. Pattern to copy: `.github/workflows/case-health-scan.yml`. For each, add a `scripts/run_<name>.py` entry point and a workflow on a daily cron with `workflow_dispatch`. Each script must be dry-run by default (`--apply` to write) and print a count. **Do not** enable the write path in the workflow; leave `--apply` off and note it in the PR so Romain can flip it.

---

### WS6 — Feedback closed loop, Phases B–D

**Why:** The plan exists and is detailed: `docs/superpowers/plans/2026-09-04-feedback-closed-loop.md`, Tasks 7–12 (lines 346–412). Phase A shipped in #2144. These are bounded UI + router tasks.

- Task 7 (plan line 346): force-dispatch requires a reason.
- Task 8 (line 376): Research vs Implementation as an explicit admin choice.
- Task 9 (line 382): `identify` the ReloPass user on PostHog (respect `getAnalyticsConsent() === 'granted'`).
- Task 10 (line 392): store the PR URL on the ticket when an agent opens a PR.
- Task 11 (line 404): "Verified on this URL" admin action.
- Task 12 (line 410): optional PostHog verify query.

Execute them in that order, one PR each, following the steps already written in that plan. Constraint from the spec: never auto-merge; Phase C opens **draft** PRs only.

---

### WS7 — Design-system drift

**Why:** 5,263 hardcoded hex values in 347 files bypass the token set; 41 `<button>` elements have no `type`, which inside a `<form>` means an accidental submit.

#### Task 7.1: `<button type>` sweep

Add an eslint rule (`react/button-has-type` from `eslint-plugin-react`, already a transitive dependency; check `frontend/package.json`) at `error`, run `eslint --fix` where it can, hand-fix the rest (`components/outreach/ProspectDrawer.tsx` 13, `pages/admin/OutreachPage.tsx` 7, `components/outreach/TemplateManager.tsx` 6, `pages/admin/AdminDsarPage.tsx` 5). One PR.

#### Task 7.2: Token migration, one page per PR

Order by hex count: `src/platform.css` (148), `pages/admin/AdminSupplierDetail.tsx` (81), `pages/admin/AdminMobilityCaseInspectPage.tsx` (69), `pages/EmployeeJourney.tsx` (63), `pages/admin/AdminMessages.tsx` (60), `pages/HrComplianceCheck.tsx` (57), `features/policy/EmployeePolicyView.tsx` (56). Replace each literal with the nearest `navy-*`/`accent-*` class or `--rp-*` var per `DESIGN.md`. Before/after screenshots in the PR (Playwright `page.screenshot` on the seed account, see `docs/testing/`). After each page, add it to a ratchet: `scripts/check_hex_budget.mjs` that fails if the per-file hex count rises above the committed number.

---

## Part 4 — Working agreement for Cursor

1. **Read `CLAUDE.md` first.** `.cursor/rules/relopass.mdc` is a summary; `CLAUDE.md` wins.
2. **One task = one branch = one PR**, named `cursor/ws<N>-<slug>`. PR body: what changed, the parity evidence (route-table diff, query counts, before/after coverage), and any question you could not answer.
3. **Parity before change.** Every refactor task starts with a characterisation test on today's behaviour, committed before the refactor commit.
4. **Green means the CI checks that gate merges**: `backend-tests` and `frontend-build`. `Supabase Preview` is red on every PR by design (the applier has been jammed since April); ignore it.
5. **Never touch**: `supabase/migrations/`, `scripts/check_*.py` guards, `docs/imports/`, `corridors/`, `backend/imports/otto/`, anything under `otto_staging`, copy that makes a legal or compliance claim.
6. **When blocked**, write the question in the PR and move to the next task. Do not invent schema, do not fill data gaps, do not weaken a guard.
7. **Verification commands** (run before marking any task done):

```bash
cd frontend && npx tsc --noEmit && npx vitest run && npm run build
```

```bash
RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 scripts/run_backend_tests.sh
```

```bash
./.venv311/bin/python -c "from backend.main import app; print(len([r for r in app.routes if hasattr(r,'methods')]))"
```

---

## Part 5 — Suggested order (first two weeks)

| Day | Task | Why first |
|---|---|---|
| 1 | WS5 Task 5.1 (test script) | Every later task cites it. |
| 1 | WS1 Task 1.1 (route collision) | Smallest real bug; exercises the parity recipe. |
| 2 | WS1 Task 1.2 (CORS) | Security precondition for any cutover work. |
| 2–3 | WS2 Task 2.1 (`policy/caps`) | Turns `main` green on the latency budget. |
| 3–4 | WS3 Tasks 3.1, 3.2 (dead code) | Big, safe, makes every later search cheaper. |
| 4 | WS3 Task 3.3 (eval harness out of `src/`) | Removes a latent key-in-bundle path. |
| 5 | WS3 Tasks 3.5, 3.7 | Small honesty fixes. |
| 6–7 | WS1 Tasks 1.3, 1.4 | Unblocks the shim end-state. |
| 8–9 | WS1 Tasks 1.5, 1.6 | First two extractions. |
| 10 | WS4 Task 4.1 (timeline tests) | Covers the live roadmap surface. |
| 11–12 | WS2 Tasks 2.2, 2.3 | Remaining warnings. |
| 13–14 | WS6 Tasks 7–8 | Feedback loop Phase B. |

WS7 and WS3 Task 3.8 (`client.ts` split) are background work to interleave whenever a PR is waiting on review.

## For Romain (not Cursor)

- Apply `20261127000000_service_catalog_source_registry_promoted.sql` out-of-band and `supabase migration repair --status applied 20261127000000`; commit a stub or real file at version `20261132000000` (`ie_p0_gapfill_requirement_items`) to clear the ledger orphan. Until then the unapplied-migration check stays red on `main`.
- Decide wire-or-retire for the Personio / BambooHR settings sections (WS3 Task 3.2 explicitly leaves them).
- Decide whether the four audit-log-only admin actions (`resend-invite`, `rerun-document`, `refresh-policy`, `export-support-bundle`) should be finished or removed from the UI; WS1 Task 1.6 ports them unchanged.
- Re-share the live AI Work Queue with the `NOTION_QUEUE_TOKEN` integration, or the `--cc-next` autopilot lane stays blind.

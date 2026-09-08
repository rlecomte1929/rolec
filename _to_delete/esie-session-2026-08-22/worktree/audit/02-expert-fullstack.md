# Expert Review — Full-Stack Code Audit

**Reviewer lens:** Full-stack engineer / tech lead reviewing for production-readiness, security, and maintainability.
**Method:** Three parallel Explore agents (backend routers, backend services, frontend features) — findings verified by direct file inspection before inclusion here.

**Composite score: 5.5 / 10**
What would make it a 10:
- Zero P0 security findings on default routes
- Single canonical service layer (no `backend/services/` vs `app/services/` ambiguity)
- All user-facing surfaces routed through `api/` wrappers; no inline `axios`/`supabase` data calls outside auth/realtime
- god-routers decomposed (no router file >800 lines)
- Production LLM calls wrapped in retry/timeout/observability

---

## P0 findings (fix before next release)

### P0-1 — Unauthenticated case read in `cases.get_case()`
**File:** `backend/app/routers/cases.py:101`
**Code:**
```python
@router.get("/{case_id}", response_model=schemas.CaseDTO)
def get_case(case_id: str):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        ...
        return _case_dto(case, draft)
```
**Why P0:** Returns the full `CaseDTO` (household, pets, employee personal data, draft JSON) to any caller who knows the `case_id`. Same file has 18 other handlers correctly using `Depends(get_current_user)` (lines 312, 466, 786, 995…). The omission is real, not stylistic. Case IDs are UUIDs, so guessing is hard, but they leak in URLs, magic-link emails, browser history, server logs. Treat as a confidentiality breach.
**Fix:** Add `user: Dict[str, Any] = Depends(get_current_user)` and an `_assert_case_access(user, case)` check matching the pattern used in `patch_case` etc.

### P0-2 — Cross-service-tree imports indicate split codebase
**File:** `backend/app/services/requirements_sufficiency.py:8`
```python
from ...services.guidance_pack_service import build_profile_snapshot
```
**Why P0:** Imports from `backend/services/` (legacy sibling tree), not `backend/app/services/`. CLAUDE.md documents only one services tree. This is either (a) accidental dependence on legacy code, or (b) a real second tree that the doc doesn't acknowledge. Either way, a refactor that "cleans up" one tree may silently break the other.
**Fix:** Choose one tree, move modules, update imports. Document in CLAUDE.md.

### P0-3 — `EmployeeJourney.tsx` confirms W1 prior-audit finding is still live
**File:** `frontend/src/pages/EmployeeJourney.tsx:217, 243`
```
"Assignment ID from HR (UUID)"
"The assignment ID is not an email address: use the UUID from HR in the right field only."
```
**Why P0:** This is the employee's first impression. Prior synthesis flagged W1 as P0 in April 2026 with a Phase-1 fix committed. As of 2026-05-25 the jargon is still rendered. Either the fix is queued behind other work or the fix shipped but didn't actually rewrite this surface.
**Fix:** Rewrite to "Enter the assignment code your HR sent you" + accept either email or UUID server-side. Also check Intake Wizard v2 (`features/platform-v2/intake/EmployeeIntakePage.tsx`) to ensure it didn't inherit the same copy.

---

## P1 findings (next sprint)

### P1-1 — `backend/main.py` is a 12k-line monolith mounting 61 routers
**Evidence:** `grep -c include_router backend/main.py` = 61. `backend/app/main.py` only mounts 6. CLAUDE.md describes the dual-layer pattern (legacy root + modular `app/`) but the boundary is currently 6:61 — i.e., almost nothing has moved. Risk: any change to root `main.py` ripples across half the app; merge conflicts are guaranteed.
**Fix:** Migration plan to move root mounts into `app/main.py` one domain at a time. Pick auth + employee + HR first (highest churn).

### P1-2 — `policy_canonical.py` reimplements auth instead of using `auth_deps`
**File:** `backend/app/routers/policy_canonical.py:25-45`
**Why P1:** `hr_policies.py:23` already imports the shared `require_admin_or_hr` from `..auth_deps`. Two copies of an auth check means two places to forget when the rule changes. Likely a legacy artifact pre-extraction.
**Fix:** Replace local helpers with `from ..auth_deps import require_admin_or_hr`.

### P1-3 — `backend/app/routers/cases.py` is 3,328 lines
**Evidence:** Per-Explore. Same file already has W1 surface (employee-facing) and HR mutations and admin operations entangled. Service extraction overdue.
**Fix:** Extract domain by domain (case CRUD → `services/case_service.py`, employee-facing reads → separate `routers/employee_cases.py`).

### P1-4 — `supplier_registry.py` uses `SessionLocal` while peers use `db.engine`
**File:** `backend/app/services/supplier_registry.py:8`
**Why P1:** CLAUDE.md states `app/services/` should use `db.engine`. `trigger_engine.py` and `prefill_engine.py` conform; `supplier_registry.py` doesn't. Inconsistency erodes the documented contract.
**Fix:** Refactor to `db.engine` pattern OR update CLAUDE.md to acknowledge the exception with rationale.

### P1-5 — Untested services (~1,500 LOC uncovered)
- `roadmap_builder.py` (515 LOC)
- `timeline_service.py` (496 LOC)
- `supplier_registry.py` (558 LOC)
**Why P1:** Backend test count is 212, but these three services have zero direct coverage. Roadmap + timeline are user-visible; supplier registry is admin-critical. Bugs here surface in production.
**Fix:** One test file each, smoke + golden-path + one edge.

### P1-6 — OpenAI passport extraction has no retry/timeout
**File:** `backend/app/services/ocr_passport_extractor.py:316+`
**Why P1:** `await client.chat.completions.create(...)` with no `timeout=` and no retry/backoff. A transient OpenAI 429 or 5xx will fail the user's intake step with no graceful recovery.
**Fix:** Wrap in `tenacity`-style retry with exponential backoff (3 tries), explicit `timeout=30`, and surface "OCR temporarily unavailable, please retry" to the user.

### P1-7 — Direct DB execution in routers (37 routers, 294 matches)
**Evidence:** `grep -r "\.execute\|\.query" routers/ | wc -l` = 294. CLAUDE.md says new code should route through services; routers should be thin. Status today: routers do everything.
**Fix:** Pick the worst 5 (most queries) and extract into services. Repeat.

### P1-8 — 37 raw HTML form elements bypass `components/antigravity/`
**Evidence:** ~25 in admin pages (`AdminLayout`, `AdminOverviewPage`, `AdminOpsSlaPage`, etc.), 7 in `Auth.tsx`, 5 scattered across HR pages.
**Why P1:** Design-system inconsistency is the primary visible signal of "engineer-built tool" rather than "professional SaaS" (per prior W3 finding). The 37 raw `<button>`/`<input>` elements compound this.
**Fix:** Auth.tsx + admin pages first (highest volume). Migrate to `Button`/`Input`/`Card` antigravity primitives.

### P1-9 — Direct `supabase.from()` in `AdminAbTestsPage.tsx`
**File:** `frontend/src/pages/AdminAbTestsPage.tsx:81-87`
```ts
supabase.from('daily_summaries').select(...)
```
**Why P1:** CLAUDE.md is explicit — Supabase client is for auth, realtime, document queries. General data fetching goes through the FastAPI API. Bypassing this means RLS is the only safety net; if a policy is missing, data leaks.
**Fix:** Move into `adminApi.ts` wrapper.

### P1-10 — `AdminProspects.tsx:276` uses raw `fetch()` for CSV export
**Why P1:** Same as above — bypasses `adminProspectsAPI` wrapper. The wrapper exists; just call it.

---

## P2 findings (backlog)

| # | Finding | Evidence |
|---|---|---|
| P2-1 | Dead pages — `HrCaseReview.tsx`, `HrReviewDashboard.tsx` not referenced in `App.tsx` or `navigation/` | Per Explore |
| P2-2 | 20+ routers with `except Exception:` swallowing errors | `auth.py:315`, `policy_summary.py:80,187,315`, `support.py:113`, `advisors.py:195,213,317`, `hr_analytics.py:157,179,198`, `branding.py:79,98,136`, `policy_publish.py:62,284,380` |
| P2-3 | 19 `console.log/error/debug` left in production paths | `HrCaseSummary.tsx:174`, `HrDashboard.tsx:179`, `ProvidersPage.tsx:182,241`, `AdminMessages.tsx:292,394,406`, `HrAssignments.tsx:355`, `CaseWizardPage.tsx:348` |
| P2-4 | a11y: icon-only buttons without `aria-label` — `HrAssignmentReview.tsx:667`, `AdminLayout.tsx:56,61,66`, `AdminOverviewPage.tsx:150`, `HrCommandCenterCaseDetail.tsx:399`, multiple in `Auth.tsx` | (deferred to Phase 2c a11y review for full sweep) |
| P2-5 | `dossier_notifications.py:30+` requires lazy imports to avoid circular deps — coupling smell | (`# Lazy import helpers (avoid circular at module load; main_db is heavy)`) |
| P2-6 | `requirements_builder.py:14` opens `with SessionLocal()` itself instead of taking session as arg | inconsistent DI |

---

## What this pass DID NOT cover (handed to other phases)

- Live a11y sweep of top-10 pages → Phase 2c
- UX-copy review of wizard + HR command center → Phase 2c
- RLS coverage check (do all Supabase-exposed tables have policies?) → Phase 2e security
- LLM-prompt-injection threat model (assistant_router.ts, policy_extractor) → Phase 2e security
- Performance of the unmounted 6/61 split (50 routers in monolith = single-process bottleneck) → Phase 2e perf

## Open questions

1. Why is the routers/services split 6:61 rather than progressing toward inversion? Is there a decision doc?
2. Is the `backend/services/` (legacy) directory intentional or vestigial? If vestigial, when can it be deleted?
3. Why does `cases.get_case()` skip auth while every sibling enforces it? Is there a magic-link unauth read flow I'm missing?
4. AdminAbTestsPage querying Supabase directly — is the RLS on `daily_summaries` sufficient, or should this go through the API?

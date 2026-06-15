# Validate-Roadmap Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an employee self-service "Validate & start tasks" checkpoint between the roadmap and execution tasks (forms/uploads), enforced as a soft gate.

**Architecture:** A small `case_roadmap_validations` table (keyed by `canonical_case_id`) records the validation. A `POST /api/cases/{id}/roadmap/validate` endpoint (on the live `cases_write.py`) writes it. The relocation plan view response gains `roadmap_validated` (+at/by), with derived grandfathering so already-in-execution cases read as validated. The roadmap page shows a CTA; the dossier page shows a soft-gate panel and dims forms until validated. Nothing is hard-blocked.

**Tech Stack:** FastAPI / SQLAlchemy core (raw SQL via `db._exec`), Supabase Postgres + SQLite tests, React/TS (Vite), pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-06-15-roadmap-validate-gate-design.md`

**Conventions:** New public table ⇒ RLS hard-gate (enable + tenant policy mirroring `case_milestones` + revoke anon). The validate route goes on `cases_write.py` (live, dual-registered) — NOT the dead `cases.py`. Backend tests: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 <venv311>/python -m pytest <path> -v`. Frontend: `cd frontend && npx tsc --noEmit` + `npx vitest`.

---

## File Structure

| File | Responsibility | New/Modify |
|------|----------------|-----------|
| `supabase/migrations/20260628000000_case_roadmap_validations.sql` | Table + RLS + revoke anon | Create |
| `backend/db/cases.py` | `_ensure_case_roadmap_validations_table`, `upsert_roadmap_validation`, `get_roadmap_validation` | Modify |
| `backend/relocation_plan_view_schemas.py` | Add `roadmap_validated`/`_at`/`_by` to response | Modify |
| `backend/app/services/relocation_plan_view_service.py` | Resolve validation (+ grandfather) into the response | Modify |
| `backend/app/routers/cases_write.py` | `POST /{case_id}/roadmap/validate` | Modify |
| `backend/tests/test_roadmap_validation.py` | DB methods + grandfather + endpoint | Create |
| `frontend/src/types/relocationPlanView.ts` | Add fields to `RelocationPlanViewResponseDTO` | Modify |
| `frontend/src/api/cases.ts` | `validateRoadmap(caseId)` | Modify |
| `frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx` | Validate CTA + validated state | Modify |
| `frontend/src/pages/employee/EmployeeDossierPage.tsx` | Soft-gate panel + dim forms until validated | Modify |

---

## Task 1: Migration — `case_roadmap_validations`

**Files:** Create `supabase/migrations/20260628000000_case_roadmap_validations.sql`

- [ ] **Step 1: Write the migration** (mirrors the `case_milestones` RLS policy)

```sql
-- Records the employee's "validate roadmap before execution" checkpoint.
-- New public table → RLS hard-gate (enable + tenant policy + revoke anon).

CREATE TABLE IF NOT EXISTS public.case_roadmap_validations (
  canonical_case_id     text PRIMARY KEY,
  validated_at          timestamptz NOT NULL DEFAULT now(),
  validated_by_user_id  text,
  created_at            timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.case_roadmap_validations ENABLE ROW LEVEL SECURITY;

-- Employee/HR who own the case can read their validation row (mirrors
-- case_milestones_select). canonical_case_id matches ca.case_id or
-- ca.canonical_case_id, same as the milestones policy.
DROP POLICY IF EXISTS case_roadmap_validations_select ON public.case_roadmap_validations;
CREATE POLICY case_roadmap_validations_select ON public.case_roadmap_validations
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE (ca.case_id = case_roadmap_validations.canonical_case_id
             OR ca.canonical_case_id = case_roadmap_validations.canonical_case_id)
        AND (ca.employee_user_id = auth.uid()::text OR ca.hr_user_id = auth.uid()::text)
    )
  );

DROP POLICY IF EXISTS case_roadmap_validations_all ON public.case_roadmap_validations;
CREATE POLICY case_roadmap_validations_all ON public.case_roadmap_validations
  FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON public.case_roadmap_validations FROM anon;
```

- [ ] **Step 2: Lint check (no apply)**

Run: `python3 -c "import pathlib; s=pathlib.Path('supabase/migrations/20260628000000_case_roadmap_validations.sql').read_text(); assert 'ENABLE ROW LEVEL SECURITY' in s and 'REVOKE ALL' in s and 'case_roadmap_validations_select' in s; print('migration OK')"`
Expected: `migration OK`

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260628000000_case_roadmap_validations.sql
git commit -m "feat(db): case_roadmap_validations table + RLS for the validate-roadmap gate"
```

---

## Task 2: DB methods

**Files:** Modify `backend/db/cases.py` (add near the milestone methods, after `delete_service_milestones_not_in` or `delete_case_milestones`). Test: `backend/tests/test_roadmap_validation.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_roadmap_validation.py
import uuid
from sqlalchemy import create_engine, text


class FakeCasesDB:
    """Exercises the real roadmap-validation method bodies against in-memory
    SQLite. Mirrors the Database raw-SQL helpers the methods rely on."""

    def __init__(self):
        self.engine = create_engine("sqlite:///:memory:")

    # --- shims the Database methods use ---
    def coalesce_case_lookup_id(self, case_id):
        return case_id

    def _exec(self, conn, sql, params=None, op_name=None, request_id=None):
        return conn.execute(text(sql), params or {})

    # bind the real methods under test
    from backend.db.cases import CasesMixin as _M  # type: ignore
    _ensure_case_roadmap_validations_table = _M.__dict__["_ensure_case_roadmap_validations_table"]
    upsert_roadmap_validation = _M.__dict__["upsert_roadmap_validation"]
    get_roadmap_validation = _M.__dict__["get_roadmap_validation"]


def test_get_returns_none_before_validation():
    db = FakeCasesDB()
    assert db.get_roadmap_validation("case-1") is None


def test_upsert_then_get_roundtrip_and_idempotent():
    db = FakeCasesDB()
    db.upsert_roadmap_validation("case-1", "emp-9")
    row = db.get_roadmap_validation("case-1")
    assert row is not None
    assert row["canonical_case_id"] == "case-1"
    assert row["validated_by_user_id"] == "emp-9"
    assert row["validated_at"]
    # idempotent — second call updates, does not duplicate
    db.upsert_roadmap_validation("case-1", "emp-9")
    again = db.get_roadmap_validation("case-1")
    assert again["canonical_case_id"] == "case-1"
```

> NOTE: the test pulls the methods off `CasesMixin` — confirm the class name during
> Step 3 (in `backend/db/cases.py` the milestone methods live on a class; use that
> exact class name in the test's `from backend.db.cases import <Class> as _M`).

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && <venv311>/python -m pytest tests/test_roadmap_validation.py -v`
Expected: FAIL — `_ensure_case_roadmap_validations_table` (or the class import) not found.

- [ ] **Step 3: Implement the methods**

In `backend/db/cases.py`, find the class that defines `upsert_case_milestone` (search `def upsert_case_milestone`). Add these three methods to that same class, right after `delete_case_milestones` / `delete_service_milestones_not_in`:

```python
    def _ensure_case_roadmap_validations_table(self, conn: Any) -> None:
        """Idempotently ensure the table exists (prod gets it via migration;
        this keeps SQLite test DBs and fresh dev DBs working)."""
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS case_roadmap_validations ("
            "  canonical_case_id TEXT PRIMARY KEY,"
            "  validated_at TEXT NOT NULL,"
            "  validated_by_user_id TEXT,"
            "  created_at TEXT NOT NULL"
            ")"
        ))

    def upsert_roadmap_validation(
        self, case_id: str, validated_by_user_id: Optional[str],
        *, request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record (or refresh) the roadmap-validation checkpoint for a case.
        Keyed by canonical case id (same as case_milestones). Idempotent."""
        cid = self.coalesce_case_lookup_id(case_id)
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._ensure_case_roadmap_validations_table(conn)
            existing = self._exec(
                conn,
                "SELECT canonical_case_id FROM case_roadmap_validations WHERE canonical_case_id = :cid",
                {"cid": cid}, op_name="get_roadmap_validation_for_upsert", request_id=request_id,
            ).fetchone()
            if existing:
                self._exec(
                    conn,
                    "UPDATE case_roadmap_validations SET validated_at = :now, "
                    "validated_by_user_id = :uid WHERE canonical_case_id = :cid",
                    {"now": now, "uid": validated_by_user_id, "cid": cid},
                    op_name="update_roadmap_validation", request_id=request_id,
                )
            else:
                self._exec(
                    conn,
                    "INSERT INTO case_roadmap_validations "
                    "(canonical_case_id, validated_at, validated_by_user_id, created_at) "
                    "VALUES (:cid, :now, :uid, :now)",
                    {"cid": cid, "now": now, "uid": validated_by_user_id},
                    op_name="insert_roadmap_validation", request_id=request_id,
                )
        return {"canonical_case_id": cid, "validated_at": now,
                "validated_by_user_id": validated_by_user_id}

    def get_roadmap_validation(
        self, case_id: str, *, request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the validation row for a case, or None."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.begin() as conn:
            self._ensure_case_roadmap_validations_table(conn)
            row = self._exec(
                conn,
                "SELECT canonical_case_id, validated_at, validated_by_user_id, created_at "
                "FROM case_roadmap_validations WHERE canonical_case_id = :cid",
                {"cid": cid}, op_name="get_roadmap_validation", request_id=request_id,
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row) if hasattr(self, "_row_to_dict") else dict(row._mapping)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && <venv311>/python -m pytest tests/test_roadmap_validation.py -v`
Expected: PASS (3 tests). If the `CasesMixin` import name was wrong, fix the test import to the real class name and re-run.

- [ ] **Step 5: Commit**

```bash
git add backend/db/cases.py backend/tests/test_roadmap_validation.py
git commit -m "feat(db): roadmap validation upsert/get methods"
```

---

## Task 3: Plan-view response — expose validation + grandfather

**Files:** Modify `backend/relocation_plan_view_schemas.py` (`RelocationPlanViewResponse`), `backend/app/services/relocation_plan_view_service.py` (`build_relocation_plan_view_response`).

- [ ] **Step 1: Add fields to the response schema**

In `backend/relocation_plan_view_schemas.py`, inside `class RelocationPlanViewResponse`, after the `empty_state_reason` field, add:

```python
    roadmap_validated: bool = Field(
        default=False,
        description="True once the employee validated the roadmap (or grandfathered: case already in execution).",
    )
    roadmap_validated_at: Optional[datetime] = Field(
        default=None,
        description="When the roadmap was explicitly validated; null when grandfathered or not validated.",
    )
    roadmap_validated_by: Optional[str] = Field(default=None)
```

- [ ] **Step 2: Add the grandfather-aware resolver + write fields in the builder**

In `backend/app/services/relocation_plan_view_service.py`, add a module-level helper (near the other private helpers):

```python
def _resolve_roadmap_validation(db, case_id, summary):
    """(validated, validated_at, validated_by). Explicit row wins; otherwise
    grandfather a case that's already in execution (any task completed or in
    progress) so the new gate never nags active users."""
    try:
        row = db.get_roadmap_validation(case_id)
    except Exception:
        row = None
    if row:
        return True, row.get("validated_at"), row.get("validated_by_user_id")
    if (summary.completed_tasks or 0) > 0 or (summary.in_progress_tasks or 0) > 0:
        return True, None, None
    return False, None, None
```

Then in `build_relocation_plan_view_response`, locate where the `RelocationPlanViewResponse(...)` is constructed and the `summary = _build_summary(...)` line. After `summary` is computed, compute the validation triple and pass it into the response constructor:

```python
    rv_validated, rv_at, rv_by = _resolve_roadmap_validation(db, case_id, summary)
```

Add to the `RelocationPlanViewResponse(...)` constructor kwargs:

```python
        roadmap_validated=rv_validated,
        roadmap_validated_at=rv_at,
        roadmap_validated_by=rv_by,
```

(`rv_at` is an ISO string from the DB; Pydantic coerces to datetime. If a validation error surfaces, wrap with `datetime.fromisoformat(rv_at) if rv_at else None`.)

- [ ] **Step 3: Add a service test**

Append to `backend/tests/test_roadmap_validation.py`:

```python
class _Summary:
    def __init__(self, completed=0, in_progress=0):
        self.completed_tasks = completed
        self.in_progress_tasks = in_progress


def test_resolver_explicit_validation_wins():
    from backend.app.services.relocation_plan_view_service import _resolve_roadmap_validation

    class DB:
        def get_roadmap_validation(self, cid):
            return {"validated_at": "2026-06-15T00:00:00", "validated_by_user_id": "emp"}
    v, at, by = _resolve_roadmap_validation(DB(), "c", _Summary())
    assert v is True and at == "2026-06-15T00:00:00" and by == "emp"


def test_resolver_grandfathers_in_execution_case():
    from backend.app.services.relocation_plan_view_service import _resolve_roadmap_validation

    class DB:
        def get_roadmap_validation(self, cid):
            return None
    v, at, by = _resolve_roadmap_validation(DB(), "c", _Summary(in_progress=2))
    assert v is True and at is None


def test_resolver_unvalidated_fresh_case():
    from backend.app.services.relocation_plan_view_service import _resolve_roadmap_validation

    class DB:
        def get_roadmap_validation(self, cid):
            return None
    v, at, by = _resolve_roadmap_validation(DB(), "c", _Summary())
    assert v is False and at is None
```

- [ ] **Step 4: Run tests**

Run: `cd backend && <venv311>/python -m pytest tests/test_roadmap_validation.py -v`
Expected: PASS (6 tests). Also run the plan-view suite for no regression:
`cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 <venv311>/python -m pytest tests/ -k "relocation_plan or plan_view" -q` (run matching files directly if `-k` hits pre-existing broken collectors).

- [ ] **Step 5: Commit**

```bash
git add backend/relocation_plan_view_schemas.py backend/app/services/relocation_plan_view_service.py backend/tests/test_roadmap_validation.py
git commit -m "feat(roadmap): expose roadmap_validated (+grandfather) on the plan view"
```

---

## Task 4: Validate endpoint

**Files:** Modify `backend/app/routers/cases_write.py` (add after the `start_research` POST, ~line 165+).

- [ ] **Step 1: Add the endpoint**

```python
@router.post("/{case_id}/roadmap/validate")
def validate_roadmap(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Employee validates their roadmap (the 'start tasks' checkpoint). Idempotent."""
    _assert_case_access(user, case_id)
    result = main_db.upsert_roadmap_validation(case_id, str(user.get("id") or ""))
    # Invalidate the cached plan view so the validated state shows immediately.
    try:
        invalidate_relocation_plan_cache(case_id)
    except Exception:
        pass
    return {
        "roadmap_validated": True,
        "roadmap_validated_at": result["validated_at"],
        "roadmap_validated_by": result["validated_by_user_id"],
    }
```

(`_assert_case_access`, `main_db`, and `invalidate_relocation_plan_cache` are already imported in `cases_write.py` — confirm and reuse.)

- [ ] **Step 2: Verify the route is registered on the prod app**

Run: `cd .. && <venv311>/python -c "from backend.main import app; print([r.path for r in app.routes if 'roadmap/validate' in r.path])"`
Expected: `['/api/cases/{case_id}/roadmap/validate']` (non-empty — confirms it serves in prod; `cases_write` is already registered in both `backend/main.py` and `backend/app/main.py`).

- [ ] **Step 3: Add an endpoint test** (app-mounted harness, override auth per `reference_app_mounted_test_harness`)

```python
def test_validate_endpoint_is_idempotent_and_sets_state(monkeypatch):
    import os
    os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"
    from fastapi.testclient import TestClient
    from backend.main import app
    import backend.app.auth_deps as auth_deps
    from backend.app.services import case_service
    from backend.database import db as main_db

    fake_user = {"id": "emp-1"}
    app.dependency_overrides[auth_deps.get_current_user] = lambda: fake_user
    monkeypatch.setattr(case_service, "_assert_case_access", lambda user, case_id: None)

    captured = {}
    monkeypatch.setattr(main_db, "upsert_roadmap_validation",
                        lambda cid, uid, **k: captured.update(cid=cid, uid=uid)
                        or {"validated_at": "2026-06-15T00:00:00", "validated_by_user_id": uid})
    try:
        c = TestClient(app)
        r = c.post("/api/cases/abc/roadmap/validate")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["roadmap_validated"] is True
        assert captured["cid"] == "abc" and captured["uid"] == "emp-1"
    finally:
        app.dependency_overrides.clear()
```

> If `_assert_case_access` is imported into `cases_write` by value (`from ..services.case_service import _assert_case_access`), monkeypatching `case_service._assert_case_access` won't affect the router's bound reference — instead patch `backend.app.routers.cases_write._assert_case_access`. Use that target if the first run still hits a real access check.

- [ ] **Step 4: Run the endpoint test**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 <venv311>/python -m pytest tests/test_roadmap_validation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/cases_write.py backend/tests/test_roadmap_validation.py
git commit -m "feat(roadmap): POST /api/cases/{id}/roadmap/validate endpoint"
```

---

## Task 5: Frontend types + API method

**Files:** Modify `frontend/src/types/relocationPlanView.ts` (`RelocationPlanViewResponseDTO`), `frontend/src/api/cases.ts`.

- [ ] **Step 1: Add fields to the DTO**

In `frontend/src/types/relocationPlanView.ts`, find `interface RelocationPlanViewResponseDTO` and add:

```typescript
  roadmap_validated: boolean;
  roadmap_validated_at?: string | null;
  roadmap_validated_by?: string | null;
```

(If the interface omits `roadmap_validated` as required would break older mocks, make it optional: `roadmap_validated?: boolean;` — check existing test fixtures and match.)

- [ ] **Step 2: Add the API method** (mirror `patchCase` in `frontend/src/api/cases.ts`)

```typescript
export async function validateRoadmap(caseId: string): Promise<{
  roadmap_validated: boolean;
  roadmap_validated_at?: string | null;
  roadmap_validated_by?: string | null;
}> {
  const { data } = await api.post(`/api/cases/${caseId}/roadmap/validate`);
  return data;
}
```

(Use the same `api`/axios import `patchCase` uses in this file — confirm the import line and reuse it.)

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/relocationPlanView.ts frontend/src/api/cases.ts
git commit -m "feat(roadmap): FE types + validateRoadmap api method"
```

---

## Task 6: Roadmap page CTA

**Files:** Modify `frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx`.

- [ ] **Step 1: Read the component** to find where the plan view data (`RelocationPlanViewResponseDTO`) is held in state and where the roadmap body renders (after the phases/steps). Identify the state variable name (e.g. `plan`/`data`) and `caseId`.

- [ ] **Step 2: Add validate state + handler + CTA**

Near the component's other hooks:

```tsx
import { validateRoadmap } from '../../api/cases';
// ...
const [validating, setValidating] = useState(false);
const [validatedAtLocal, setValidatedAtLocal] = useState<string | null>(null);
const isValidated = !!(plan?.roadmap_validated || validatedAtLocal);

const handleValidate = async () => {
  if (!caseId || validating) return;
  setValidating(true);
  try {
    const res = await validateRoadmap(caseId);
    setValidatedAtLocal(res.roadmap_validated_at ?? new Date().toISOString());
  } finally {
    setValidating(false);
  }
};
```

After the roadmap steps/phases render, add (use antigravity `Button`/`Card`, navy/teal per DESIGN.md):

```tsx
{!isValidated ? (
  <div className="mt-6 rounded-xl border border-[#e2e8f0] bg-white p-5 text-center">
    <div className="text-sm font-semibold text-[#0b2b43]">Happy with your plan?</div>
    <div className="text-xs text-[#64748b] mt-1 mb-3">
      Validate your roadmap to start working through your tasks — forms and documents.
    </div>
    <Button onClick={handleValidate} disabled={validating}>
      {validating ? 'Validating…' : '✓ Validate & start tasks'}
    </Button>
  </div>
) : (
  <div className="mt-6 flex items-center gap-2 text-xs text-[#1f8e8b]">
    ✓ <span>Roadmap validated{validatedAtLocal || plan?.roadmap_validated_at
        ? ` on ${new Date((validatedAtLocal || plan?.roadmap_validated_at) as string).toLocaleDateString()}`
        : ''}. Your tasks are unlocked.</span>
  </div>
)}
```

(Match the file's existing `Button` import; if it imports from `../../components/antigravity`, reuse that. Replace `plan` with the real state var name.)

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx
git commit -m "feat(roadmap): validate CTA on the employee roadmap page"
```

---

## Task 7: Dossier soft gate

**Files:** Modify `frontend/src/pages/employee/EmployeeDossierPage.tsx`.

- [ ] **Step 1: Fetch the validation flag** (the page currently loads forms via `dossierAPI.list`). Add a plan-view fetch for the flag.

Near the existing imports/hooks:

```tsx
import { fetchRelocationPlanView } from '../../api/relocationPlanView';
// ...
const [roadmapValidated, setRoadmapValidated] = useState<boolean>(true); // optimistic: don't flash the gate
useEffect(() => {
  if (!caseId) return;
  let cancelled = false;
  fetchRelocationPlanView(caseId, { role: 'employee' })
    .then((p) => { if (!cancelled) setRoadmapValidated(!!p.roadmap_validated); })
    .catch(() => { if (!cancelled) setRoadmapValidated(true); }); // fail-open (soft gate)
  return () => { cancelled = true; };
}, [caseId]);
```

- [ ] **Step 2: Add the soft-gate panel + dim the forms section**

Find the JSX region where the forms list renders (the page header is around the "Every official form…" copy, ~line 150; the list/empty-state ~line 277). Immediately before the forms list block, add:

```tsx
{!roadmapValidated && (
  <div className="mb-4 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4 flex items-start gap-3"
       data-testid="validate-roadmap-gate">
    <span className="text-lg">🗺️</span>
    <div className="flex-1">
      <div className="text-sm font-semibold text-[#0b2b43]">Validate your roadmap to start</div>
      <div className="text-xs text-[#64748b] mt-0.5">
        Review your roadmap and click “Validate &amp; start tasks”. Your forms and uploads are below — they’ll be the focus once you’ve validated.
      </div>
      <Link to={`/employee/case/${caseId}/roadmap`}
            className="inline-block mt-2 text-xs font-semibold text-[#1f8e8b]">
        Go to my roadmap →
      </Link>
    </div>
  </div>
)}
<div className={roadmapValidated ? '' : 'opacity-60'}>
  {/* existing forms list / empty-state JSX moves inside this wrapper */}
</div>
```

Wrap the existing forms list JSX in the `<div className={roadmapValidated ? '' : 'opacity-60'}>` (soft dim — forms remain clickable). Ensure `Link` is imported from `react-router-dom` (it likely already is).

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Add a vitest for the gate** `frontend/src/pages/employee/__tests__/EmployeeDossierGate.test.tsx` — render with a mocked `fetchRelocationPlanView` returning `roadmap_validated: false` and assert `getByTestId('validate-roadmap-gate')` appears; returning `true` and assert it's absent. (Mirror an existing employee-page test's mocking setup; mock `../../api/relocationPlanView` and `../../api/dossier`/`dossierAPI`.)

- [ ] **Step 5: Run vitest + tsc**

Run: `cd frontend && npx vitest run src/pages/employee/__tests__/EmployeeDossierGate.test.tsx` then `npx tsc --noEmit`
Expected: PASS / no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/employee/EmployeeDossierPage.tsx frontend/src/pages/employee/__tests__/EmployeeDossierGate.test.tsx
git commit -m "feat(roadmap): dossier soft-gate until roadmap validated"
```

---

## Task 8: Full verification + push + PR

- [ ] **Step 1:** Backend: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 <venv311>/python -m pytest tests/test_roadmap_validation.py -v` → all PASS.
- [ ] **Step 2:** Backend regression: run the relocation-plan/milestone test files directly → PASS.
- [ ] **Step 3:** Frontend: `cd frontend && npx tsc --noEmit && npx vitest run src/pages/employee` → clean / PASS.
- [ ] **Step 4:** Build gate: `cd frontend && npm run build` → OK.
- [ ] **Step 5:** Confirm only one migration file changed vs `origin/main` and the timestamp doesn't collide: `git ls-tree -r --name-only origin/main supabase/migrations/ | grep 20260628000000 || echo free`.
- [ ] **Step 6:** Push: `git push -u origin feat/roadmap-validate-gate`.
- [ ] **Step 7:** PR via REST: `gh api -X POST repos/rlecomte1929/rolec/pulls -f title="feat(roadmap): validate-roadmap gate before execution tasks" -f head="feat/roadmap-validate-gate" -f base="main" -f body="$(cat docs/superpowers/specs/2026-06-15-roadmap-validate-gate-design.md)"`. Do NOT merge.

---

## Self-review (coverage vs spec)

- Table + RLS + revoke anon → Task 1. ✅
- Employee self-validate endpoint (idempotent, ownership) → Task 4. ✅
- Soft gate (no 403; dossier dim + CTA) → Tasks 6/7. ✅
- State on plan view + grandfathering (derived, no backfill) → Tasks 2/3. ✅
- Sticky / per-canonical-case → Task 2 (keyed by canonical_case_id; upsert refresh). ✅
- Not reviving readiness; no status-enum change → nothing touches those. ✅
- Verification (DB, resolver, endpoint, FE gate, build, migration) → Tasks 2/3/4/7/8. ✅

**Type consistency:** `upsert_roadmap_validation(case_id, validated_by_user_id)` / `get_roadmap_validation(case_id)` defined in Task 2, called in Task 4 + Task 3's resolver. Response fields `roadmap_validated`/`roadmap_validated_at`/`roadmap_validated_by` added in Task 3 (backend) and Task 5 (FE DTO), consumed in Tasks 6/7. `validateRoadmap(caseId)` defined Task 5, used Task 6. Consistent.

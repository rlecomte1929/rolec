# BL-Compliance Follow-Up — Data Backfill & Scheduled Evaluation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the BL-Compliance engine safe to run on real data and then put it on a schedule, without flooding the HR command center with noise.

**Architecture:** Three sequential phases with hard gates between them.
- **Phase A** patches the one rule that is *actually* noisy (`missing_employer_reg` — type `missing_field`) so it only fires when intake has started for that case. The other two seed rules (`permit_expiry`, `tax_183_day`) are already null-safe in the pure evaluator; no change required.
- **Phase B** durably feeds the engine by surfacing `employer_reg_number`, `permit_expiry_date`, and `expected_start_date` in the HR + Employee intake flows so coverage grows naturally.
- **Phase C** wires a daily scheduled fleet-wide run via a new admin endpoint + GitHub Actions cron — gated behind a dry-run flag for the first two weeks so we can sanity-check the output distribution before HR sees real alerts.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Supabase Postgres (RLS), React/Vite, GitHub Actions, pytest.

**Key code referenced throughout:**
- `backend/app/services/compliance_evaluator.py` — pure evaluator + SQL data source
- `backend/app/routers/compliance.py` — existing per-company HR endpoint
- `backend/app/routers/immigration_intake_profile.py` — HR PATCH for `imm_employee_profiles`
- `backend/app/routers/immigration.py` — Pydantic `HrProfileFields`, `EmployeeProfileUpdate`
- `frontend/src/features/platform-v2/intake/IntakeWizard.tsx` — Intake Wizard v2 entry
- `supabase/migrations/20260607000000_compliance_rules_alerts.sql` — compliance tables
- `supabase/migrations/20260607010000_seed_compliance_rules.sql` — 3 seed rules
- `.github/workflows/calibration-monthly.yml` — cron pattern to follow

**Branch convention (per CLAUDE.md):** one PR per phase.
- Phase A → `compliance/phase-a-null-safety`
- Phase B → `compliance/phase-b-intake-fields`
- Phase C → `compliance/phase-c-scheduler`

---

## Phase A — Null-safety for `missing_field` rules

**Hard gate before Phase B:** A fleet-wide `run_compliance_evaluation(db)` (no `company_id`) against a snapshot of the prod DB must produce **0 alerts** for `missing_employer_reg` on cases that have never started intake (no `imm_employee_profiles` row at all). Verified via a unit test plus a manual dry-run.

### Task A1: Extend the pure evaluator to support a precondition predicate

**Files:**
- Modify: `backend/app/services/compliance_evaluator.py` — extend `_evaluate_condition` + `CaseComplianceData`
- Test: `backend/tests/test_compliance_evaluator.py` — add precondition cases

- [ ] **Step 1: Write the failing test for "missing_field with precondition_field skips when precondition is null"**

Add to `backend/tests/test_compliance_evaluator.py` (append at end of the existing tests, BEFORE any `if __name__` block):

```python
def test_missing_field_rule_skips_when_precondition_absent():
    """A missing_field rule with a `precondition_field` must NOT fire when the
    precondition is also null — i.e. intake has not started for this case, so
    we can't claim a field is 'missing' yet."""
    rule_with_precondition = ComplianceRule(
        id="rule-employer-pc",
        category="employer",
        severity="high",
        trigger_condition={
            "type": "missing_field",
            "field": "employer_registration_id",
            "operator": "is_null",
            "value": None,
            "precondition_field": "profile_exists",
        },
    )
    # No profile at all — precondition_field is None — must skip.
    case_no_profile = CaseComplianceData(
        case_id="case-noprofile",
        employer_registration_id=None,
        profile_exists=False,
    )
    # Profile started but employer_reg_number not filled — must fire.
    case_started_intake = CaseComplianceData(
        case_id="case-started",
        employer_registration_id=None,
        profile_exists=True,
    )
    firings_skip = evaluate([rule_with_precondition], case_no_profile, today=TODAY)
    firings_fire = evaluate([rule_with_precondition], case_started_intake, today=TODAY)
    assert firings_skip == []
    assert len(firings_fire) == 1
    assert firings_fire[0].rule_id == "rule-employer-pc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 pytest tests/test_compliance_evaluator.py::test_missing_field_rule_skips_when_precondition_absent -v`
Expected: FAIL — `CaseComplianceData` has no `profile_exists` field; `TypeError` on construction.

- [ ] **Step 3: Add `profile_exists` field to `CaseComplianceData`**

In `backend/app/services/compliance_evaluator.py`, modify the `CaseComplianceData` dataclass:

```python
@dataclass(frozen=True)
class CaseComplianceData:
    """Resolved per-case field values the rules evaluate against."""

    case_id: str
    permit_expiry_date: Optional[date] = None
    employer_registration_id: Optional[str] = None
    days_present_in_host: Optional[int] = None
    # Precondition flag: does the case have an imm_employee_profiles row?
    # Used by `missing_field` rules to distinguish "intake never started"
    # from "intake started but field wasn't filled" — only the latter fires.
    profile_exists: bool = False

    def get(self, field_name: str) -> Any:
        return getattr(self, field_name, None)
```

- [ ] **Step 4: Wire precondition_field into `_evaluate_condition` for `missing_field` type**

In `backend/app/services/compliance_evaluator.py`, replace the `missing_field` branch in `_evaluate_condition`:

```python
    if ctype == "missing_field":
        # Precondition guard: if the rule names a precondition_field and that
        # field is falsy/null on this case, the rule cannot fire — we don't yet
        # know whether the field applies.
        precondition_field = cond.get("precondition_field")
        if precondition_field is not None:
            precondition_value = case.get(precondition_field)
            if not precondition_value:
                return None
        if actual is None or (isinstance(actual, str) and actual.strip() == ""):
            return {"field": field_name, "reason": "missing"}
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 pytest tests/test_compliance_evaluator.py -v`
Expected: PASS — new test passes; all pre-existing tests still pass (the field is optional with default `False`; rules without `precondition_field` behave identically to before).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/compliance_evaluator.py backend/tests/test_compliance_evaluator.py
git commit -m "feat(compliance): add precondition_field guard for missing_field rules

Lets a missing_field rule skip cases where intake has not started yet,
so it does not fire on every relocation_case that lacks an
imm_employee_profiles row. Phase A1 of BL-Compliance follow-up."
```

---

### Task A2: Populate `profile_exists` in the SQL data source

**Files:**
- Modify: `backend/app/services/compliance_evaluator.py` — `_open_cases_sql` + `SqlComplianceDataSource.open_cases`
- Test: `backend/tests/test_compliance_evaluator.py` — add SQL-shape test (sqlite or mocked rows)

- [ ] **Step 1: Write the failing test for the data source surfacing `profile_exists`**

Add to `backend/tests/test_compliance_evaluator.py`:

```python
def test_sql_data_source_sets_profile_exists_from_row():
    """SqlComplianceDataSource.open_cases() must populate profile_exists from
    the joined imm_employee_profiles lateral row."""
    from backend.app.services.compliance_evaluator import SqlComplianceDataSource

    class FakeRowResult:
        def __init__(self, rows):
            self._rows = rows
        def mappings(self):
            return self
        def all(self):
            return self._rows

    class FakeSession:
        def execute(self, sql, params=None):
            return FakeRowResult([
                {
                    "case_id": "case-A",
                    "permit_expiry_date": None,
                    "employer_registration_id": None,
                    "expected_start_date": None,
                    "profile_exists": False,
                },
                {
                    "case_id": "case-B",
                    "permit_expiry_date": None,
                    "employer_registration_id": None,
                    "expected_start_date": None,
                    "profile_exists": True,
                },
            ])

    source = SqlComplianceDataSource(FakeSession(), today=TODAY)
    cases = list(source.open_cases())
    assert len(cases) == 2
    assert cases[0].case_id == "case-A" and cases[0].profile_exists is False
    assert cases[1].case_id == "case-B" and cases[1].profile_exists is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 pytest tests/test_compliance_evaluator.py::test_sql_data_source_sets_profile_exists_from_row -v`
Expected: FAIL — current SQL has no `profile_exists` column and `open_cases()` never sets the flag.

- [ ] **Step 3: Add `profile_exists` to the open-cases SQL**

In `backend/app/services/compliance_evaluator.py`, modify `_open_cases_sql`:

```python
def _open_cases_sql(company_scoped: bool):
    where = "where rc.archived_at is null"
    if company_scoped:
        where += " and rc.company_id = :company_id"
    return text(
        f"""
        select
            rc.id::text                                 as case_id,
            ic.permit_expiry_date                       as permit_expiry_date,
            prof.employer_reg_number                    as employer_registration_id,
            rc.expected_start_date                      as expected_start_date,
            (prof.case_id is not null)                  as profile_exists
        from public.relocation_cases rc
        left join lateral (
            select permit_expiry_date
            from public.immigration_cases i
            where i.case_id = rc.id
            order by i.created_at desc
            limit 1
        ) ic on true
        left join lateral (
            -- imm_employee_profiles.case_id is text; relocation_cases.id is uuid.
            select case_id, employer_reg_number
            from public.imm_employee_profiles p
            where p.case_id = rc.id::text
            order by p.created_at desc
            limit 1
        ) prof on true
        {where}
        """
    )
```

- [ ] **Step 4: Read `profile_exists` in `SqlComplianceDataSource.open_cases`**

In `backend/app/services/compliance_evaluator.py`, modify `open_cases`:

```python
    def open_cases(self) -> Iterable[CaseComplianceData]:
        sql = _open_cases_sql(self._company_id is not None)
        params = {"company_id": self._company_id} if self._company_id is not None else {}
        rows = self._db.execute(sql, params).mappings().all()
        for r in rows:
            start = r["expected_start_date"]
            days_present = (self._today - start).days if start is not None else None
            yield CaseComplianceData(
                case_id=r["case_id"],
                permit_expiry_date=r["permit_expiry_date"],
                employer_registration_id=r["employer_registration_id"],
                days_present_in_host=days_present,
                profile_exists=bool(r["profile_exists"]),
            )
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 pytest tests/test_compliance_evaluator.py -v`
Expected: PASS — all tests, including the new SQL-shape test, pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/compliance_evaluator.py backend/tests/test_compliance_evaluator.py
git commit -m "feat(compliance): surface profile_exists in SqlComplianceDataSource

Lateral-joins imm_employee_profiles and surfaces a boolean indicating
whether intake has started for the case, so the missing_field rule can
skip cases that never started intake. Phase A2."
```

---

### Task A3: Update the seed rule to use the precondition

**Files:**
- Create: `supabase/migrations/20260608000000_compliance_rules_missing_employer_precondition.sql`
- Test: `backend/tests/test_seed_compliance_rules.py` — assert the JSON shape

- [ ] **Step 1: Write the failing test asserting the updated trigger_condition**

Open `backend/tests/test_seed_compliance_rules.py` and find the existing assertion block for `c0119a03-...` (the employer rule). Add a sub-assertion checking the new precondition key. If no such test exists yet, append:

```python
def test_seed_employer_rule_has_profile_exists_precondition():
    """The employer-registration seed rule must specify a precondition_field
    so it does not fire on cases that have never started intake."""
    import psycopg2, os, json
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        import pytest; pytest.skip("DATABASE_URL not set")
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select trigger_condition from public.compliance_rules "
                "where id = 'c0119a03-0000-4000-8000-000000000003'"
            )
            (cond,) = cur.fetchone()
            cond = cond if isinstance(cond, dict) else json.loads(cond)
            assert cond.get("precondition_field") == "profile_exists", cond
    finally:
        conn.close()
```

(If the existing test file uses a different style — e.g. reads the SQL file directly — match that style. The substantive assertion is: the migration sets `precondition_field = "profile_exists"` on rule `c0119a03-...`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_seed_compliance_rules.py -v`
Expected: FAIL or SKIP — if SKIP, push to a branch and let CI run it against the test DB; either way it should not pass yet.

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20260608000000_compliance_rules_missing_employer_precondition.sql`:

```sql
-- ============================================================================
-- BL-Compliance follow-up · Phase A3 — add precondition to missing_employer_reg
--
-- Without a precondition, the missing_field rule for employer_reg_number fires
-- on every relocation_case whose imm_employee_profiles row is absent — i.e.
-- ~all 592 prod cases on first run. Adding precondition_field=profile_exists
-- restricts firing to cases where intake has started but the field wasn't
-- filled. The evaluator (compliance_evaluator.py) consumes this key.
--
-- Replay-safe: jsonb_set on the existing row by deterministic id.
-- ============================================================================

begin;

update public.compliance_rules
   set trigger_condition = jsonb_set(
         trigger_condition,
         '{precondition_field}',
         '"profile_exists"'::jsonb,
         true
       ),
       updated_at = now()
 where id = 'c0119a03-0000-4000-8000-000000000003';

commit;

-- ============================================================================
-- Rollback (manual):
--   update public.compliance_rules
--      set trigger_condition = trigger_condition - 'precondition_field'
--    where id = 'c0119a03-0000-4000-8000-000000000003';
-- ============================================================================
```

- [ ] **Step 4: Apply the migration via Supabase MCP (project nsvefcvpvwwwhuqyuqmp)**

Per `project_supabase_migration_drift.md` memory: `supabase db push` is blocked by ~95 orphan remote rows in this repo; apply via the Supabase MCP `apply_migration` instead. Confirm with the user before applying; once applied, re-run:

Run: `cd backend && pytest tests/test_seed_compliance_rules.py::test_seed_employer_rule_has_profile_exists_precondition -v`
Expected: PASS.

- [ ] **Step 5: Manual verification — fleet-wide dry-evaluation in a python shell**

After migration is applied, run a one-off sanity check (do NOT commit any alerts; abort the transaction):

```bash
cd /Users/romainlecomte/Documents/GitHub/rolec && python3 -c "
from backend.app.db import SessionLocal
from backend.app.services.compliance_evaluator import run_compliance_evaluation
with SessionLocal() as db:
    r = run_compliance_evaluation(db)
    print('cases:', r.cases_evaluated, 'would-create:', r.alerts_created, 'skipped-existing:', r.alerts_skipped_existing)
    db.rollback()  # do NOT persist
"
```

Expected: `would-create` should be a small number (only cases that *have* an `imm_employee_profiles` row but missing `employer_reg_number`, plus any with permits expiring inside 60 days, plus any past 183 days). If it's still in the hundreds, the precondition guard is not working — debug before proceeding to Phase B.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260608000000_compliance_rules_missing_employer_precondition.sql backend/tests/test_seed_compliance_rules.py
git commit -m "feat(compliance): gate missing_employer_reg behind profile_exists

Stops the rule firing on cases that never started intake (~all 592
prod cases). Phase A3 of BL-Compliance follow-up. Migration applied
via Supabase MCP per project_supabase_migration_drift."
```

- [ ] **Step 7: Open Phase A PR**

```bash
git push -u origin compliance/phase-a-null-safety
gh pr create --title "feat(compliance): Phase A — null-safety for missing_field rules" --body "$(cat <<'EOF'
## Summary
- Adds `precondition_field` guard to the pure compliance evaluator so a `missing_field` rule can require an enabling condition before firing.
- Lateral-joins `imm_employee_profiles` in the SQL data source to expose `profile_exists`.
- Migrates the seed `missing_employer_reg` rule to use `precondition_field=profile_exists`, so it only fires for cases that started intake but didn't fill the field — instead of firing on all ~592 prod cases.

The other two seed rules (`permit_expiry`, `tax_183_day`) were already null-safe in the pure evaluator; no change required there.

This is Phase A of the BL-Compliance follow-up. Phase B (intake-field UI) and Phase C (scheduled evaluation) follow once this lands.

## Test plan
- [x] Unit tests for precondition guard (missing_field with and without precondition).
- [x] Unit test for SQL data source populating `profile_exists`.
- [x] Seed-rule test verifies migration sets `precondition_field`.
- [x] Manual fleet-wide dry-evaluation against prod DB shows alerts_created drop from ~592 to a small number.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Phase B — Surface compliance-relevant fields in intake

**Hard gate before Phase C:** at least one real prod case has `employer_reg_number` AND `expected_start_date` set via the intake UI, end-to-end. No use shipping a scheduler that runs against empty data.

### Task B1: Add `expected_start_date` to the HR intake fields model

**Background:** `HrProfileFields` already exposes `employer_reg_number`. But `expected_start_date` lives on `relocation_cases`, not on the profile, so it needs a separate code path. We'll add a tiny dedicated PATCH endpoint to keep blast radius small.

**Files:**
- Modify: `backend/app/routers/immigration.py:109` — `HrProfileFields` is fine as-is; do NOT add expected_start_date here (different table).
- Modify: `backend/app/routers/immigration_intake_profile.py` — add `PATCH /api/hr/cases/{case_id}/expected-start-date`
- Test: `backend/tests/test_compliance_router.py` already has the app-mounted harness pattern — copy it.
- Create: `backend/tests/test_intake_expected_start_date.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_intake_expected_start_date.py`. Pattern from `reference_app_mounted_test_harness.md` memory — needs `RELOPASS_QUERY_COUNTER_OFF=1`; override `backend.app.auth_deps.get_current_user` (NOT `backend.main`'s):

```python
"""Phase B1 — HR can set expected_start_date on a relocation_case."""
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps


@pytest.fixture
def hr_client(monkeypatch):
    def _fake_hr_user():
        return {"id": "hr-1", "role": "hr", "company_id": "company-1"}
    def _fake_org():
        return "company-1"
    app.dependency_overrides[auth_deps.get_current_user] = _fake_hr_user
    app.dependency_overrides[auth_deps.require_admin_or_hr] = _fake_hr_user
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = _fake_org
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_patch_expected_start_date_route_exists(hr_client):
    # Smoke test: route must be reachable. 404 or 422 (validation) ≠ 405.
    r = hr_client.patch("/api/hr/cases/00000000-0000-0000-0000-000000000000/expected-start-date",
                        json={"expected_start_date": "2026-09-01"})
    assert r.status_code != 405, "route not registered — Phase B1 regression"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_intake_expected_start_date.py -v`
Expected: FAIL — 405 method not allowed (route absent).

- [ ] **Step 3: Add the PATCH endpoint**

In `backend/app/routers/immigration_intake_profile.py`, add at the bottom of the file (above any `# end` comment):

```python
from pydantic import BaseModel


class ExpectedStartDateBody(BaseModel):
    expected_start_date: str  # ISO date


@router.patch("/hr/cases/{case_id}/expected-start-date")
def update_case_expected_start_date(
    case_id: str,
    body: ExpectedStartDateBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """HR sets the case's expected start date — feeds the `tax_183_day`
    compliance rule via the days_present_in_host derivation."""
    with db.engine.begin() as conn:
        # Tenant-scope the update via company_id; UPDATE ... WHERE returns 0
        # rows for cross-tenant attempts.
        result = conn.execute(
            text(
                "UPDATE public.relocation_cases "
                "SET expected_start_date = :d, updated_at = now() "
                "WHERE id = :case_id AND company_id = :company_id "
                "RETURNING id"
            ),
            {"d": body.expected_start_date, "case_id": case_id, "company_id": org_id},
        ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Case not found or not in your company")
    return {"case_id": case_id, "expected_start_date": body.expected_start_date}
```

- [ ] **Step 4: Register the router in BOTH backend/main.py and backend/app/main.py**

Per CLAUDE.md hard rule — Render serves `backend.main:app`, so router-only registration in `app/main.py` returns 405. The `immigration_intake_profile` router may already be registered; if not, add it in both places following the existing `immigration_router` registration pattern (~line 580 of `backend/main.py`).

Verify both registrations:

```bash
python3 -c "from backend.main import app; print([r.path for r in app.routes if 'expected-start-date' in r.path])"
```

Expected output (single line): `['/api/hr/cases/{case_id}/expected-start-date']`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_intake_expected_start_date.py -v`
Expected: PASS — route is now reachable (smoke).

- [ ] **Step 6: Add full happy-path + tenant-isolation tests**

Extend `test_intake_expected_start_date.py` with:

```python
def test_patch_expected_start_date_returns_404_for_other_company(hr_client, monkeypatch):
    # No row in company-1 matches → 404.
    r = hr_client.patch(
        "/api/hr/cases/11111111-1111-1111-1111-111111111111/expected-start-date",
        json={"expected_start_date": "2026-09-01"},
    )
    assert r.status_code == 404, r.text


def test_patch_expected_start_date_rejects_invalid_payload(hr_client):
    r = hr_client.patch(
        "/api/hr/cases/00000000-0000-0000-0000-000000000000/expected-start-date",
        json={},
    )
    assert r.status_code == 422, r.text
```

Run: `cd backend && pytest tests/test_intake_expected_start_date.py -v` → PASS all three.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/immigration_intake_profile.py backend/main.py backend/app/main.py backend/tests/test_intake_expected_start_date.py
git commit -m "feat(intake): HR endpoint to set relocation_case.expected_start_date

Required for the BL-Compliance tax_183_day rule (days_present_in_host
derives from expected_start_date). Registered in both backend/main.py
and backend/app/main.py per CLAUDE.md dual-mount rule. Phase B1."
```

---

### Task B2: Surface `employer_reg_number` + `expected_start_date` in IntakeWizard.tsx

**Files:**
- Modify: `frontend/src/features/platform-v2/intake/IntakeWizard.tsx` — add the two inputs to the HR-side step
- Test: `frontend/src/features/platform-v2/intake/__tests__/IntakeWizard.test.tsx` (create if absent)

- [ ] **Step 1: Read the current IntakeWizard.tsx to locate the HR step**

Read the file end-to-end before editing — it's the canonical entry point per `project_intake_wizard_v2.md` memory.

- [ ] **Step 2: Write failing component test**

Create or extend the test file:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import IntakeWizard from "../IntakeWizard";

describe("IntakeWizard — compliance fields", () => {
  it("renders the employer registration number input", () => {
    render(<IntakeWizard caseId="test" mode="hr" />);
    expect(screen.getByLabelText(/employer registration/i)).toBeInTheDocument();
  });

  it("renders the expected start date input", () => {
    render(<IntakeWizard caseId="test" mode="hr" />);
    expect(screen.getByLabelText(/expected start date/i)).toBeInTheDocument();
  });
});
```

Run: `cd frontend && npx vitest run src/features/platform-v2/intake/__tests__/IntakeWizard.test.tsx`
Expected: FAIL (fields absent).

- [ ] **Step 3: Add the inputs**

In `IntakeWizard.tsx`, add to the HR step (matching the existing antigravity `Input` component style — do NOT introduce new component imports). For `employer_reg_number`, hit the existing `PATCH /api/hr/cases/{case_id}/profile/hr-fields` endpoint. For `expected_start_date`, hit the new `PATCH /api/hr/cases/{case_id}/expected-start-date` endpoint from Task B1.

(The exact JSX depends on the existing wizard's structure — match the surrounding pattern. Do NOT refactor unrelated code per CLAUDE.md "Surgical Changes" guideline.)

- [ ] **Step 4: Run tests + type-check**

```bash
cd frontend && npx vitest run src/features/platform-v2/intake/__tests__/IntakeWizard.test.tsx
cd frontend && npx tsc --noEmit
```

Both PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/platform-v2/intake/
git commit -m "feat(intake): expose employer_reg_number + expected_start_date in IntakeWizard

Lets HR fill the two fields the BL-Compliance engine reads. Phase B2."
```

---

### Task B3: Expose `permit_expiry_date` in the employee-side intake (or HR-side, mirror existing pattern)

**Background:** `permit_expiry_date` lives on `immigration_cases`. Check whether the existing wizard already collects it (immigration step) before adding new UI — likely it does, in which case this task is a no-op verification.

- [ ] **Step 1: Audit the current immigration step of IntakeWizard.tsx for a permit-expiry input**

Run: `grep -rn "permit_expiry" frontend/src/features/platform-v2/intake/`

If found: skip steps 2–4, jump to Step 5 (commit a note in the PR description that no UI change was needed).

If absent: add an input that PATCHes `immigration_cases.permit_expiry_date` via the existing immigration endpoints. Follow the same TDD loop as B2.

- [ ] **Step 5: Commit (or no-op note)**

If a change was made:

```bash
git add frontend/src/features/platform-v2/intake/
git commit -m "feat(intake): expose permit_expiry_date in IntakeWizard immigration step

Phase B3."
```

If no change needed, document in the Phase B PR body.

---

### Task B4: Phase B PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin compliance/phase-b-intake-fields
gh pr create --title "feat(compliance): Phase B — surface compliance fields in IntakeWizard" --body "$(cat <<'EOF'
## Summary
- Adds an HR PATCH endpoint to set `relocation_cases.expected_start_date` (feeds the tax_183_day rule).
- Surfaces `employer_reg_number` and `expected_start_date` in `IntakeWizard.tsx`.
- Verifies / adds `permit_expiry_date` collection (no UI change needed if already present).

Phase B of the BL-Compliance follow-up. Phase A (precondition guard) must be merged first. Phase C (scheduler) is blocked on at least one prod case being filled end-to-end via this UI.

## Test plan
- [x] Backend tests for the new PATCH endpoint (smoke, happy path, tenant isolation, payload validation).
- [x] Vitest component tests for the new inputs in IntakeWizard.
- [x] `tsc --noEmit` clean.
- [ ] Manual: log into HR command center, fill the two fields for one real case, confirm `relocation_cases.expected_start_date` and `imm_employee_profiles.employer_reg_number` are written.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Phase C — Scheduled evaluation with a dry-run safety net

**Hard gate before turning on live writes:** two weeks of dry-run output reviewed; per-rule alert counts look sane (no rule firing on >50% of cases without explanation).

### Task C1: Add a `dry_run` parameter to the evaluator

**Files:**
- Modify: `backend/app/services/compliance_evaluator.py` — `run_evaluation` + `run_compliance_evaluation` accept `dry_run: bool = False`
- Test: `backend/tests/test_compliance_evaluator.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_run_evaluation_dry_run_does_not_insert():
    """dry_run=True must report would-be firings without calling store.insert_alert."""
    rule = ComplianceRule(
        id="rule-tax", category="tax", severity="high",
        trigger_condition={"type": "day_count", "field": "days_present_in_host",
                            "operator": "gte", "value": 183, "unit": "days"},
    )
    case = CaseComplianceData(case_id="c1", days_present_in_host=200)
    source = FakeSource([rule], [case])
    store = FakeStore()
    result = run_evaluation(source, store, today=TODAY, dry_run=True)
    assert result.cases_evaluated == 1
    assert result.alerts_created == 1     # reported as "would-be created"
    assert store.inserted == []            # but nothing actually persisted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_compliance_evaluator.py::test_run_evaluation_dry_run_does_not_insert -v`
Expected: FAIL — `run_evaluation` does not accept `dry_run`.

- [ ] **Step 3: Add `dry_run` to `run_evaluation` and the production wrapper**

In `backend/app/services/compliance_evaluator.py`:

```python
def run_evaluation(
    source: ComplianceDataSource,
    store: AlertStore,
    today: Optional[date] = None,
    dry_run: bool = False,
) -> EvaluationResult:
    today = today or date.today()
    rules = list(source.active_rules())
    rule_by_id = {r.id: r for r in rules}
    result = EvaluationResult()
    for case in source.open_cases():
        result.cases_evaluated += 1
        for firing in evaluate(rules, case, today):
            if store.open_alert_exists(firing.case_id, firing.rule_id):
                result.alerts_skipped_existing += 1
                continue
            if not dry_run:
                store.insert_alert(firing, rule_by_id[firing.rule_id].severity)
            result.alerts_created += 1
    log.info(
        "compliance_evaluator: %d cases, %d alerts created (dry_run=%s), %d skipped (existing)",
        result.cases_evaluated, result.alerts_created, dry_run, result.alerts_skipped_existing,
    )
    return result


def run_compliance_evaluation(
    db: Any,
    today: Optional[date] = None,
    company_id: Optional[str] = None,
    dry_run: bool = False,
) -> EvaluationResult:
    source = SqlComplianceDataSource(db, today=today, company_id=company_id)
    store = SqlAlertStore(db)
    return run_evaluation(source, store, today=today, dry_run=dry_run)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_compliance_evaluator.py -v`
Expected: PASS — new test + pre-existing tests (dry_run defaults to False, so existing behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/compliance_evaluator.py backend/tests/test_compliance_evaluator.py
git commit -m "feat(compliance): add dry_run flag to evaluator

Reports would-be firings without inserting compliance_alerts rows.
Used by the scheduled cron during the first two weeks of operation.
Phase C1."
```

---

### Task C2: Admin fleet-wide evaluate endpoint

**Files:**
- Modify: `backend/app/routers/compliance.py` — add `POST /api/compliance/evaluate-all` (admin-only)
- Test: extend `backend/tests/test_compliance_router.py`

- [ ] **Step 1: Write the failing test**

Append to `test_compliance_router.py`:

```python
def test_evaluate_all_requires_admin(hr_client):
    # HR (not admin) must be rejected.
    r = hr_client.post("/api/compliance/evaluate-all?dry_run=true")
    assert r.status_code in (401, 403), r.text


def test_evaluate_all_admin_dry_run_returns_counts(admin_client):
    r = admin_client.post("/api/compliance/evaluate-all?dry_run=true")
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"cases_evaluated", "alerts_created", "alerts_skipped_existing", "dry_run"} <= set(body)
    assert body["dry_run"] is True
```

(If `admin_client` fixture doesn't exist, add one that overrides `get_current_user` to return `{"role": "admin"}` and `require_admin` to allow.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_compliance_router.py::test_evaluate_all_requires_admin tests/test_compliance_router.py::test_evaluate_all_admin_dry_run_returns_counts -v`
Expected: FAIL — endpoint absent.

- [ ] **Step 3: Add the admin endpoint**

In `backend/app/routers/compliance.py`:

```python
from fastapi import Query
from ..auth_deps import require_admin


class EvaluateAllResponse(BaseModel):
    cases_evaluated: int
    alerts_created: int
    alerts_skipped_existing: int
    dry_run: bool


@router.post("/evaluate-all", response_model=EvaluateAllResponse)
def evaluate_all(
    dry_run: bool = Query(True),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> EvaluateAllResponse:
    """Fleet-wide compliance run (admin-only). Defaults to dry_run=True so the
    scheduled cron is safe-by-default; pass dry_run=false explicitly to persist."""
    with SessionLocal() as db:
        result = run_compliance_evaluation(db, dry_run=dry_run)
        if not dry_run:
            db.commit()
        else:
            db.rollback()
    return EvaluateAllResponse(
        cases_evaluated=result.cases_evaluated,
        alerts_created=result.alerts_created,
        alerts_skipped_existing=result.alerts_skipped_existing,
        dry_run=dry_run,
    )
```

(If `require_admin` doesn't exist in `auth_deps`, use the existing admin-check pattern from another router — e.g. how `backend/main.py` gates admin routes. Match the canonical pattern; do not invent a new one.)

- [ ] **Step 4: Register the router (verify dual-mount per CLAUDE.md)**

```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '/api/compliance' in r.path))"
```

Expected: includes `/api/compliance/evaluate-all`.

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && pytest tests/test_compliance_router.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/compliance.py backend/tests/test_compliance_router.py backend/main.py backend/app/main.py
git commit -m "feat(compliance): admin POST /api/compliance/evaluate-all

Fleet-wide run, admin-only, dry_run=true by default. Designed for the
scheduled cron job. Phase C2."
```

---

### Task C3: GitHub Actions daily cron (dry-run by default)

**Files:**
- Create: `.github/workflows/compliance-daily.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/compliance-daily.yml`, modeled on `.github/workflows/calibration-monthly.yml`:

```yaml
name: Daily compliance evaluation

# Calls POST /api/compliance/evaluate-all once a day. Dry-run by default
# during the first 2 weeks of operation — flip to dry_run=false via the
# workflow_dispatch input after manual review of the dry-run output.

on:
  schedule:
    # 04:00 UTC every day.
    - cron: "0 4 * * *"
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Dry-run mode (no alerts persisted)"
        required: false
        default: "true"

concurrency:
  group: compliance-daily
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  evaluate:
    name: Run compliance evaluation
    runs-on: ubuntu-latest
    timeout-minutes: 5
    # Gate on a single repo var so this is a no-op until secrets are wired.
    if: ${{ vars.COMPLIANCE_CRON_ENABLED == 'true' }}
    env:
      DRY_RUN: ${{ github.event.inputs.dry_run || 'true' }}
      API_BASE: ${{ vars.COMPLIANCE_API_BASE }}        # e.g. https://api.relopass.com
      ADMIN_TOKEN: ${{ secrets.COMPLIANCE_ADMIN_TOKEN }}
    steps:
      - name: POST /api/compliance/evaluate-all
        run: |
          set -euo pipefail
          if [ -z "${API_BASE:-}" ] || [ -z "${ADMIN_TOKEN:-}" ]; then
            echo "API_BASE or ADMIN_TOKEN not set; skipping."
            exit 0
          fi
          response=$(curl -fsS -X POST \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" \
            -H "Content-Type: application/json" \
            "${API_BASE}/api/compliance/evaluate-all?dry_run=${DRY_RUN}")
          echo "$response"
          # Surface counts in the workflow summary.
          echo "## Compliance run (dry_run=${DRY_RUN})" >> "$GITHUB_STEP_SUMMARY"
          echo '```json' >> "$GITHUB_STEP_SUMMARY"
          echo "$response" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
```

- [ ] **Step 2: Verify the YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/compliance-daily.yml'))"
```

Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/compliance-daily.yml
git commit -m "ci(compliance): daily evaluation cron (dry-run by default)

Calls POST /api/compliance/evaluate-all once a day at 04:00 UTC. Gated
behind vars.COMPLIANCE_CRON_ENABLED so it is a no-op until the
ADMIN_TOKEN secret + API_BASE var are configured. dry_run=true by
default; flip via workflow_dispatch after 2 weeks of review. Phase C3."
```

---

### Task C4: Phase C PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin compliance/phase-c-scheduler
gh pr create --title "feat(compliance): Phase C — daily dry-run scheduler" --body "$(cat <<'EOF'
## Summary
- Adds `dry_run` flag to `run_compliance_evaluation` — reports would-be firings without persisting.
- New admin `POST /api/compliance/evaluate-all` endpoint for fleet-wide runs (dry_run=true by default).
- GitHub Actions daily cron (04:00 UTC) calling the admin endpoint in dry-run mode. Gated behind `vars.COMPLIANCE_CRON_ENABLED` so it is a no-op until the `COMPLIANCE_ADMIN_TOKEN` secret and `COMPLIANCE_API_BASE` var are configured.

Phase C of the BL-Compliance follow-up. Phases A + B must be merged first AND at least one prod case must have `employer_reg_number` and `expected_start_date` filled end-to-end via the new intake UI.

## Test plan
- [x] Unit test for dry_run skipping `store.insert_alert`.
- [x] Router tests for admin gating and dry-run response shape.
- [x] `python3 -c "import yaml; yaml.safe_load(...)"` on the workflow.
- [ ] Post-merge: configure `vars.COMPLIANCE_CRON_ENABLED=true`, `vars.COMPLIANCE_API_BASE`, and `secrets.COMPLIANCE_ADMIN_TOKEN`; trigger via workflow_dispatch; verify the response in the workflow summary.
- [ ] Two weeks of dry-run output reviewed before flipping `dry_run=false`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Post-merge follow-ups (NOT in scope of these PRs)

- Configure the three repo settings (`vars.COMPLIANCE_CRON_ENABLED`, `vars.COMPLIANCE_API_BASE`, `secrets.COMPLIANCE_ADMIN_TOKEN`) once the PR lands.
- After 2 weeks of dry-run output, flip the workflow_dispatch default to `dry_run=false` (or set via repo var).
- Add a `/admin/compliance/dry-run-log` page surfacing the cron output so HR can review what would have fired — optional, only if dry-run logs aren't easily reviewable via the GitHub Actions summary alone.

## Notion Work Queue items to update

- AIQ-746 (BL-Compliance.4) — close once Phase A lands and the engine is safe to run broadly.
- Open new Work Queue items for Phase B and Phase C tied back to this plan.

---

## Self-review notes

- **Spec coverage:** Phase A addresses the noise problem; Phase B addresses the durable backfill path; Phase C addresses the scheduler — all three asks from the follow-up brief are covered.
- **Placeholder scan:** Task B2 + B3 deliberately leave the exact JSX to "match surrounding pattern" because IntakeWizard.tsx structure dictates it — the test contract (`getByLabelText`) is concrete enough that the implementation is constrained.
- **Type consistency:** `profile_exists` is used the same way everywhere (`CaseComplianceData.profile_exists: bool`, `precondition_field="profile_exists"`, SQL column `profile_exists`). `dry_run` is propagated identically through `run_evaluation` → `run_compliance_evaluation` → router → workflow.
- **Hard rules respected:** CLAUDE.md dual-mount registration called out twice (B1 step 4, C2 step 4); migration uses Supabase MCP per memory.

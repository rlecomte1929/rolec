"""
AIQ-1591 — employee_tasks column-rename regression guard.

Migration 20260513280000 renamed employee_tasks."type" -> "task_type", but four
DB-layer queries kept the old name and raised `column "type" does not exist` on
Postgres — swallowed by their except blocks into None / [] (HR add-task 500'd, the
HR backlog was always empty). There was no test exercising these functions, so
SQLite (which would have used whatever column the test created) never caught it.

This test builds the employee_tasks table with the CURRENT column name (`task_type`)
— matching prod — and exercises each fixed path. If the code reverts to `type`, the
queries fail against the `task_type`-only table and these tests go red.

Strategy: in-memory SQLite + the real CasesMixin / HrMixin query methods.
"""
from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.db.cases import CasesMixin
from backend.db.hr import HrMixin


class _DB(CasesMixin, HrMixin):
    """Minimal composition: the query methods only need self.engine."""

    def __init__(self, engine):
        self.engine = engine


# employee_tasks with the POST-rename column name (`task_type`), plus every column
# the fixed SELECTs reference. profiles is needed for the list_hr_backlog JOIN.
_DDL = """
CREATE TABLE employee_tasks (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    employee_id TEXT,
    org_id TEXT,
    task_type TEXT,
    title TEXT,
    description TEXT,
    due_date TEXT,
    status TEXT,
    required_file_upload INTEGER,
    submission_data TEXT,
    file_url TEXT,
    submitted_at TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_note TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE profiles (
    id TEXT PRIMARY KEY,
    full_name TEXT,
    email TEXT
);
"""

_CASE_ID = "case-1"
_EMP_ID = "emp-1"
_ORG_ID = "org-1"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _DDL.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
        conn.execute(
            text("INSERT INTO profiles (id, full_name, email) VALUES (:i, :n, :e)"),
            {"i": _EMP_ID, "n": "Test Employee", "e": "emp@probe.test"},
        )
    return _DB(engine)


def test_create_employee_task_for_case_succeeds(db):
    """HR add-task: the fix's core path. Was returning None (endpoint 500) via `type`."""
    created = db.create_employee_task_for_case(
        case_id=_CASE_ID,
        employee_id=_EMP_ID,
        org_id=_ORG_ID,
        task_type="custom",
        title="Sign the lease",
        description="Upload the signed lease",
    )
    assert created is not None, "create returned None — the INSERT failed (regression to `type`?)"
    assert created["task_type"] == "custom"
    assert created["title"] == "Sign the lease"


def test_created_task_is_visible_to_employee_and_hr(db):
    """After HR adds a task the employee (task_type) and HR (backlog: aliased `type`) both see it."""
    created = db.create_employee_task_for_case(
        case_id=_CASE_ID, employee_id=_EMP_ID, org_id=_ORG_ID,
        task_type="document_upload", title="Passport scan", required_file_upload=True,
    )
    assert created is not None
    task_id = created["id"]

    # get_employee_task — EmployeeTask contract exposes `task_type`
    one = db.get_employee_task(task_id=task_id, employee_id=_EMP_ID)
    assert one is not None
    assert one["task_type"] == "document_upload"

    # list_employee_tasks_for_case_hr — EmployeeTaskListResponse, also `task_type`
    hr_case_tasks = db.list_employee_tasks_for_case_hr(case_id=_CASE_ID)
    assert any(t["id"] == task_id and t["task_type"] == "document_upload" for t in hr_case_tasks)

    # list_hr_backlog — HrBacklogTask contract expects the aliased `type` key
    backlog = db.list_hr_backlog(org_id=_ORG_ID)
    row = next((t for t in backlog if t["id"] == task_id), None)
    assert row is not None, "task missing from HR backlog (primary+fallback both empty?)"
    assert row["type"] == "document_upload", "backlog must alias task_type -> type for HrBacklogTask"

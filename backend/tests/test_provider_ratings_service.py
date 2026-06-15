"""CATALOG-3 / AIQ-1067 — provider_ratings_service unit tests.

Self-contained SQLite harness (mirrors test_plan_versions_service): create the
two tables the service touches, monkeypatch SessionLocal, exercise the public
functions. Covers idempotency (criterion 1) and the live aggregate (criterion 2).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.services import provider_ratings_service as svc

_SCHEMA = """
CREATE TABLE provider_ratings (
  id TEXT PRIMARY KEY,
  employee_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  supplier_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  score INTEGER NOT NULL,
  comment TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (employee_id, supplier_id, case_id)
);
CREATE TABLE supplier_scoring_metadata (
  supplier_id TEXT PRIMARY KEY,
  average_rating REAL,
  review_count INTEGER NOT NULL DEFAULT 0,
  -- mirror prod: NOT NULL with no DB default, so the service INSERT must set them
  preferred_partner BOOLEAN NOT NULL,
  premium_partner BOOLEAN NOT NULL
);
"""

_EMP1 = "11111111-1111-1111-1111-111111111111"
_EMP2 = "22222222-2222-2222-2222-222222222222"
_COMPANY = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CASE = "cccccccc-cccc-cccc-cccc-cccccccccccc"
_SUP = "supplier-acme-movers"


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in _SCHEMA.split(";"))):
            conn.execute(text(stmt))
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(svc, "SessionLocal", TestSession)
    return TestSession


def _count_rows(session_factory, supplier_id=_SUP):
    with session_factory() as db:
        return db.execute(
            text("SELECT COUNT(*) FROM provider_ratings WHERE supplier_id = :s"),
            {"s": supplier_id},
        ).scalar()


def _aggregate(session_factory, supplier_id=_SUP):
    with session_factory() as db:
        row = db.execute(
            text("SELECT average_rating, review_count FROM supplier_scoring_metadata WHERE supplier_id = :s"),
            {"s": supplier_id},
        ).first()
    return (row.average_rating, row.review_count) if row else (None, None)


def test_record_creates_rating_and_aggregate(session_factory):
    out = svc.record_rating(
        employee_id=_EMP1, company_id=_COMPANY, supplier_id=_SUP, case_id=_CASE, score=4
    )
    assert out == {"average_rating": 4.0, "review_count": 1}
    assert _count_rows(session_factory) == 1
    assert _aggregate(session_factory) == (4.0, 1)


def test_idempotent_per_employee_supplier_case(session_factory):
    # Same (employee, supplier, case) rated twice -> one row, latest score wins.
    svc.record_rating(employee_id=_EMP1, company_id=_COMPANY, supplier_id=_SUP, case_id=_CASE, score=3)
    out = svc.record_rating(employee_id=_EMP1, company_id=_COMPANY, supplier_id=_SUP, case_id=_CASE, score=5)
    assert _count_rows(session_factory) == 1  # no duplicate
    assert out == {"average_rating": 5.0, "review_count": 1}
    assert _aggregate(session_factory) == (5.0, 1)


def test_multiple_employees_average(session_factory):
    svc.record_rating(employee_id=_EMP1, company_id=_COMPANY, supplier_id=_SUP, case_id=_CASE, score=4)
    out = svc.record_rating(employee_id=_EMP2, company_id=_COMPANY, supplier_id=_SUP, case_id=_CASE, score=2)
    assert _count_rows(session_factory) == 2
    assert out == {"average_rating": 3.0, "review_count": 2}


def test_comment_persisted_and_updated(session_factory):
    svc.record_rating(
        employee_id=_EMP1, company_id=_COMPANY, supplier_id=_SUP, case_id=_CASE, score=4, comment="Great mover"
    )
    with session_factory() as db:
        c = db.execute(text("SELECT comment FROM provider_ratings WHERE employee_id = :e"), {"e": _EMP1}).scalar()
    assert c == "Great mover"

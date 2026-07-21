"""AIQ-1602 Seg 4: HR supplier-submission moderation queue — service logic.

Runs the real create → approve → reject flow against an in-memory SQLite DB
(the supplier ORM tables + a SQLite-compatible submissions table), so the
approval genuinely exercises supplier_registry.create_supplier.
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db import Base
from backend.app.models import (
    Supplier,
    SupplierScoringMetadata,
    SupplierServiceCapability,
)
from backend.app.services import hr_supplier_submissions as svc
from backend.app.services.supplier_registry import DuplicateSupplierError

_SUBMISSIONS_DDL = """
CREATE TABLE hr_supplier_submissions (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  submitted_by_user_id TEXT,
  name TEXT NOT NULL,
  service_category TEXT NOT NULL,
  coverage_scope_type TEXT NOT NULL DEFAULT 'country',
  country_code TEXT,
  city_name TEXT,
  contact_email TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  reviewed_by TEXT,
  reviewed_at TEXT,
  review_notes TEXT,
  created_supplier_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Supplier.__table__,
            SupplierServiceCapability.__table__,
            SupplierScoringMetadata.__table__,
        ],
    )
    with engine.begin() as conn:
        conn.execute(text(_SUBMISSIONS_DDL))
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(svc, "SessionLocal", TestSession)
    return TestSession


def _submit(name="ABC Movers", cat="movers", company="co-1"):
    return svc.create(
        company_id=company,
        submitted_by="hr-1",
        name=name,
        service_category=cat,
        coverage_scope_type="city",
        country_code="DE",
        city_name="Munich",
        contact_email="abc@example.com",
    )


def test_create_is_pending_and_makes_no_supplier(session_factory):
    sub = _submit()
    assert sub["status"] == "pending"
    assert sub["name"] == "ABC Movers"
    assert svc.list_for_company("co-1")[0]["id"] == sub["id"]
    with session_factory() as s:
        assert s.query(Supplier).count() == 0  # nothing in the registry yet


def test_approve_creates_supplier_with_hr_provenance(session_factory):
    sub = _submit()
    out = svc.approve(submission_id=sub["id"], reviewed_by="admin-1")
    assert out["status"] == "approved"
    assert out["created_supplier_id"]
    with session_factory() as s:
        suppliers = s.query(Supplier).all()
        assert len(suppliers) == 1
        sup = suppliers[0]
        assert sup.name == "ABC Movers"
        assert sup.source == "customer_upload"
        assert sup.source_reference == f"hr_submission:{sub['id']}"
        caps = s.query(SupplierServiceCapability).all()
        assert len(caps) == 1
        assert caps[0].service_category == "movers"
        assert caps[0].city_name == "Munich"


def test_approve_country_less_submission_promotes_as_global(session_factory):
    """AIQ-1659: a submission with no country (HR form defaulted scope to 'country'
    but left the country blank) must still be approvable — as a GLOBAL supplier —
    instead of 400ing in create_supplier's validate_capability."""
    sub = svc.create(
        company_id="co-1",
        submitted_by="hr-1",
        name="Worldwide Relo",
        service_category="movers",
        coverage_scope_type="country",  # the form's default when no city is given
        country_code=None,              # ...but no country was entered
        city_name=None,
    )
    out = svc.approve(submission_id=sub["id"], reviewed_by="admin-1")
    assert out["status"] == "approved"
    assert out["created_supplier_id"]
    with session_factory() as s:
        caps = s.query(SupplierServiceCapability).all()
        assert len(caps) == 1
        # Scope derived from the fields present → global (no country to scope to).
        assert caps[0].coverage_scope_type == "global"
        assert caps[0].country_code is None


def test_approve_country_only_submission_stays_country_scoped(session_factory):
    """A submission WITH a country (no city) approves as 'country' scope, unchanged."""
    sub = svc.create(
        company_id="co-1",
        submitted_by="hr-1",
        name="DE Movers",
        service_category="movers",
        coverage_scope_type="country",
        country_code="DE",
        city_name=None,
    )
    svc.approve(submission_id=sub["id"], reviewed_by="admin-1")
    with session_factory() as s:
        cap = s.query(SupplierServiceCapability).one()
        assert cap.coverage_scope_type == "country"
        assert cap.country_code == "DE"


def test_reject_requires_notes_and_creates_no_supplier(session_factory):
    sub = _submit()
    with pytest.raises(ValueError):
        svc.reject(submission_id=sub["id"], reviewed_by="admin-1", notes="")
    out = svc.reject(submission_id=sub["id"], reviewed_by="admin-1", notes="Not a fit")
    assert out["status"] == "rejected"
    assert out["review_notes"] == "Not a fit"
    with session_factory() as s:
        assert s.query(Supplier).count() == 0


def test_duplicate_name_on_approve_leaves_submission_pending(session_factory):
    a = _submit(name="Dup Vendor")
    b = _submit(name="Dup Vendor")
    svc.approve(submission_id=a["id"], reviewed_by="admin-1")
    with pytest.raises(DuplicateSupplierError):
        svc.approve(submission_id=b["id"], reviewed_by="admin-1")
    still = [x for x in svc.list_for_company("co-1") if x["id"] == b["id"]][0]
    assert still["status"] == "pending"


def test_approve_already_resolved_raises(session_factory):
    sub = _submit()
    svc.approve(submission_id=sub["id"], reviewed_by="admin-1")
    with pytest.raises(svc.SubmissionNotPending):
        svc.approve(submission_id=sub["id"], reviewed_by="admin-1")


def test_create_requires_name_and_category(session_factory):
    with pytest.raises(ValueError):
        svc.create(company_id="co-1", submitted_by="hr-1", name="  ", service_category="movers")
    with pytest.raises(ValueError):
        svc.create(company_id="co-1", submitted_by="hr-1", name="X", service_category="")

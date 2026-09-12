"""
Tests for the admin coverage dashboard route (GET /api/admin/coverage).

Seeds in-memory SQLite copies of the two acquisition tables, points the coverage
service's SessionLocal at them, and drives the route via TestClient. The load-
bearing case is the country-key merge: facts key on the catalog's UPPERCASE NAME
("IRELAND") while providers key on ISO-2 ("IE"), and the service must land both on
one row. Also covers auth gating, the status splits, the per-category breakdown,
totals, and the cache/refresh behaviour.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import coverage_service as cov  # noqa: E402
from backend.app.routers import coverage as coverage_router  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402


_SCHEMA = [
    """CREATE TABLE requirement_items (
         id TEXT PRIMARY KEY,
         country_code TEXT,
         review_status TEXT NOT NULL DEFAULT 'approved',
         verification_status TEXT
       )""",
    "CREATE TABLE suppliers (id TEXT PRIMARY KEY, name TEXT)",
    """CREATE TABLE supplier_service_capabilities (
         id TEXT PRIMARY KEY,
         supplier_id TEXT,
         service_category TEXT,
         country_code TEXT,
         platform_vetting_status TEXT NOT NULL DEFAULT 'pending'
       )""",
    "CREATE TABLE countries (code TEXT PRIMARY KEY, name TEXT, flag_emoji TEXT)",
]

# (id, country_code, review_status, verification_status)
_FACTS = [
    ("f1", "IRELAND", "approved", "expert_verified"),
    ("f2", "IRELAND", "approved", None),
    ("f3", "IRELAND", "approved", None),
    ("f4", "IRELAND", "pending", None),
    ("f5", "IRELAND", "rejected", None),
    ("f6", "SPAIN", "pending", None),
    ("f7", "SPAIN", "pending", None),
]
# (id, supplier_id, service_category, country_code (ISO-2), platform_vetting_status)
_CAPS = [
    ("c1", "s1", "banks", "IE", "approved"),
    ("c2", "s1", "banks", "IE", "approved"),
    ("c3", "s2", "banks", "IE", "pending"),
    ("c4", "s2", "movers", "IE", "approved"),
    ("c5", "s2", "healthcare_ipmi", "IE", "pending"),  # non-serving category
    ("c6", "s1", "schools", "ES", "pending"),
]


def _seed(Session):
    s = Session()
    try:
        for r in _FACTS:
            s.execute(
                text(
                    "INSERT INTO requirement_items "
                    "(id, country_code, review_status, verification_status) "
                    "VALUES (:id, :cc, :rs, :vs)"
                ),
                {"id": r[0], "cc": r[1], "rs": r[2], "vs": r[3]},
            )
        for sid in ("s1", "s2"):
            s.execute(text("INSERT INTO suppliers (id, name) VALUES (:id, :id)"), {"id": sid})
        for r in _CAPS:
            s.execute(
                text(
                    "INSERT INTO supplier_service_capabilities "
                    "(id, supplier_id, service_category, country_code, platform_vetting_status) "
                    "VALUES (:id, :sup, :cat, :cc, :st)"
                ),
                {"id": r[0], "sup": r[1], "cat": r[2], "cc": r[3], "st": r[4]},
            )
        s.execute(
            text("INSERT INTO countries (code, name, flag_emoji) VALUES ('IE', 'Ireland', '🇮🇪')")
        )
        s.commit()
    finally:
        s.close()


@pytest.fixture
def sqlite_sessionmaker(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for ddl in _SCHEMA:
            conn.execute(text(ddl))
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(cov, "SessionLocal", Session)
    monkeypatch.setattr(cov, "_CACHE", None)  # never leak a snapshot across tests
    return Session


def _app(*, is_admin: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(coverage_router.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-1", "is_admin": is_admin}
    return app


def _country(body, iso):
    return next(c for c in body["countries"] if c["iso"] == iso)


def test_non_admin_is_rejected(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    r = TestClient(_app(is_admin=False)).get("/api/admin/coverage")
    assert r.status_code == 403


def test_name_and_iso_keying_merge_onto_one_row(sqlite_sessionmaker):
    """The load-bearing case: IRELAND facts + IE providers → a single row."""
    _seed(sqlite_sessionmaker)
    body = TestClient(_app()).get("/api/admin/coverage").json()
    assert {c["iso"] for c in body["countries"]} == {"IE", "ES"}

    ie = _country(body, "IE")
    assert ie["name"] == "Ireland"          # display name from the countries table
    assert ie["flag"] == "🇮🇪"
    assert ie["facts"] == {"approved": 3, "pending": 1, "rejected": 1, "total": 5}
    # providers: banks (2 approved + 1 pending) + movers (1) + healthcare (1 pending)
    assert ie["providers"]["by_cat"]["banks"] == 3
    assert ie["providers"]["by_cat"]["movers"] == 1
    assert ie["providers"]["by_cat"]["schools"] == 0
    assert ie["providers"]["approved"] == 3
    assert ie["providers"]["pending"] == 2
    assert ie["providers"]["total"] == 5     # includes the non-serving healthcare row
    assert ie["providers"]["by_cat_detail"]["banks"] == {
        "approved": 2, "pending": 1, "total": 3,
    }


def test_non_serving_category_excluded_from_by_cat(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    body = TestClient(_app()).get("/api/admin/coverage").json()
    ie = _country(body, "IE")
    # healthcare_ipmi is not one of the six serving categories → not a by_cat key…
    assert "healthcare_ipmi" not in ie["providers"]["by_cat"]
    # …but it still counts toward the provider total (5), so total > sum(by_cat)=4.
    assert ie["providers"]["total"] == 5
    assert sum(ie["providers"]["by_cat"].values()) == 4
    assert "healthcare_ipmi" in body["extra_categories"]
    assert ie["providers"]["by_cat_detail"]["healthcare_ipmi"]["pending"] == 1


def test_fallback_display_name_when_country_ref_missing(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    body = TestClient(_app()).get("/api/admin/coverage").json()
    es = _country(body, "ES")  # no 'ES' row in countries → title-case the catalog name
    assert es["name"] == "Spain"
    assert es["facts"]["pending"] == 2
    assert es["providers"]["by_cat"]["schools"] == 1


def test_totals(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    body = TestClient(_app()).get("/api/admin/coverage").json()
    t = body["totals"]
    assert t["destinations"] == 2
    assert t["facts_approved"] == 3
    assert t["facts_pending"] == 3          # Ireland 1 + Spain 2
    assert t["facts_rejected"] == 1
    assert t["facts_total"] == 7
    assert t["caps_total"] == 6             # Ireland 5 + Spain 1
    assert t["caps_approved"] == 3
    assert t["caps_pending"] == 3           # Ireland 2 + Spain 1
    assert t["suppliers"] == 2
    assert t["expert_verified"] == 1
    assert set(body["serving_categories"]) == {
        "banks", "movers", "schools", "legal_admin", "tax_finance", "housing_agencies",
        "temp_accommodation", "medical", "language_integration",  # [ANDREA-P1] settle-in categories
    }


def test_cache_holds_until_refresh(sqlite_sessionmaker):
    Session = sqlite_sessionmaker
    _seed(Session)
    client = TestClient(_app())

    first = client.get("/api/admin/coverage").json()
    assert first["totals"]["facts_total"] == 7

    # add a fact; a plain load still returns the cached snapshot…
    s = Session()
    s.execute(
        text("INSERT INTO requirement_items (id, country_code, review_status) "
             "VALUES ('f8', 'IRELAND', 'approved')")
    )
    s.commit()
    s.close()
    assert client.get("/api/admin/coverage").json()["totals"]["facts_total"] == 7

    # …until refresh forces a recompute.
    refreshed = client.get("/api/admin/coverage", params={"refresh": "true"}).json()
    assert refreshed["totals"]["facts_total"] == 8
    assert refreshed["generated_at"] != first["generated_at"]

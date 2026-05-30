"""
Tests for the admin AI unit-economics rollup route — Parker Step G.

Seeds an in-memory SQLite policy_assistant_traces table, points the rollup service'
SessionLocal at it, and drives the route via TestClient. Covers auth gating, the
aggregate schema, and customer / date filtering.
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

from backend.app.services import ai_unit_economics as econ  # noqa: E402
from backend.app.routers import admin_ai_unit_economics  # noqa: E402
from backend.app.auth_deps import require_admin, get_current_user  # noqa: E402


_SCHEMA = """
CREATE TABLE policy_assistant_traces (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  query_hash TEXT NOT NULL DEFAULT '',
  company_id TEXT NOT NULL DEFAULT '',
  steps_json TEXT NOT NULL DEFAULT '[]',
  total_latency_ms INTEGER NOT NULL DEFAULT 0,
  fallback_triggered INTEGER NOT NULL DEFAULT 0,
  co2e_grams_estimated REAL,
  cost_usd_estimated REAL,
  tokens_in INTEGER,
  tokens_out INTEGER,
  customer_id TEXT,
  feature_key TEXT,
  created_at TEXT NOT NULL
)
"""


@pytest.fixture
def sqlite_sessionmaker(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(econ, "SessionLocal", Session)
    return Session


def _seed(Session):
    rows = [
        # (id, customer, feature, tokens_in, tokens_out, cost, co2e, created_at)
        ("t1", "cust-A", "policy_assistant", 1000, 500, 0.0075, 0.088889, "2026-05-01T10:00:00"),
        ("t2", "cust-A", "policy_assistant", 2000, 800, 0.0130, 0.150000, "2026-05-02T10:00:00"),
        ("t3", "cust-A", "passport_ocr",      500,   0, 0.0050, 0.005556, "2026-05-03T10:00:00"),
        ("t4", "cust-B", "policy_extraction", 300, 100, 0.0010, 0.013000, "2026-05-04T10:00:00"),
    ]
    s = Session()
    try:
        for r in rows:
            s.execute(
                text(
                    "INSERT INTO policy_assistant_traces "
                    "(id, query_hash, company_id, total_latency_ms, fallback_triggered, "
                    " tokens_in, tokens_out, cost_usd_estimated, co2e_grams_estimated, "
                    " customer_id, feature_key, created_at) "
                    "VALUES (:id, '', :cust, 0, 0, :tin, :tout, :cost, :co2e, :cust, :fk, :ca)"
                ),
                {"id": r[0], "cust": r[1], "fk": r[2], "tin": r[3], "tout": r[4],
                 "cost": r[5], "co2e": r[6], "ca": r[7]},
            )
        s.commit()
    finally:
        s.close()


def _app(*, is_admin: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_ai_unit_economics.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-1", "is_admin": is_admin}
    return app


def test_non_admin_is_rejected(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    client = TestClient(_app(is_admin=False))
    r = client.get("/api/admin/ai-unit-economics")
    assert r.status_code == 403


def test_rollup_groups_by_customer_and_feature(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    client = TestClient(_app())
    r = client.get("/api/admin/ai-unit-economics")
    assert r.status_code == 200, r.text
    body = r.json()
    # 3 distinct (customer, feature) buckets.
    assert len(body["rows"]) == 3
    pa = next(x for x in body["rows"] if x["customer_id"] == "cust-A"
              and x["feature_key"] == "policy_assistant")
    assert pa["n_calls"] == 2
    assert pa["total_tokens_in"] == 3000
    assert pa["total_cost_usd"] == pytest.approx(0.0205, abs=1e-6)
    # Totals across everything.
    assert body["totals"]["n_calls"] == 4
    assert body["totals"]["total_cost_usd"] == pytest.approx(0.0265, abs=1e-6)


def test_customer_filter(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    client = TestClient(_app())
    r = client.get("/api/admin/ai-unit-economics", params={"customer_id": "cust-B"})
    body = r.json()
    assert {x["customer_id"] for x in body["rows"]} == {"cust-B"}
    assert body["totals"]["n_calls"] == 1


def test_feature_filter(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    client = TestClient(_app())
    r = client.get("/api/admin/ai-unit-economics", params={"feature_key": "passport_ocr"})
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["feature_key"] == "passport_ocr"


def test_date_range_filter(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    client = TestClient(_app())
    r = client.get(
        "/api/admin/ai-unit-economics",
        params={"from": "2026-05-02T00:00:00", "to": "2026-05-03T23:59:59"},
    )
    body = r.json()
    # Only t2 (policy_assistant) + t3 (passport_ocr) fall in range.
    assert body["totals"]["n_calls"] == 2


def test_empty_range_is_zeroed(sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    client = TestClient(_app())
    r = client.get("/api/admin/ai-unit-economics",
                   params={"from": "2099-01-01", "to": "2099-12-31"})
    body = r.json()
    assert body["rows"] == []
    assert body["totals"]["n_calls"] == 0
    assert body["totals"]["total_cost_usd"] == 0.0

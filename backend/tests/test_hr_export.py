"""
W2-4 — HR policy-compliance export (CSV + PDF).

Mounts the prod app (backend.main:app) so the test also proves the router is
registered there (not only in the modular app). The compliance-matrix builder is
monkeypatched so no DB is touched; auth is overridden per the app-mounted harness.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import hr_analytics
from backend.app.routers.hr_analytics import (
    BENEFIT_COLUMNS,
    BENEFIT_LABELS,
    ComplianceCaseRow,
    ComplianceKpis,
    PolicyComplianceMatrixResponse,
)

_HR_USER = {"id": "hr-1", "role": "HR", "company": "co-1", "is_admin": False}


def _fake_matrix(*, period=None, tier=None, destination=None, user=None):
    cells = {k: "green" for k in BENEFIT_COLUMNS}
    cells["immigration"] = "red"   # over policy cap
    cells["tax"] = "blue"          # exception pending
    return PolicyComplianceMatrixResponse(
        cases=[ComplianceCaseRow(
            id="c1", name="Jane Doe", init="JD", origin="FR", dest="NO",
            tier="senior", assignment_type="long_term", start_date="2026-01-01",
            budget_eur=50000, spend_eur=42000, cells=cells,
        )],
        kpis=ComplianceKpis(
            compliance_pct=92, active_count=5, avg_overage_eur=1200,
            most_overrun_benefit="immigration",
            benefit_columns=BENEFIT_COLUMNS, benefit_labels=BENEFIT_LABELS,
        ),
    )


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(hr_analytics, "get_policy_compliance_matrix", _fake_matrix)
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _HR_USER
    yield TestClient(app)
    app.dependency_overrides.pop(auth_deps.get_current_user, None)


def test_routes_registered_in_prod_app():
    paths = {r.path for r in app.routes}
    assert "/api/hr/policy-compliance-matrix/export.csv" in paths
    assert "/api/hr/policy-compliance-matrix/export.pdf" in paths


def test_csv_export(client):
    r = client.get("/api/hr/policy-compliance-matrix/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=policy_compliance_" in r.headers["content-disposition"]
    body = r.text
    assert "Jane Doe" in body
    assert BENEFIT_LABELS["immigration"] in body  # header label present
    assert "red" in body and "blue" in body        # cell statuses serialised


def test_pdf_export(client):
    r = client.get("/api/hr/policy-compliance-matrix/export.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"

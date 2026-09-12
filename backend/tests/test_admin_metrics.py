"""
Admin KPI source-of-truth (AIQ-2326 / ADMIN-IA-0a).

Proves the contract that keeps the numbers honest:
  * every metric is a {value, definition, source, as_of} envelope;
  * a metric whose query fails degrades to value=None (tile omitted), never 500;
  * the Executive overview AND the Companies overview both read their counts from
    admin_metrics_service (the mock-spy) rather than duplicating SQL — this is what
    makes "Companies 71" and "Companies 48" the same number;
  * the summary and companies-overview routes are registered in the prod app
    (backend.main.app), i.e. the dual-layer registration actually happened.

DB-hitting queries are monkeypatched, mirroring test_exec_overview_service.py, so the
suite stays green on the bare sqlite CI env.
"""
from backend.app.services import admin_metrics_service as ams

_METRIC_KEYS = (
    "tenants_total", "tenants_active", "hr_users", "employees", "signups",
    "cases_total", "cases_open", "cases_closed", "destinations_with_data",
    "destinations_curated", "content_review_pending", "prospects_waiting",
)


def test_summary_envelope_shape(monkeypatch):
    for key in _METRIC_KEYS:
        monkeypatch.setattr(ams, key, lambda k=key: {
            "value": 1, "definition": f"def {k}", "source": "s", "as_of": "t",
        })
    summary = ams.build_metrics_summary()
    for key in _METRIC_KEYS:
        m = summary[key]
        assert {"value", "definition", "source", "as_of"}.issubset(m), key
        assert m["definition"] and m["source"] and m["as_of"], key
        assert isinstance(m["value"], int), key
        assert m["value"] is not None


def test_summary_omits_uncomputable_metrics(monkeypatch):
    monkeypatch.setattr(ams, "tenants_total", lambda: {
        "value": 4, "definition": "d", "source": "s", "as_of": "t",
    })
    monkeypatch.setattr(ams, "tenants_active", lambda: {
        "value": None, "definition": "d", "source": "s", "as_of": "t",
    })
    for key in _METRIC_KEYS:
        if key in ("tenants_total", "tenants_active"):
            continue
        monkeypatch.setattr(ams, key, lambda: {
            "value": None, "definition": "d", "source": "s", "as_of": "t",
        })
    summary = ams.build_metrics_summary()
    assert summary["tenants_total"]["value"] == 4
    assert "tenants_active" not in summary
    assert summary["tenants_total"].get("value") is not None


def test_ceo_definition_wording(monkeypatch):
    monkeypatch.setattr(ams, "_safe_int", lambda fn: 1)
    assert ams.tenants_total()["definition"] == "Companies on the platform, excluding test tenants."
    assert ams.tenants_active()["definition"] == (
        "Real tenants with at least one open case assignment (assigned, submitted or awaiting intake)."
    )
    assert ams.hr_users()["definition"] == "HR logins across real tenants."
    assert ams.employees()["definition"] == "Employee logins across real tenants."
    assert ams.destinations_with_data()["definition"] == (
        "Destinations with at least one requirement fact or vetted provider in the catalog."
    )
    assert ams.destinations_curated()["definition"] == "Countries with a curated requirements catalog."


def test_metric_degrades_to_none_on_failure(monkeypatch):
    def boom(_query):
        raise RuntimeError("relation does not exist")

    monkeypatch.setattr(ams, "_scalar", boom)
    m = ams.cases_total()
    assert m["value"] is None
    # definition/source survive so the tooltip and audit trail are still meaningful
    assert m["definition"] and m["source"] and m["as_of"]


def _spy(recorder, name, value=1):
    def _fn():
        recorder.add(name)
        return {"value": value, "definition": "d", "source": "s", "as_of": "t"}
    return _fn


def test_exec_overview_reads_admin_metrics(monkeypatch):
    """build_exec_overview must source companies/employees/signups/cases from the SoT."""
    import backend.app.services.exec_overview_service as exo

    calls: set[str] = set()
    monkeypatch.setattr(ams, "tenants_total", _spy(calls, "tenants_total", 5))
    monkeypatch.setattr(ams, "hr_users", _spy(calls, "hr_users", 3))
    monkeypatch.setattr(ams, "employees", _spy(calls, "employees", 7))
    monkeypatch.setattr(ams, "signups", _spy(calls, "signups", 9))
    monkeypatch.setattr(ams, "cases_total", _spy(calls, "cases_total", 2))
    monkeypatch.setattr(ams, "cases_closed", _spy(calls, "cases_closed", 1))
    # avoid the DB for the two remaining direct counts (new_companies / in_intake)
    monkeypatch.setattr(exo, "_scalar_counts", lambda q, p: {"new_companies": 0, "in_intake": 0})

    out = exo.build_exec_overview()

    assert out["growth"]["companies"] == 5  # the shared tenant number, not count(*)
    assert {"tenants_total", "hr_users", "employees"}.issubset(calls)
    assert out["funnel"]["signups"] == 9
    assert {"signups", "cases_total", "cases_closed"}.issubset(calls)


def test_companies_overview_reads_admin_metrics(monkeypatch):
    """The Companies KPI strip (build_companies_overview) reuses the SoT functions."""
    calls: set[str] = set()
    for name in ("tenants_total", "tenants_active", "hr_users", "employees"):
        monkeypatch.setattr(ams, name, _spy(calls, name))

    out = ams.build_companies_overview()

    assert {"tenants_total", "tenants_active", "hr_users", "employees"}.issubset(calls)
    assert out["tenants_total"]["value"] == 1


def test_overview_declared_before_company_id_path():
    """The 500 was FastAPI capturing 'overview' as company_id. Order in main.py is the fix."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1].joinpath("main.py").read_text()
    overview = src.index('@app.get("/api/admin/companies/overview")')
    detail = src.index('@app.get("/api/admin/companies/{company_id}")')
    assert overview < detail


def test_metrics_summary_router_registered_in_both_apps():
    from backend.app.main import create_app
    from backend.app.routers.admin_metrics import router

    assert any(getattr(r, "path", None) == "/api/admin/metrics/summary" for r in router.routes)
    modular = create_app()
    paths = {getattr(r, "path", None) for r in modular.routes}
    assert "/api/admin/metrics/summary" in paths


def test_companies_overview_and_detail_not_captured(monkeypatch):
    """GET /companies/overview must not be captured by /companies/{company_id}."""
    import backend.app.services.query_counter as qc
    monkeypatch.setattr(qc, "install_query_counter", lambda engine: None)

    from fastapi.testclient import TestClient
    from backend.main import app, require_admin
    import backend.main as main_mod

    overview = {
        "tenants_total": {"value": 4, "definition": "d", "source": "s", "as_of": "t"},
        "as_of": "t",
    }
    monkeypatch.setattr(
        "backend.app.services.admin_metrics_service.build_companies_overview",
        lambda: overview,
    )

    seen_ids: list[str] = []

    def fake_get_company(company_id: str):
        seen_ids.append(company_id)
        if company_id == "co-real":
            return {"id": "co-real", "name": "Acme"}
        return None

    monkeypatch.setattr(main_mod.db, "get_company", fake_get_company)
    monkeypatch.setattr(main_mod.db, "list_hr_users_with_profiles", lambda _cid: [])
    monkeypatch.setattr(main_mod.db, "list_employees_with_profiles", lambda _cid: [])
    monkeypatch.setattr(main_mod.db, "list_assignments_for_company_with_details", lambda _cid: [])
    monkeypatch.setattr(main_mod.db, "get_admin_policies_by_company", lambda _cid: {"policies": []})
    monkeypatch.setattr(main_mod.db, "get_company_detail_orphan_diagnostics", lambda _cid: {})
    monkeypatch.setattr(main_mod.db, "log_audit", lambda *a, **k: None)

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/admin/metrics/summary" in paths
    assert "/api/admin/companies/overview" in paths

    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "role": "ADMIN"}
    try:
        client = TestClient(app, raise_server_exceptions=False)
        ov = client.get("/api/admin/companies/overview")
        assert ov.status_code == 200, ov.text
        body = ov.json()
        assert body["tenants_total"]["value"] == 4
        assert "overview" not in seen_ids

        detail = client.get("/api/admin/companies/co-real")
        assert detail.status_code == 200, detail.text
        assert detail.json()["company"]["id"] == "co-real"
        assert "co-real" in seen_ids
    finally:
        app.dependency_overrides.pop(require_admin, None)

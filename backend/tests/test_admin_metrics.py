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


def test_summary_envelope_shape():
    summary = ams.build_metrics_summary()
    for key in _METRIC_KEYS:
        m = summary[key]
        assert {"value", "definition", "source", "as_of"}.issubset(m), key
        assert m["definition"] and m["source"] and m["as_of"], key
        # value may be None on the CI DB (missing table) but never a wrong type
        assert m["value"] is None or isinstance(m["value"], int), key


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


def test_routes_registered_in_prod_app():
    """CLAUDE.md hard rule: a router must be reachable on the app uvicorn boots
    (backend.main.app), not only the modular app — else it 405s in prod."""
    from backend.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/admin/metrics/summary" in paths
    assert "/api/admin/companies/overview" in paths

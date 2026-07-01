"""Admin DSAR desk — the cross-tenant erasure-requests route is dual-registered + resolves."""
from pathlib import Path


def test_route_registered_in_both_apps():
    backend_dir = Path(__file__).resolve().parents[1]
    app_main = (backend_dir / "app/main.py").read_text()
    assert "admin_dsar," in app_main
    assert "app.include_router(admin_dsar.router)" in app_main
    prod_main = (backend_dir / "main.py").read_text()
    assert "import admin_dsar as admin_dsar_router" in prod_main
    assert "app.include_router(admin_dsar_router.router)" in prod_main

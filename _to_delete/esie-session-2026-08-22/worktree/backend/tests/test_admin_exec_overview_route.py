"""Executive dashboard route — dual-registration (CLAUDE.md hard rule)."""
from pathlib import Path


def test_route_registered_in_both_apps():
    backend_dir = Path(__file__).resolve().parents[1]
    app_main = (backend_dir / "app/main.py").read_text()
    assert "admin_exec_overview," in app_main
    assert "app.include_router(admin_exec_overview.router)" in app_main
    prod_main = (backend_dir / "main.py").read_text()
    assert "import admin_exec_overview as admin_exec_overview_router" in prod_main
    assert "app.include_router(admin_exec_overview_router.router)" in prod_main

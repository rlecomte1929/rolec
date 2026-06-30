"""
Mission Control P1 — the demands-console router: dual-registration (CLAUDE.md hard
rule) + the soft-fail-on-missing-table helper (the store is committed-not-applied,
so reads must not 500 the console).
"""
from pathlib import Path

from sqlalchemy.exc import ProgrammingError

from backend.app.routers.admin_work_items import _missing_table


def test_missing_table_detected():
    exc = ProgrammingError("stmt", {}, Exception('relation "public.work_items" does not exist'))
    assert _missing_table(exc) is True
    exc2 = ProgrammingError("stmt", {}, Exception("42P01 undefined_table"))
    assert _missing_table(exc2) is True


def test_other_errors_are_not_swallowed():
    exc = ProgrammingError("stmt", {}, Exception("syntax error near FROM"))
    assert _missing_table(exc) is False


def test_route_registered_in_both_apps():
    backend_dir = Path(__file__).resolve().parents[1]
    app_main = (backend_dir / "app/main.py").read_text()
    assert "admin_work_items," in app_main
    assert "app.include_router(admin_work_items.router)" in app_main
    prod_main = (backend_dir / "main.py").read_text()
    assert "import admin_work_items as admin_work_items_router" in prod_main
    assert "app.include_router(admin_work_items_router.router)" in prod_main

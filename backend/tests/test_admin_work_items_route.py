"""
Mission Control P1 — the demands-console router: dual-registration (CLAUDE.md hard
rule) + the soft-fail-on-missing-table helper (the store is committed-not-applied,
so reads must not 500 the console).
"""
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import ProgrammingError

from backend.app.routers.admin_work_items import (
    _missing_table,
    _verify_callback_secret,
    dispatch_block_reason,
    dispatch_enabled,
)


class _Req:
    def __init__(self, auth=""):
        self.headers = {"Authorization": auth}


def test_dispatch_guard_only_allows_trivial_non_blocked():
    assert dispatch_block_reason(True, {"blocked": False}) is None
    assert dispatch_block_reason(False, {"blocked": False}) is not None  # not agent-eligible
    assert dispatch_block_reason(True, {"blocked": True}) is not None    # blocklisted surface
    # triage_json may arrive as a JSON string from the DB
    assert dispatch_block_reason(True, '{"blocked": true}') is not None


def test_dispatch_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MISSION_CONTROL_DISPATCH_ENABLED", raising=False)
    assert dispatch_enabled() is False
    monkeypatch.setenv("MISSION_CONTROL_DISPATCH_ENABLED", "true")
    assert dispatch_enabled() is True


def test_callback_secret_fail_closed(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    with pytest.raises(HTTPException) as e1:
        _verify_callback_secret(_Req("Bearer anything"))
    assert e1.value.status_code == 503  # not configured → blocked
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    with pytest.raises(HTTPException) as e2:
        _verify_callback_secret(_Req("Bearer wrong"))
    assert e2.value.status_code == 401
    _verify_callback_secret(_Req("Bearer s3cret"))  # correct → no raise


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

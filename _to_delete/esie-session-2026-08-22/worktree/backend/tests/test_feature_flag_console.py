"""
Feature-flag console — the DB-then-env resolver (the load-bearing logic) + dual-reg.
resolve_flag is tested with a fake session so no DB is needed.
"""
from pathlib import Path

import backend.app.services.feature_flags as ff


class _FakeFlag:
    def __init__(self, enabled):
        self.enabled = enabled


class _FakeDB:
    """Mimics SQLAlchemy Session.get for FeatureFlag / FeatureFlagAccount."""
    def __init__(self, flag=None, accounts=()):
        self._flag = flag
        self._accts = set(accounts)

    def get(self, model, key):
        if model is ff.FeatureFlag:
            return self._flag
        return object() if key in self._accts else None  # FeatureFlagAccount (key, account_id)


def test_db_flag_enabled_global():
    assert ff.resolve_flag("k", db=_FakeDB(flag=_FakeFlag(True))) is True


def test_db_flag_disabled_wins_over_env(monkeypatch):
    monkeypatch.setenv("k", "true")
    assert ff.resolve_flag("k", db=_FakeDB(flag=_FakeFlag(False))) is False  # explicit DB off beats env


def test_db_flag_account_scoped():
    db = _FakeDB(flag=_FakeFlag(True), accounts={("k", "acct-1")})
    assert ff.resolve_flag("k", account_id="acct-1", db=db) is True
    assert ff.resolve_flag("k", account_id="acct-2", db=db) is False  # not on allowlist


def test_env_fallback_when_no_db_row(monkeypatch):
    monkeypatch.setenv("MY_TOGGLE", "1")
    assert ff.resolve_flag("MY_TOGGLE", db=_FakeDB(flag=None)) is True
    monkeypatch.setenv("MY_TOGGLE", "off")
    assert ff.resolve_flag("MY_TOGGLE", db=_FakeDB(flag=None)) is False


def test_env_default_when_nothing_set(monkeypatch):
    monkeypatch.delenv("ABSENT", raising=False)
    assert ff.resolve_flag("ABSENT", db=_FakeDB(flag=None)) is False
    assert ff.resolve_flag("ABSENT", env_default=True, db=_FakeDB(flag=None)) is True


def test_routes_registered_in_both_apps():
    backend_dir = Path(__file__).resolve().parents[1]
    app_main = (backend_dir / "app/main.py").read_text()
    assert "admin_feature_flags," in app_main
    assert "app.include_router(admin_feature_flags.router)" in app_main
    prod_main = (backend_dir / "main.py").read_text()
    assert "import admin_feature_flags as admin_feature_flags_router" in prod_main
    assert "app.include_router(admin_feature_flags_router.router)" in prod_main

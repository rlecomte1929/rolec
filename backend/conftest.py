"""
Root conftest — runs before pytest collects any test.

Problem: pytest.ini sets pythonpath = . which adds backend/ to sys.path,
making `app` a top-level package. The app code uses 3-level relative imports
(e.g. `from ...database import db`) that only work when `backend` is itself
importable as a package (i.e. the repo root is in sys.path).

Fix: swap backend/ out of sys.path and add the repo root instead so that
`backend.app.services.*` resolves correctly. Then mock backend.database
so unit tests don't need a live DB connection.
"""
import os
import sys
from unittest.mock import MagicMock
from urllib.parse import urlparse

import pytest

# ── Path surgery ─────────────────────────────────────────────────────────────
_backend_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_backend_dir)

# Remove backend/ (added by pytest's pythonpath = .) to avoid the
# double-import trap where `app` and `backend.app` are different objects.
while _backend_dir in sys.path:
    sys.path.remove(_backend_dir)

# Add repo root so `backend` is importable as a (namespace) package.
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# ── Mock backend.database before any test module is imported ─────────────────
# This prevents SQLAlchemy engine creation from firing during import.
_mock_db = MagicMock()
_mock_db.engine = MagicMock()
_mock_module = MagicMock()
_mock_module.db = _mock_db

sys.modules.setdefault("backend.database", _mock_module)


# ── AIQ-1777: refuse to run the suite against a non-local database ───────────
# The mock above is not a guarantee. Test modules that need real SQL pop it and swap
# the real backend.database back in — two of them at MODULE IMPORT, during collection
# (test_e1b_extraction_persist, test_policy_config_matrix_propagation). Any app module
# first imported inside that window binds the REAL db, whose engine comes from
# DATABASE_URL. With a local .env that is the production pooler, and a unit test then
# talks to prod with no warning: measured 2026-08-09, pets.list_pets SELECTed against
# the live pooler and returned 0 rows that looked exactly like the product bug under test.
#
# Per-file `os.environ.setdefault("DATABASE_URL", "sqlite:...")` guards do NOT help:
# db_config calls load_dotenv(override=False), so whoever imports first wins, and in a
# full run the tests/ subdirectories collect before tests/test_*.py.
#
# So decide once, before collection, and fail loudly.

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_OPT_OUT = "RELOPASS_ALLOW_REMOTE_DB_IN_TESTS"


def _resolve_effective_database_url():
    """Resolve DATABASE_URL exactly as backend/db_config.py will, without importing it.

    Returns (url, source). Mirrors db_config.py:11-36 — the production guard, then
    os.environ (dotenv uses override=False, so a real env var wins), then .env, then
    the sqlite default.
    """
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url, "the DATABASE_URL environment variable"

    is_production = (
        os.getenv("RENDER") in ("true", "1") or os.getenv("ENV") == "production"
    )
    if not is_production:
        try:
            from dotenv import dotenv_values  # read-only; does not touch os.environ

            env_path = os.path.join(_repo_root, ".env")
            dotenv_url = (dotenv_values(env_path) or {}).get("DATABASE_URL")
            if dotenv_url:
                return dotenv_url, env_path
        except ImportError:
            pass

    return "sqlite:///./relopass.db", "db_config's built-in default"


def _describe_target(url):
    """scheme + host only. NEVER the credentials — this string is printed."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "(no host)"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port}"
    except Exception:
        return "(unparseable DATABASE_URL)"


def _is_local_target(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme.startswith("sqlite"):
        return True
    return (parsed.hostname or "") in _LOCAL_HOSTS


def pytest_configure(config):
    """Abort the run when the resolved DATABASE_URL is not local.

    Must run before collection: engines are built at module-import time, so a
    session-scoped fixture would fire only after a connection could already exist.
    """
    if os.environ.get(_OPT_OUT) == "1":
        return

    url, source = _resolve_effective_database_url()
    if _is_local_target(url):
        return

    raise pytest.UsageError(
        "\n"
        "Refusing to run the test suite against a non-local database.\n"
        f"  target: {_describe_target(url)}\n"
        f"  source: {source}\n"
        "\n"
        "Tests import app modules that build a real SQLAlchemy engine from DATABASE_URL,\n"
        "so this run could read from — or write to — that database.\n"
        "\n"
        "Fix one of these:\n"
        "  * export DATABASE_URL=sqlite:///./ci_test.db   (what CI uses)\n"
        f"  * unset DATABASE_URL in your .env\n"
        f"  * {_OPT_OUT}=1  to override deliberately (integration runs only)\n"
    )

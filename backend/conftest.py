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

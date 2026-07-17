"""AIQ-1587 — guard against SQLite-mirror ↔ prod schema drift for policy_cap_requests.

The HR compliance page was dead in prod for weeks because the SQLite mirror
(backend/db/misc.py) created a DIFFERENT shape than prod, so local + CI never
touched the real schema — the drift was invisible. This test freezes the prod
column set (probed live against project nsvefcvpvwwwhuqyuqmp on 2026-07-17) and
fails if the SQLite mirror diverges. It backs the compliance page, which (after
AIQ-1587) reads/writes policy_cap_requests.

Update PROD_* only when a real migration changes the prod shape — never to make a
drifted mirror pass.
"""
import sys

# backend/conftest.py installs a MagicMock for backend.database before collection so
# unit tests don't hit a live DB. This test MUST exercise the real SQLite mirror, so
# drop the mock before importing the real Database.
sys.modules.pop("backend.database", None)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import Database  # noqa: E402

# Frozen from prod information_schema.columns for public.policy_cap_requests.
PROD_POLICY_CAP_REQUESTS_COLUMNS = {
    "id", "case_id", "organization_id", "category", "requested_amount",
    "cap_amount", "currency", "reason", "status", "hr_note",
    "requested_by_user_id", "resolved_by_user_id", "created_at",
    "resolved_at", "updated_at", "exception_type",
}


def _fresh_sqlite_schema():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db = Database()
    db.engine = engine
    db.request_engine = engine
    db.init_db()
    return engine


def _columns(engine, table: str):
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def test_policy_cap_requests_mirror_matches_prod_shape():
    engine = _fresh_sqlite_schema()
    mirror = _columns(engine, "policy_cap_requests")
    missing = PROD_POLICY_CAP_REQUESTS_COLUMNS - mirror
    extra = mirror - PROD_POLICY_CAP_REQUESTS_COLUMNS
    assert not missing, f"SQLite mirror is MISSING prod columns: {sorted(missing)}"
    assert not extra, f"SQLite mirror has columns NOT in prod: {sorted(extra)}"

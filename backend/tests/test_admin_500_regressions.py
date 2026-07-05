"""Regression guards for three admin-API 500s found in the 2026-07-05 admin audit.

All three were Postgres-only (uuid/text type mismatches or route shadowing) and were
INVISIBLE to the SQLite test suite — hence these are structural/source-level guards, not
behavioural tests. The behavioural proof is the live prod re-probe (endpoints return 2xx).
"""
import inspect
import re
import uuid

from backend.app.routers import admin_catalog


def test_discovery_quota_key_is_valid_uuid():
    """catalog_scrape_quota.company_id is UUID in prod; the admin-discovery sentinel
    must be a valid UUID or get_quota_state 500s with 22P02 (invalid input syntax)."""
    uuid.UUID(admin_catalog._DISCOVERY_QUOTA_KEY)  # raises ValueError if not a valid UUID


def test_people_index_casts_profile_id_comparisons():
    """hr_users.profile_id / employees.profile_id are TEXT while profiles.id is UUID in
    prod; comparing them directly raises 'operator does not exist: text = uuid' (42883),
    which made /api/admin/users 500 and /api/admin/people silently return empty. Every
    `profile_id = <profiles.id>` comparison must cast the uuid side to text."""
    from backend.db import users

    src = inspect.getsource(users.UsersMixin.get_admin_people_index)
    # No bare `profile_id = p.id` (without a CAST) may remain.
    bare = re.findall(r"profile_id\s*=\s*p\.id\b(?!\s*AS)", src)
    assert not bare, f"uncast profile_id = p.id comparison(s) will 500 on Postgres: {bare}"
    assert "CAST(p.id AS TEXT)" in src, "expected profiles.id cast to text in the join predicates"


def test_policies_templates_route_precedes_policy_id():
    """GET /api/admin/policies/templates must be registered BEFORE the
    /api/admin/policies/{policy_id} catch-all, else it resolves policy_id='templates'
    and 500s in get_admin_policy_detail."""
    from backend.main import app

    paths = [getattr(r, "path", "") for r in app.routes]
    assert "/api/admin/policies/templates" in paths
    assert "/api/admin/policies/{policy_id}" in paths
    assert paths.index("/api/admin/policies/templates") < paths.index(
        "/api/admin/policies/{policy_id}"
    ), "templates route is shadowed by {policy_id} — reorder so templates registers first"

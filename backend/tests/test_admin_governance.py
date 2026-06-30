"""
Governance — the security-critical guards are the ONLY protection (service role
bypasses RLS), so test them hard: grant requires @relopass.com; revoke is blocked
for the last admin + for self-removal. Plus the audit filter builder + dual-reg.
"""
from pathlib import Path

from backend.app.routers.admin_governance import _audit_where, validate_grant, validate_revoke


def test_grant_requires_relopass_domain():
    assert validate_grant("attacker@gmail.com") is not None
    assert validate_grant("") is not None
    assert validate_grant("new.admin@relopass.com") is None
    assert validate_grant("  NEW.ADMIN@Relopass.com ") is None  # normalised


def test_revoke_blocks_last_admin():
    assert validate_revoke("a@relopass.com", "b@relopass.com", admin_count=1) is not None  # last admin
    assert validate_revoke("a@relopass.com", "b@relopass.com", admin_count=2) is None


def test_revoke_blocks_self_removal():
    assert validate_revoke("me@relopass.com", "me@relopass.com", admin_count=3) is not None  # self
    assert validate_revoke("ME@relopass.com ", "me@relopass.com", admin_count=3) is not None  # normalised self
    assert validate_revoke("other@relopass.com", "me@relopass.com", admin_count=3) is None


def test_audit_where_builds_filters():
    where, params = _audit_where("cases", "update", None, None, "2026-01-01", None)
    assert "al.entity_type = :entity_type" in where
    assert "al.action_type = :action_type" in where
    assert "al.created_at >= :date_from" in where
    assert params == {"entity_type": "cases", "action_type": "update", "date_from": "2026-01-01"}
    # no filters → empty clause
    assert _audit_where(None, None, None, None, None, None) == ("", {})
    # event filter targets the JSONB event key
    w2, p2 = _audit_where(None, None, "REASSIGN_HR_OWNER", None, None, None)
    assert "new_value_json->>'event'" in w2 and p2["event"] == "REASSIGN_HR_OWNER"


def test_routes_registered_in_both_apps():
    backend_dir = Path(__file__).resolve().parents[1]
    app_main = (backend_dir / "app/main.py").read_text()
    assert "admin_governance," in app_main
    assert "app.include_router(admin_governance.router)" in app_main
    prod_main = (backend_dir / "main.py").read_text()
    assert "import admin_governance as admin_governance_router" in prod_main
    assert "app.include_router(admin_governance_router.router)" in prod_main

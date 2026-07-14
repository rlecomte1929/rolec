"""TD-FIX-7 (AIQ-1510): corridor lock for test-drive sessions.

The beta campaign measures the platform per corridor across five locked routes. The
corridor is *assigned* at provisioning (``test_sessions.corridor_id``) but was never
*enforced*: a tester could put their case on any route, breaking the corridor ↔ case
correspondence the whole analysis rests on.

This module is the single source of truth for what each corridor id means as a concrete
route, plus the acting-user → corridor resolver the guards call.

Two call sites enforce it (defense in depth — a UI lock can be bypassed):
  1. ``backend/main.py`` ``assign_case``      — stamps the route onto the case at assign.
  2. ``cases_write.py`` ``patch_case``        — overrides ``relocationBasics`` on write,
     which is where the employee intake actually submits origin/destination.

Non-test users have no ``test_sessions`` row, so ``resolve_test_drive_route`` returns
None and both guards become no-ops. Real HR keeps full freedom of route.
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy import text

from ...database import db

logger = logging.getLogger(__name__)

# The identity marker for a test-drive account. Provisioning mints
# hr-{slug}-{suffix}@probe.test / emp-{slug}-{suffix}@probe.test (test_drive.py).
# NB: deliberately narrower than db/test_data_filter.looks_like_test_email(), which also
# matches the @testco.com e2e seed accounts — those are not test-drive testers and must
# not get a corridor lock.
TEST_DRIVE_EMAIL_DOMAIN = "@probe.test"

# corridor_id → the concrete route a test-drive case is pinned to.
# Keys are the ISO-2 origin_destination pair and are the canonical list of locked
# corridors (see LOCKED_CORRIDORS below) — the provisioner whitelists against the same
# set, so a test-drive case can never land on a corridor outside these five.
# Cities mirror the tester-facing labels in frontend/src/pages/public/testDriveContent.ts.
# IN_DE is the one that differs: the page shows "India" (a country) as the origin label,
# so the case carries Mumbai as the concrete origin city the intake form needs.
TEST_DRIVE_CORRIDOR_ROUTES: Dict[str, Dict[str, str]] = {
    "FR_NO": {"home_country": "FR", "home_city": "Paris",     "host_country": "NO", "host_city": "Oslo"},
    "IN_DE": {"home_country": "IN", "home_city": "Mumbai",    "host_country": "DE", "host_city": "Munich"},
    "GB_US": {"home_country": "GB", "home_city": "London",    "host_country": "US", "host_city": "New York"},
    "NL_SG": {"home_country": "NL", "home_city": "Amsterdam", "host_country": "SG", "host_city": "Singapore"},
    "ES_AE": {"home_country": "ES", "home_city": "Madrid",    "host_country": "AE", "host_city": "Dubai"},
}

LOCKED_CORRIDORS = list(TEST_DRIVE_CORRIDOR_ROUTES)


def _corridor_id_for_email(email: str) -> Optional[str]:
    """The corridor_id of the test session this email belongs to, or None.

    Joins through `users.username` because test_sessions.hr_user_id / emp_user_id are
    always NULL in practice — provisioning only writes hr_username / emp_username
    (test_drive.py). Matches BOTH usernames: the HR account assigns the case, but the
    EMPLOYEE account is the one that submits the intake carrying origin/destination.
    """
    sql = text(
        "SELECT ts.corridor_id "
        "FROM test_sessions ts "
        "JOIN users u ON u.username IN (ts.hr_username, ts.emp_username) "
        "WHERE LOWER(u.email) = :email "
        "ORDER BY ts.created_at DESC "
        "LIMIT 1"
    )
    with db.engine.connect() as conn:
        row = conn.execute(sql, {"email": email}).mappings().first()
    return row.get("corridor_id") if row else None


def resolve_test_drive_route(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """The locked route for a test-drive user, or None for everyone else.

    Never raises: a lookup failure must degrade to "not a test-drive user" rather than
    break case assignment or intake submission for real customers.
    """
    email = ((user or {}).get("email") or "").strip().lower()
    if not email.endswith(TEST_DRIVE_EMAIL_DOMAIN):
        return None
    try:
        corridor_id = _corridor_id_for_email(email)
    except Exception:
        logger.warning("test_drive_corridor: corridor lookup failed", exc_info=True)
        return None
    if not corridor_id:
        return None
    route = TEST_DRIVE_CORRIDOR_ROUTES.get(str(corridor_id).strip().upper())
    if route is None:
        logger.warning("test_drive_corridor: unknown corridor_id=%s", corridor_id)
        return None
    return dict(route)

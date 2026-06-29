"""Case rule-update notification service (P2-02e / AIQ-693).

Reads/dismisses the per-case "rule updated — please review" notifications that
P2-02d writes on review approval (public.case_rule_update_notifications). Powers
the in-app roadmap banner: list the active ones for a case, and dismiss one.

Pure functions over an injected executor (`conn`: a SQLAlchemy Connection or
Session); the case router supplies the real engine connection and enforces
case-access auth.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import text

log = logging.getLogger(__name__)

_LIST_ACTIVE_SQL = text(
    """
    SELECT n.id::text                       AS id,
           n.source_change_review_id::text  AS source_change_review_id,
           n.created_at                      AS created_at,
           r.source_name                     AS source_name,
           r.source_url                      AS source_url
    FROM public.case_rule_update_notifications n
    JOIN public.source_change_reviews r ON r.id = n.source_change_review_id
    WHERE n.case_id = :case_id AND n.status = 'active'
    ORDER BY n.created_at DESC
    """
)

_GET_ACTIVE_SQL = text(
    "SELECT id::text AS id FROM public.case_rule_update_notifications "
    "WHERE id = :id AND case_id = :case_id AND status = 'active'"
)

_DISMISS_SQL = text(
    "UPDATE public.case_rule_update_notifications "
    "SET status = :status, dismissed_at = now() WHERE id = :id"
)


def list_active_rule_updates(conn: Any, case_id: str) -> List[Dict[str, Any]]:
    """Active rule-update notifications for a case, newest first."""
    rows = conn.execute(_LIST_ACTIVE_SQL, {"case_id": case_id}).mappings().all()
    return [dict(r) for r in rows]


def dismiss_rule_update(conn: Any, case_id: str, notification_id: str) -> Dict[str, Any]:
    """Dismiss one active notification for a case.

    Raises ValueError if no active notification with that id exists for the case
    (already dismissed, wrong case, or unknown id) — the case_id scoping makes a
    cross-case dismiss a no-op error rather than a silent success.
    """
    rows = conn.execute(
        _GET_ACTIVE_SQL, {"id": notification_id, "case_id": case_id}
    ).mappings().all()
    if not rows:
        raise ValueError(
            f"rule-update notification {notification_id!r} not active for case {case_id!r}"
        )
    conn.execute(_DISMISS_SQL, {"status": "dismissed", "id": notification_id})
    log.info("case_rule_update %s dismissed for case %s", notification_id, case_id)
    return {"id": notification_id, "status": "dismissed"}

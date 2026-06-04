"""Admin material-change review service (P2-02d / AIQ-692).

Backs the human-in-the-loop gate of the source-change monitoring pipeline. When
a crawled page diff is classified material (source_change_classifier, P2-02b), a
row lands in `public.source_change_reviews` with status `pending`. An admin then:

  * approves → every *active* case citing the changed rule (active_case_finder,
    P2-02c) gets a `public.case_rule_update_notifications` row (the contract the
    in-app roadmap banner, P2-02e, reads), and the review is marked `approved`
    with the notified set recorded for audit; or
  * rejects → the review is marked `rejected` (with an optional note); no case is
    notified.

Pure functions over an injected executor (`conn`: a SQLAlchemy Connection or
Session) and an injected finder, so the approve/reject logic is unit-testable
without a live DB. The thin admin router supplies the real engine connection.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Sequence

from sqlalchemy import text

from .active_case_finder import find_active_cases_for_rule_version

log = logging.getLogger(__name__)

CaseFinder = Callable[[str], Sequence[str]]

_LIST_PENDING_SQL = text(
    """
    SELECT id::text AS id, rule_version_id::text AS rule_version_id, source_url,
           source_name, old_excerpt, new_excerpt, changed_sections,
           status, created_at
    FROM public.source_change_reviews
    WHERE status = :status
    ORDER BY created_at ASC
    LIMIT :limit OFFSET :offset
    """
)

_GET_REVIEW_SQL = text(
    "SELECT rule_version_id::text AS rule_version_id, status "
    "FROM public.source_change_reviews WHERE id = :id"
)

_INSERT_NOTIFICATION_SQL = text(
    """
    INSERT INTO public.case_rule_update_notifications (case_id, source_change_review_id)
    VALUES (:case_id, :review_id)
    ON CONFLICT (case_id, source_change_review_id) DO NOTHING
    """
)

_APPROVE_SQL = text(
    """
    UPDATE public.source_change_reviews
       SET status = :status,
           notified_case_ids = CAST(:notified_case_ids AS jsonb),
           reviewed_by = :reviewed_by,
           reviewed_at = now()
     WHERE id = :id
    """
)

_REJECT_SQL = text(
    """
    UPDATE public.source_change_reviews
       SET status = :status,
           reviewed_by = :reviewed_by,
           reviewed_at = now(),
           review_note = :review_note
     WHERE id = :id
    """
)


def list_pending_reviews(conn: Any, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Return pending material-change reviews, oldest first."""
    rows = conn.execute(
        _LIST_PENDING_SQL, {"status": "pending", "limit": limit, "offset": offset}
    ).mappings().all()
    return [dict(r) for r in rows]


def _load_pending_review(conn: Any, review_id: str) -> Dict[str, Any]:
    rows = conn.execute(_GET_REVIEW_SQL, {"id": review_id}).mappings().all()
    if not rows:
        raise ValueError(f"source_change_review {review_id!r} not found")
    review = dict(rows[0])
    if review.get("status") != "pending":
        raise ValueError(
            f"source_change_review {review_id!r} is {review.get('status')!r}, not pending"
        )
    return review


def approve_review(
    conn: Any,
    review_id: str,
    reviewed_by: str,
    finder: CaseFinder = find_active_cases_for_rule_version,
) -> Dict[str, Any]:
    """Approve a pending review: notify every active case citing the rule.

    Raises ValueError if the review does not exist or is not pending (so a
    double-approve is a no-op error, not a duplicate notification storm).
    """
    review = _load_pending_review(conn, review_id)
    case_ids = list(finder(review["rule_version_id"]))
    for case_id in case_ids:
        conn.execute(_INSERT_NOTIFICATION_SQL, {"case_id": case_id, "review_id": review_id})
    conn.execute(
        _APPROVE_SQL,
        {
            "status": "approved",
            "notified_case_ids": json.dumps(case_ids),
            "reviewed_by": reviewed_by,
            "id": review_id,
        },
    )
    log.info(
        "source_change_review %s approved by %s; notified %d active case(s)",
        review_id, reviewed_by, len(case_ids),
    )
    return {"review_id": review_id, "status": "approved", "notified_case_ids": case_ids}


def reject_review(
    conn: Any,
    review_id: str,
    reviewed_by: str,
    note: str = None,
) -> Dict[str, Any]:
    """Reject a pending review: log it, notify no one.

    Raises ValueError if the review does not exist or is not pending.
    """
    _load_pending_review(conn, review_id)
    conn.execute(
        _REJECT_SQL,
        {
            "status": "rejected",
            "reviewed_by": reviewed_by,
            "review_note": note,
            "id": review_id,
        },
    )
    log.info("source_change_review %s rejected by %s", review_id, reviewed_by)
    return {"review_id": review_id, "status": "rejected"}

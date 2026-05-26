"""
Authorization for /api/mobility/* graph routes.

Non-admin: require assignment_mobility_links row + same visibility as assignment-scoped APIs.
Admin: may read any existing mobility_cases row (pilot / inspect parity).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from fastapi import HTTPException

log = logging.getLogger(__name__)


def _load_assignment_visibility_check() -> Callable[[str, Dict[str, Any]], Any]:
    """Lazy import avoids loading full FastAPI app during isolated unit tests."""
    from backend.main import _require_assignment_visibility  # noqa: WPS433

    return _require_assignment_visibility


def enforce_mobility_graph_read_access(db: Any, mobility_case_id: str, user: Dict[str, Any]) -> None:
    """
    Raise HTTPException if user may not read this mobility graph case.

    UUID alone is insufficient for non-admins: bridge + assignment visibility required.
    """
    cid = (mobility_case_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="Invalid case id")

    if user.get("is_admin"):
        if not db.mobility_case_row_exists(cid):
            raise HTTPException(status_code=404, detail="Mobility case not found")
        return

    aid = db.get_assignment_id_for_mobility_case(cid)
    if not aid:
        # Do not reveal whether the UUID exists without a live assignment link
        raise HTTPException(status_code=404, detail="Mobility case not found")

    _load_assignment_visibility_check()(aid, user)

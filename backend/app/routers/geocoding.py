"""AIQ-1607: server-side proxy for employee address autocomplete (Geoapify).

The provider key stays server-side; the client only ever calls this endpoint.
Returns ``{"disabled": true}`` when no ``GEOAPIFY_API_KEY`` is set → the intake
UI degrades to a plain input. Employee-authenticated (used during intake).

Dual-registered in backend/main.py AND backend/app/main.py (CLAUDE.md 405 rule).
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, Request

from ...rate_limit import limiter
from ..auth_deps import get_current_user
from ..services.geocoding_service import autocomplete, is_enabled

router = APIRouter(prefix="/api/employee/geocode", tags=["geocode"])


@router.get("/autocomplete")
@limiter.limit("600/hour;5000/day")
def address_autocomplete(
    request: Request,
    q: str = Query(..., min_length=3, max_length=200, description="Partial address to autocomplete."),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Address suggestions for the intake office-address field. The Geoapify key
    is server-side only; empty + ``disabled`` when unkeyed (no PII leaves the
    platform until the DPA is signed and the key is configured)."""
    if not is_enabled():
        return {"disabled": True, "suggestions": []}
    return {"disabled": False, "suggestions": autocomplete(q)}

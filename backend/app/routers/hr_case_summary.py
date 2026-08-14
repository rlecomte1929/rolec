"""
HR AI case summary — GET /api/hr/cases/{assignment_id}/ai-summary  (AIQ-1697)

Thin, tenant-safe proxy to the `case-summary` Supabase Edge Function (AIQ-1693/1698).
The browser must NEVER call the Edge Function directly (it would need the service-role
key), so the frontend calls this endpoint; the backend attaches the caller's company_id
and the service-role bearer and forwards to the function.

Tenant isolation is not widened here: `company_id` comes from the authenticated HR user
(`get_org_id_for_hr_user`), never from client input, and the Edge Function independently
404s a case that doesn't belong to that company. A non-HR caller is rejected 403 by the
dependency. Mirrors the edge-invoke pattern in `services/autofix_dispatch.py`.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests
from fastapi import APIRouter, Depends, HTTPException

from ..auth_deps import get_org_id_for_hr_user

router = APIRouter(prefix="/api/hr", tags=["hr-case-summary"])
logger = logging.getLogger(__name__)

_EDGE_TIMEOUT = 20.0


@router.get("/cases/{assignment_id}/ai-summary")
def get_case_ai_summary(
    assignment_id: str,
    company_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Return the AI case summary for one assignment, scoped to the caller's company.

    403 for a non-HR caller (dependency), 404 when the case isn't in the caller's
    company or doesn't exist (from the function), 502/503 when the summary service is
    unreachable/unconfigured — all so the HR card can degrade gracefully.
    """
    base = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not base or not key:
        logger.warning("case-summary proxy not configured (SUPABASE_URL / SERVICE_ROLE_KEY missing)")
        raise HTTPException(status_code=503, detail="AI summary is not configured")

    url = f"{base.rstrip('/')}/functions/v1/case-summary"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            # company_id is the caller's OWN company (from the token), never client input.
            json={"assignment_id": assignment_id, "company_id": company_id},
            timeout=_EDGE_TIMEOUT,
        )
    except requests.RequestException:
        logger.exception("case-summary edge request failed")
        raise HTTPException(status_code=502, detail="Could not reach the summary service")

    if resp.status_code == 404:
        # Unknown assignment OR a case outside the caller's company — no existence oracle.
        raise HTTPException(status_code=404, detail="Case not found")
    if resp.status_code >= 400:
        logger.warning("case-summary edge error %s", resp.status_code)
        raise HTTPException(status_code=502, detail="Summary generation failed")

    try:
        return resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Summary generation failed")

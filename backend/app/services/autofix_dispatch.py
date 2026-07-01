"""
Mission Control P2 — on-demand autofix dispatch.

Fires the EXISTING Supabase autofix edge function for ONE work_item, reusing the
whole proven pipeline (classify → blocklist → branch → draft PR → autofix-validate
→ E2E → merge → deploy → revert). The backend already holds SUPABASE_URL +
SUPABASE_SERVICE_ROLE_KEY — the same credential the nightly cron uses — so no new
GitHub token is needed. Soft no-op (never raises) when unconfigured, so the dispatch
endpoint degrades gracefully.

Requires the edge function's single-demand extension (accepts {work_item}); until
that is deployed the dispatch endpoint stays feature-flagged off.
"""
import logging
import os
from typing import Any, Dict

import requests

log = logging.getLogger(__name__)


def dispatch_autofix(work_item: Dict[str, Any], *, timeout: float = 120.0) -> Dict[str, Any]:
    base = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not base or not key:
        log.warning("autofix dispatch not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing)")
        return {"ok": False, "reason": "not_configured"}

    url = f"{base.rstrip('/')}/functions/v1/autofix-pipeline"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"work_item": work_item},
            timeout=timeout,
        )
    except requests.RequestException as exc:  # network/timeout — never blow up the request
        log.exception("autofix dispatch request failed")
        return {"ok": False, "reason": "request_failed", "error": str(exc)}

    if resp.status_code >= 400:
        log.warning("autofix dispatch edge error %s", resp.status_code)
        return {"ok": False, "reason": "edge_error", "status_code": resp.status_code}

    try:
        data = resp.json()
    except ValueError:
        data = {}
    return {"ok": True, "status_code": resp.status_code, "result": data, "pr_url": data.get("pr_url")}

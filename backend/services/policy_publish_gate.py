"""
Publish gate: only structured, traceable policy_versions may become employee-visible.

Employees consume policy only via `policy_versions.status = 'published'` and resolved benefits.
This module blocks publish when a version would masquerade as usable policy (empty structure,
failed source document, or missing normalization provenance).

See docs/policy/published-policy-consumption-rules.md.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

log = logging.getLogger(__name__)


def _truthy_auto_generated(raw: Any) -> bool:
    if raw is True:
        return True
    if raw is False or raw is None:
        return False
    if isinstance(raw, (int, float)):
        return raw != 0
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes")
    return bool(raw)


def require_employee_publishable_policy_version(db: Any, policy_version_id: str) -> None:
    """
    Raise HTTPException if this version must not be published for employee consumption.

    Rules:
    - Version row must exist.
    - At least one policy_benefit_rules OR policy_exclusions row for this version (non-empty Layer-2 output).
    - Provenance: source_policy_document_id set (document normalization path) OR auto_generated true
      (includes normalize + default template seed).
    - If linked to a policy_document, that document must not be processing_status == 'failed'.
    """
    v = db.get_policy_version(str(policy_version_id))
    if not v:
        raise HTTPException(status_code=404, detail="Policy version not found")

    vid = str(policy_version_id)
    try:
        rules = db.list_policy_benefit_rules(vid)
        excl = db.list_policy_exclusions(vid)
    except Exception as exc:
        log.warning("publish_gate list rules/exclusions failed version_id=%s exc=%s", vid, exc)
        rules, excl = [], []

    if len(rules) == 0 and len(excl) == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "This version cannot be published for employees: it has no benefit rules or exclusions. "
                "Normalize the document or add structured rules in the HR Policy workspace first."
            ),
        )

    doc_id = v.get("source_policy_document_id")
    ag = _truthy_auto_generated(v.get("auto_generated"))
    has_provenance = bool(doc_id) or ag
    if not has_provenance:
        raise HTTPException(
            status_code=400,
            detail=(
                "This version cannot be published: it is not linked to a source policy document and is not "
                "marked as auto-generated from normalization or template. Only structured, traceable versions "
                "may be exposed to employees."
            ),
        )

    if doc_id:
        try:
            doc = db.get_policy_document(str(doc_id), request_id=None)
        except Exception as exc:
            log.warning("publish_gate get_policy_document failed doc_id=%s exc=%s", doc_id, exc)
            doc = None
        if doc and (doc.get("processing_status") or "").lower() == "failed":
            raise HTTPException(
                status_code=400,
                detail=(
                    "The source policy document is in a failed processing state. Fix extraction or reprocess "
                    "before publishing."
                ),
            )

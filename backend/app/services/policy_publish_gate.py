"""
Publish gate: only structured, traceable policy_versions may become employee-visible.

Employees consume policy only via `policy_versions.status = 'published'` and resolved benefits.
This module blocks publish when a version would masquerade as usable policy (empty structure,
failed source document, or missing normalization provenance).

See docs/policy/published-policy-consumption-rules.md.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from .policy_normalization_states import NORMALIZATION_STATE_BLOCK_PUBLISH

log = logging.getLogger(__name__)

# Stable API codes (normalize + publish endpoints, analytics)
PUBLISH_BLOCKED_NO_LAYER2_RULES = "PUBLISH_BLOCKED_NO_LAYER2_RULES"
PUBLISH_BLOCKED_INCOMPLETE_METADATA = "PUBLISH_BLOCKED_INCOMPLETE_METADATA"
PUBLISH_BLOCKED_SOURCE_DOCUMENT_FAILED = "PUBLISH_BLOCKED_SOURCE_DOCUMENT_FAILED"
PUBLISH_BLOCKED_NORMALIZATION_INCOMPLETE = "PUBLISH_BLOCKED_NORMALIZATION_INCOMPLETE"


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


def evaluate_employee_publish_blockers(db: Any, policy_version_id: str) -> Optional[Tuple[str, str]]:
    """
    If the version must not be published for employee consumption, return (error_code, message).
    Otherwise return None.
    """
    v = db.get_policy_version(str(policy_version_id))
    if not v:
        return ("NOT_FOUND", "Policy version not found")

    ns = (v.get("normalization_state") or "").strip().lower()
    if ns and ns in {s.lower() for s in NORMALIZATION_STATE_BLOCK_PUBLISH}:
        return (
            PUBLISH_BLOCKED_NORMALIZATION_INCOMPLETE,
            "This version is marked as normalization_in_progress or normalization_failed and cannot be "
            "published for employees until normalization completes successfully.",
        )

    vid = str(policy_version_id)
    try:
        rules = db.list_policy_benefit_rules(vid)
        excl = db.list_policy_exclusions(vid)
    except Exception as exc:
        log.warning("publish_gate list rules/exclusions failed version_id=%s exc=%s", vid, exc)
        rules, excl = [], []

    if len(rules) == 0 and len(excl) == 0:
        return (
            PUBLISH_BLOCKED_NO_LAYER2_RULES,
            "This version cannot be published for employees: it has no benefit rules or exclusions. "
            "Normalize the document or add structured rules in the HR Policy workspace first.",
        )

    doc_id = v.get("source_policy_document_id")
    ag = _truthy_auto_generated(v.get("auto_generated"))
    has_provenance = bool(doc_id) or ag
    if not has_provenance:
        return (
            PUBLISH_BLOCKED_INCOMPLETE_METADATA,
            "This version cannot be published: it is not linked to a source policy document and is not "
            "marked as auto-generated from normalization or template. Only structured, traceable versions "
            "may be exposed to employees.",
        )

    if doc_id:
        try:
            doc = db.get_policy_document(str(doc_id), request_id=None)
        except Exception as exc:
            log.warning("publish_gate get_policy_document failed doc_id=%s exc=%s", doc_id, exc)
            doc = None
        if doc and (doc.get("processing_status") or "").lower() == "failed":
            return (
                PUBLISH_BLOCKED_SOURCE_DOCUMENT_FAILED,
                "The source policy document is in a failed processing state. Fix extraction or reprocess "
                "before publishing.",
            )

    return None


def require_employee_publishable_policy_version(db: Any, policy_version_id: str) -> None:
    """
    Raise HTTPException if this version must not be published for employee consumption.

    HTTPException.detail is a dict: {"code": <stable code>, "message": <human text>} when blocked,
    so callers can classify failures without parsing strings.
    """
    block = evaluate_employee_publish_blockers(db, policy_version_id)
    if not block:
        return
    code, message = block
    if code == "NOT_FOUND":
        raise HTTPException(status_code=404, detail={"code": code, "message": message})
    raise HTTPException(status_code=400, detail={"code": code, "message": message})

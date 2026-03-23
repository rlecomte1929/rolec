"""
Structured errors for policy normalization (422 responses, not opaque 500s).

Stable error_code values (API contract):
- INVALID_POLICY_VERSION_SCHEMA — Pydantic / assembled payload invalid (true schema failure)
- NORMALIZATION_BLOCKED — draft cannot be persisted (e.g. unknown scope + empty Layer 2)
- NORMALIZATION_NOT_READY — document intake / clauses not ready to normalize (input validation)
- PERSISTENCE_FAILED — DB rejected a row after validation (see persistence_stage)

Publish path (HTTP 200 from normalize when auto-publish is attempted):
- PUBLISH_BLOCKED_* — returned on success body as publish_block_code (see policy_publish_gate)

Legacy alias INVALID_POLICY_VERSIONS_PAYLOAD is still accepted in outcome mapping for old clients.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PolicyNormalizationFieldIssue:
    """Single field-level issue for API `details` array."""

    field: str
    issue: str
    expected: Optional[str] = None
    actual: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"field": self.field, "issue": self.issue}
        if self.expected is not None:
            out["expected"] = self.expected
        if self.actual is not None:
            out["actual"] = self.actual
        return out


@dataclass
class PolicyNormalizationPayloadInvalid(Exception):
    """
    Normalization cannot proceed or persistence failed; maps to HTTP 422 with structured body.

    Raised before any DB writes for blocked drafts and pre-insert validation; may be raised after
    partial writes when Layer-2 insert fails (see error_code).
    """

    error_code: str
    message: str
    details: List[PolicyNormalizationFieldIssue] = field(default_factory=list)
    document_id: Optional[str] = None
    request_id: Optional[str] = None
    policy_readiness: Optional[Dict[str, Any]] = None
    readiness_status: Optional[str] = None
    readiness_issues: List[PolicyNormalizationFieldIssue] = field(default_factory=list)
    mapping_summary: Optional[Dict[str, Any]] = None
    persistence_stage: Optional[str] = None

    def to_response_body(self) -> Dict[str, Any]:
        outcome = _normalization_error_outcome(self.error_code)
        body: Dict[str, Any] = {
            "ok": False,
            "normalized": False,
            "publishable": False,
            "published": False,
            "outcome": outcome,
            "error_code": self.error_code,
            "message": self.message,
            "details": [d.to_json() for d in self.details],
            "request_id": self.request_id,
            "document_id": self.document_id,
        }
        if self.policy_readiness is not None:
            body["policy_readiness"] = self.policy_readiness
        if self.readiness_status is not None:
            body["readiness_status"] = self.readiness_status
        if self.readiness_issues:
            body["readiness_issues"] = [i.to_json() for i in self.readiness_issues]
        if self.mapping_summary is not None:
            body["mapping_summary"] = self.mapping_summary
        if self.persistence_stage is not None:
            body["persistence_stage"] = self.persistence_stage
        return body


def _normalization_error_outcome(error_code: str) -> str:
    if error_code in ("INVALID_POLICY_VERSION_SCHEMA", "INVALID_POLICY_VERSIONS_PAYLOAD"):
        return "validation_failed"
    if error_code == "PERSISTENCE_FAILED":
        return "persistence_failed"
    if error_code in ("POLICY_VERSION_PERSISTENCE_FAILED", "POLICY_LAYER2_PERSISTENCE_FAILED"):
        return "persistence_failed"
    if error_code == "NORMALIZATION_NOT_READY":
        return "normalization_not_ready"
    if error_code == "NORMALIZATION_BLOCKED":
        return "normalization_blocked"
    return "normalization_blocked"

"""
Initialize a company_policies row + draft policy_version from platform starter templates.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .policy_normalization_draft import build_normalization_draft_model
from .policy_normalization_validate import evaluate_normalization_readiness
from .policy_starter_templates import (
    STARTER_TEMPLATE_DISCLAIMER,
    build_starter_template_benefit_rows,
    is_valid_starter_template_key,
    starter_policy_document_stub,
)


class StarterPolicyTemplateInitError(Exception):
    """Business-rule failure for template initialization (HTTP 4xx mapping)."""

    def __init__(self, message: str, *, code: str = "INIT_FAILED") -> None:
        self.code = code
        super().__init__(message)


def _mapped_for_draft(benefit_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    stripped: List[Dict[str, Any]] = []
    for r in benefit_rows:
        o = {k: v for k, v in r.items() if k not in ("policy_version_id", "id")}
        stripped.append(o)
    return {
        "benefit_rules": stripped,
        "exclusions": [],
        "conditions": [],
        "evidence_requirements": [],
        "assignment_applicability": [],
        "draft_rule_candidates": [],
    }


def initialize_company_policy_from_starter_template(
    db: Any,
    *,
    company_id: str,
    template_key: str,
    comparison_ready_structure: bool = True,
    created_by: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    tid = str(template_key or "").strip().lower()
    if not is_valid_starter_template_key(tid):
        raise StarterPolicyTemplateInitError(
            f"Unknown template_key {template_key!r}. Expected one of: conservative, standard, premium.",
            code="UNKNOWN_TEMPLATE",
        )

    existing = db.list_company_policies(company_id)
    if existing:
        raise StarterPolicyTemplateInitError(
            "Company already has a company policy. Starter templates apply only when none exists.",
            code="POLICY_ALREADY_EXISTS",
        )

    policy_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    title = f"Mobility baseline ({tid.title()})"

    db.create_company_policy(
        policy_id=policy_id,
        company_id=company_id,
        title=title,
        version="1.0-template",
        effective_date=None,
        file_url="",
        file_type="application/json",
        created_by=created_by,
        template_source="default_platform_template",
        template_name=f"starter_{tid}",
        is_default_template=False,
        request_id=request_id,
    )
    db.update_company_policy_status(policy_id, "extracted", datetime.utcnow().isoformat())

    db.create_policy_version(
        version_id=version_id,
        policy_id=policy_id,
        source_policy_document_id=None,
        version_number=1,
        status="draft",
        auto_generated=True,
        review_status="pending",
        confidence=1.0 if comparison_ready_structure else 0.85,
        created_by=created_by,
        request_id=request_id,
    )

    benefit_rows = build_starter_template_benefit_rows(
        tid,  # type: ignore[arg-type]
        policy_version_id=version_id,
        comparison_ready_structure=comparison_ready_structure,
    )
    doc_stub = starter_policy_document_stub(tid)
    doc_stub["company_id"] = company_id

    mapped = _mapped_for_draft(benefit_rows)
    norm_core = evaluate_normalization_readiness(
        doc_stub,
        mapped,
        request_id=request_id,
        document_id=None,
    )
    draft = build_normalization_draft_model(
        policy_document=doc_stub,
        company_id=company_id,
        policy_id=policy_id,
        policy_version_id=version_id,
        clauses=[],
        mapped=mapped,
        norm_core=norm_core,
    )

    for row in benefit_rows:
        brid = db.insert_policy_benefit_rule(row)
        for at in ("LTA", "STA"):
            db.insert_policy_assignment_applicability(
                {
                    "policy_version_id": version_id,
                    "benefit_rule_id": brid,
                    "assignment_type": at,
                }
            )

    db.update_policy_version_normalization_draft(version_id, draft, request_id=request_id)

    return {
        "ok": True,
        "policy_id": policy_id,
        "policy_version_id": version_id,
        "template_key": tid,
        "version_status": "draft",
        "benefit_rules_created": len(benefit_rows),
        "comparison_ready_structure": comparison_ready_structure,
        "disclaimer": STARTER_TEMPLATE_DISCLAIMER,
        "message": (
            "Draft baseline created from the platform starter template. Customize and publish when it "
            "reflects your approved company policy."
        ),
    }

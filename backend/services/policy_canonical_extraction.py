"""
LLM-backed canonical fact extraction with legacy compatibility projection.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..app.schemas import (
    AssignmentType,
    PolicyFactCanonicalCreate,
    PolicyFactExtractionLLMInput,
    PolicyFactExtractionLLMOutput,
    PolicyFactLLMRecord,
)
from ..database import Database
from .policy_canonical_validation import validate_canonical_fact_payload, validate_canonical_fact_model
from .policy_fact_extraction_service import extract_minimal_policy_facts


def project_canonical_fact_to_legacy_fact(fact: Dict[str, Any]) -> Dict[str, Any]:
    category = str(fact.get("benefit_category") or "general")
    value_payload: Dict[str, Any] = {}
    for key in (
        "amount",
        "currency",
        "percentage",
        "quantity",
        "duration_value",
        "duration_unit",
        "value_text",
    ):
        if fact.get(key) is not None:
            value_payload[key] = fact.get(key)
    if fact.get("provider_entity"):
        value_payload["provider_entity"] = fact.get("provider_entity")
    if fact.get("frequency"):
        value_payload["frequency"] = fact.get("frequency")
    applicability = {
        "assignment_types": fact.get("assignment_types") or [],
        "eligibility": fact.get("eligibility") or {},
    }
    return {
        "fact_type": "benefit",
        "category": category,
        "subcategory": str(fact.get("phase") or "") or None,
        "normalized_value_json": value_payload,
        "applicability_json": applicability,
        "ambiguity_flag": False,
        "confidence_score": fact.get("confidence_score"),
        "source_chunk_id": fact.get("canonical_policy_document_chunk_id"),
        "source_quote": fact.get("source_quote"),
        "source_page": None,
        "source_section": fact.get("title") or category,
    }


class OpenAIPolicyCanonicalExtractor:
    def __init__(self, *, client: Any = None, model: Optional[str] = None) -> None:
        self._client = client
        self._model = model or os.getenv("OPENAI_POLICY_EXTRACTION_MODEL", "gpt-4.1-mini")

    def _client_or_raise(self) -> Any:
        if self._client is not None:
            return self._client
        from ..core.llm_flags import LLMDisabled, policy_llm_disabled
        if policy_llm_disabled():
            # RELOPASS_POLICY_LLM_DISABLED=1 — never build a client, never
            # egress. Caller must treat this as "no LLM contribution".
            return LLMDisabled
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised via tests with mock clients
            raise RuntimeError("openai package is required for canonical policy extraction") from exc
        # Explicit timeout + retries — the OpenAI SDK's defaults let a hung
        # connection block the background task indefinitely. OPENAI_TIMEOUT_SECONDS
        # and OPENAI_MAX_RETRIES are the env-var overrides for ops tuning.
        timeout_s = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
        max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=timeout_s,
            max_retries=max_retries,
        )

    def extract(self, llm_input: PolicyFactExtractionLLMInput) -> PolicyFactExtractionLLMOutput:
        from ..core.llm_flags import LLMDisabled, policy_llm_temperature
        client = self._client_or_raise()
        if client is LLMDisabled:
            # Deterministic short-circuit. Callers will typically route to
            # the fallback extractor (extract_minimal_policy_facts) and set
            # review_required=True on the document row.
            return PolicyFactExtractionLLMOutput(facts=[])
        schema_json = {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                    },
                }
            },
            "required": ["facts"],
            "additionalProperties": False,
        }
        response = client.chat.completions.create(
            model=self._model,
            temperature=policy_llm_temperature(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract relocation policy facts into strict JSON. "
                        "Return only fields supported by the schema. "
                        f"Schema: {json.dumps(schema_json)}"
                    ),
                },
                {
                    "role": "user",
                    "content": llm_input.model_dump_json(),
                },
            ],
        )
        content = response.choices[0].message.content if response.choices else "{}"
        payload = json.loads(content or "{}")
        return PolicyFactExtractionLLMOutput.model_validate(payload)


def _fallback_extract_for_chunk(chunk: Dict[str, Any]) -> List[PolicyFactLLMRecord]:
    legacy_facts = extract_minimal_policy_facts(
        [
            {
                "id": chunk["id"],
                "chunk_index": chunk.get("chunk_index"),
                "text_content": chunk.get("text_content"),
                "section_title": chunk.get("section_path"),
                "page_number": chunk.get("page_number"),
            }
        ]
    )
    out: List[PolicyFactLLMRecord] = []
    assignment_types = [
        AssignmentType(value)
        for value in (legacy_facts[0].get("applicability_json", {}).get("assignment_types") or [])
        if value in AssignmentType._value2member_map_
    ] if legacy_facts else []
    for legacy in legacy_facts:
        raw_span = str((legacy.get("normalized_value_json") or {}).get("raw_span") or "")
        payload = {
            "phase": None,
            "benefit_category": category_to_benefit(legacy.get("category")),
            "value_type": infer_value_type_from_legacy(legacy),
            "title": legacy.get("category"),
            "description": legacy.get("source_quote"),
            "assignment_types": assignment_types,
            "value_text": raw_span or None,
            "source_quote": legacy.get("source_quote"),
            "confidence_score": legacy.get("confidence_score"),
            "raw_payload": legacy,
        }
        out.append(PolicyFactLLMRecord.model_validate(payload))
    return out


def infer_value_type_from_legacy(legacy_fact: Dict[str, Any]) -> str:
    category = str(legacy_fact.get("category") or "")
    raw_span = str((legacy_fact.get("normalized_value_json") or {}).get("raw_span") or "")
    if "%" in raw_span or category == "percentage":
        return "percentage"
    if any(token in raw_span for token in ("USD", "EUR", "GBP", "$", "€", "£")):
        return "monetary"
    if legacy_fact.get("fact_type") == "duration_limit":
        return "duration"
    return "text"


def category_to_benefit(category: Any) -> Optional[str]:
    mapping = {
        "housing": "housing",
        "temporary_housing": "temporary_housing",
        "travel": "travel",
        "shipment": "shipment",
        "immigration": "immigration",
        "tax": "tax",
        "school": "schooling",
        "tuition": "schooling",
        "allowance": "allowance",
        "mobility": "mobility_premium",
        "home_leave": "home_leave",
    }
    key = str(category or "").strip().lower()
    return mapping.get(key)


def extract_canonical_policy_facts(
    db: Database,
    canonical_document_id: str,
    *,
    extractor: Optional[OpenAIPolicyCanonicalExtractor] = None,
    use_fallback: bool = False,
) -> Dict[str, Any]:
    document = db.get_canonical_policy_document(canonical_document_id)
    if not document:
        raise RuntimeError("canonical_policy_document_not_found")
    chunks = db.list_canonical_policy_document_chunks(canonical_document_id)
    if not chunks:
        raise RuntimeError("canonical_policy_document_not_chunked")

    extractor = extractor or OpenAIPolicyCanonicalExtractor()
    inserted_ids: List[str] = []
    validation_errors: List[Dict[str, Any]] = []
    legacy_projection: List[Dict[str, Any]] = []
    company_id = str(document.get("company_id") or "").strip()

    for chunk in chunks:
        if use_fallback:
            llm_records = _fallback_extract_for_chunk(chunk)
        else:
            llm_input = PolicyFactExtractionLLMInput(
                chunk_id=str(chunk["id"]),
                title=chunk.get("section_path"),
                section_path=chunk.get("section_path"),
                structure_type=chunk.get("structure_type"),
                page_number=chunk.get("page_number"),
                text_content=str(chunk.get("text_content") or ""),
                default_currency=document.get("default_currency"),
                assignment_types=[
                    AssignmentType(value)
                    for value in (document.get("assignment_types_json") or [])
                    if value in AssignmentType._value2member_map_
                ],
            )
            llm_records = extractor.extract(llm_input).facts

        for record in llm_records:
            payload = {
                "company_id": company_id,
                "canonical_policy_document_id": canonical_document_id,
                "canonical_policy_document_chunk_id": str(chunk["id"]),
                "source_policy_document_id": document.get("source_policy_document_id"),
                **record.model_dump(mode="json"),
            }
            fact_model, model_errors = validate_canonical_fact_model(payload)
            errors = model_errors if fact_model is None else validate_canonical_fact_payload(fact_model)
            if errors or fact_model is None:
                db.insert_canonical_policy_validation_error(
                    company_id=company_id,
                    canonical_policy_document_id=canonical_document_id,
                    canonical_policy_document_chunk_id=str(chunk["id"]),
                    raw_payload_json=payload,
                    errors_json=errors or model_errors,
                )
                validation_errors.append({"chunk_id": chunk["id"], "errors": errors or model_errors, "payload": payload})
                continue
            fact_payload = fact_model.model_dump(mode="json")
            fact_id = db.insert_canonical_policy_fact(
                canonical_policy_document_id=fact_payload["canonical_policy_document_id"],
                company_id=fact_payload["company_id"],
                canonical_policy_document_chunk_id=fact_payload["canonical_policy_document_chunk_id"],
                source_policy_document_id=fact_payload.get("source_policy_document_id"),
                phase=fact_payload.get("phase"),
                benefit_category=fact_payload.get("benefit_category"),
                value_type=fact_payload["value_type"],
                frequency=fact_payload.get("frequency"),
                provider_entity=fact_payload.get("provider_entity"),
                title=fact_payload.get("title"),
                description=fact_payload.get("description"),
                eligibility_json=fact_payload.get("eligibility"),
                assignment_types_json=fact_payload.get("assignment_types"),
                amount=fact_payload.get("amount"),
                currency=fact_payload.get("currency"),
                percentage=fact_payload.get("percentage"),
                quantity=fact_payload.get("quantity"),
                duration_value=fact_payload.get("duration_value"),
                duration_unit=fact_payload.get("duration_unit"),
                value_text=fact_payload.get("value_text"),
                is_taxable=fact_payload.get("is_taxable"),
                reimbursement_required=fact_payload.get("reimbursement_required"),
                source_quote=fact_payload.get("source_quote"),
                confidence_score=fact_payload.get("confidence_score"),
                raw_payload_json=fact_payload.get("raw_payload"),
            )
            inserted_ids.append(fact_id)
            legacy_projection.append(project_canonical_fact_to_legacy_fact(fact_payload))

    db.update_canonical_policy_document(
        canonical_document_id,
        extraction_status="extracted" if inserted_ids else "validated_with_errors",
    )
    return {
        "canonical_document_id": canonical_document_id,
        "facts_inserted": len(inserted_ids),
        "validation_errors": validation_errors,
        "legacy_projection": legacy_projection,
    }

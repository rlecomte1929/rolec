from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from .. import crud
from ..db import SessionLocal
from ..schemas import CaseRequirementsDTO, RequirementItemDTO, SourceRecordDTO
from .rules_engine import apply_rules


def compute_case_requirements(case_id: str) -> CaseRequirementsDTO:
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise ValueError("Case not found")

        draft = json.loads(case.draft_json)
        dest_country = case.dest_country or draft.get("relocationBasics", {}).get("destCountry") or "UNKNOWN"
        purpose = case.purpose or draft.get("relocationBasics", {}).get("purpose") or "employment"

        sources = crud.list_sources(db, dest_country.upper())
        requirements = crud.list_requirements(db, dest_country.upper(), purpose)

        base_items = [
            {
                "id": item.id,
                "pillar": item.pillar,
                "title": item.title,
                "description": item.description,
                "severity": item.severity,
                "owner": item.owner,
                "requiredFields": json.loads(item.required_fields_json),
                "citations": json.loads(item.citations_json),
            }
            for item in requirements
        ]

        required_fields, expanded, _ = apply_rules(draft, base_items)

        source_map = {record.id: record for record in sources}
        requirement_dtos: List[RequirementItemDTO] = []

        for item in expanded:
            required = item.get("requiredFields", [])
            status = _status_for_case(required, draft)
            citations = [
                _source_dto(source_map[cid])
                for cid in item.get("citations", [])
                if cid in source_map
            ]
            requirement_dtos.append(
                RequirementItemDTO(
                    id=item.get("id") or item.get("title"),
                    pillar=item.get("pillar"),
                    title=item.get("title"),
                    description=item.get("description"),
                    severity=item.get("severity"),
                    owner=item.get("owner"),
                    requiredFields=required,
                    statusForCase=status,
                    citations=citations,
                )
            )

        source_dtos = [_source_dto(record) for record in sources]

        return CaseRequirementsDTO(
            caseId=case.id,
            destCountry=dest_country,
            purpose=purpose,
            computedAt=datetime.utcnow(),
            requirements=requirement_dtos,
            sources=source_dtos,
        )


def _status_for_case(required_fields: List[str], draft: Dict[str, Any]) -> str:
    for field in required_fields:
        value = _get_nested_value(draft, field)
        if value in (None, "", [], {}):
            return "MISSING"
    return "PROVIDED" if required_fields else "NEEDS_REVIEW"


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    cursor = data
    for part in path.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return None
    return cursor


def _source_dto(record: Any) -> SourceRecordDTO:
    return SourceRecordDTO(
        id=record.id,
        url=record.url,
        title=record.title,
        publisherDomain=record.publisher_domain,
        retrievedAt=record.retrieved_at,
        snippet=record.snippet,
    )

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from .. import crud
from ..db import SessionLocal
from ..schemas import CaseRequirementsDTO, RequirementItemDTO, SourceRecordDTO
from .disclaimers import DEFAULT_VERIFICATION_STATUS, IMMIGRATION_DISCLAIMER
from .requirements_country_key import resolve_catalog_country, to_iso
from .requirements_purpose_key import (
    assignment_type_from_purpose,
    is_known_catalog_gap,
    to_purpose,
)
from .rules_engine import apply_rules

log = logging.getLogger(__name__)

# AIQ-1473 boundary (see docs/specs/requirements-engine-consolidation.md):
# this path (requirement_items) is the in-country RELOCATION DOSSIER across the
# IDENTITY / RESIDENCE / EMPLOYMENT / HOUSING / HEALTHCARE pillars, keyed by
# destination only. It is distinct-by-design from the immigration ENTRY-VISA
# checklist (immigration_requirement_service, keyed corridor × visa_type) — the
# two are documented as non-overlapping, not merged.


def _is_in_country_move(draft: Dict[str, Any], case) -> bool:
    """True when origin and destination are the same country.

    Keyed off a VERIFIABLE FACT, not off the purpose label. 53 production cases
    say `domestic` or `repatriation`, and those labels sit in a free-text field
    that has proved unreliable — but every one of them also has
    originCountry == destCountry, which is checkable. No border crossed means no
    immigration requirements, as a matter of fact rather than of trust.

    Deliberately NOT triggered by the label: a `repatriation` that genuinely does
    cross a border (returning home from abroad) must fall through to the normal
    engine. "No immigration requirements" is only true there if the destination is
    their country of nationality, and nationality is null on all of them. If we
    cannot positively know, we make no claim.
    """
    basics = draft.get("relocationBasics", {}) or {}
    origin = to_iso(getattr(case, "origin_country", None) or basics.get("originCountry"))
    dest = to_iso(getattr(case, "dest_country", None) or basics.get("destCountry"))
    return bool(origin and dest and origin == dest)


def _in_country_move(case_id: str, dest_raw: str, purpose: str) -> CaseRequirementsDTO:
    """An in-country move has no immigration requirements — and that answer must be
    STATED, not implied by an empty list.

    An empty requirements screen reads as "nothing is required of you" or, worse,
    as "we didn't check". This is the same anti-silence contract the nationality
    gate uses (rules_engine._immigration_confirmation): a correct answer of "none"
    is a positive result and gets said out loud, with its reason.

    Aligns the requirements engine with what the rest of the product already
    believes: plan_scope._SUPPRESSED["domestic_move"] = {"immigration"} and
    relocation_classifier both drop the immigration phase for these.
    """
    where = resolve_catalog_country(dest_raw)
    reason = (
        f"This is a move within {where.title()} — you are not crossing a border. "
        "No visa, residence permit or immigration registration applies."
    )
    return CaseRequirementsDTO(
        caseId=case_id,
        destCountry=where,
        purpose=purpose,
        computedAt=datetime.utcnow(),
        requirements=[
            RequirementItemDTO(
                id="immigration_not_applicable_in_country_move",
                pillar="RESIDENCE",
                title="No immigration requirements",
                description=reason,
                severity="INFO",
                owner="EMPLOYEE",
                requiredFields=[],
                statusForCase="CONFIRMED",
                citations=[],
                outcomeType="nothing_to_do",
                reason=reason,
            )
        ],
        sources=[],
        disclaimer=IMMIGRATION_DISCLAIMER,
        verificationStatus=DEFAULT_VERIFICATION_STATUS,
        staWaived=[],
        covered=True,
    )


def _not_covered(case_id: str, dest_raw: str, purpose: str) -> CaseRequirementsDTO:
    """AIQ-1473c fail-closed: the destination didn't resolve to a known catalog
    key, so we have no requirements catalogue for it. Return an explicit
    covered=False result with an empty list, rather than querying with a
    raw-upper key that yields zero rows and reads as "nothing required"."""
    return CaseRequirementsDTO(
        caseId=case_id,
        destCountry=resolve_catalog_country(dest_raw),
        purpose=purpose,
        computedAt=datetime.utcnow(),
        requirements=[],
        sources=[],
        disclaimer=IMMIGRATION_DISCLAIMER,
        verificationStatus=DEFAULT_VERIFICATION_STATUS,
        staWaived=[],
        covered=False,
    )


def compute_case_requirements(case_id: str) -> CaseRequirementsDTO:
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise ValueError("Case not found")

        draft = json.loads(case.draft_json)
        dest_raw = case.dest_country or draft.get("relocationBasics", {}).get("destCountry") or "UNKNOWN"
        purpose_raw = case.purpose or draft.get("relocationBasics", {}).get("purpose") or "employment"

        # The purpose key is matched with `==` against a catalog seeded with only
        # {employment, other, study, family}. Nothing validated the field, three
        # intakes wrote three vocabularies into it, and 616 of 780 production cases
        # (79%) matched NOTHING — returning an empty list that reads as "nothing is
        # required of you". Resolve through the single shared resolver, exactly as
        # the destination key already does (requirements_country_key).
        purpose = to_purpose(purpose_raw)

        # An in-country move crosses no border, so no immigration requirement can
        # apply. Checked BEFORE the catalog lookup and keyed off origin == dest — a
        # verifiable fact — rather than off the `domestic`/`repatriation` labels,
        # which live in the same untrustworthy field. Answered explicitly rather
        # than by an empty list.
        if _is_in_country_move(draft, case):
            return _in_country_move(case.id, dest_raw, purpose or "employment")

        # AIQ-1473c: fail closed. If the destination doesn't resolve to a known
        # ISO key (to_iso is None), we have no catalogue for it — return an
        # explicit "not covered" result instead of a misleading empty list.
        # NOTE: a destination that DOES resolve but has no rows yet is a catalog
        # gap (covered=True, empty) — a different state, deliberately not merged.
        if to_iso(dest_raw) is None:
            return _not_covered(case.id, dest_raw, purpose or purpose_raw)

        # Same fail-closed contract for the purpose half of the key: an
        # unrecognised purpose means we cannot say what is required, and we must
        # not let a zero-row lookup say "nothing".
        if purpose is None:
            return _not_covered(case.id, dest_raw, purpose_raw)

        # 272 cases store an assignment type (`lta`/`sta`/`permanent`) in the
        # purpose field while assignmentContext.assignmentType sits empty — so the
        # assignment-type gate, and every STA waiver, has never fired for them.
        # Recover it. Only when the real field is empty: never override a real value.
        recovered = assignment_type_from_purpose(purpose_raw)
        if recovered:
            assignment_ctx = draft.setdefault("assignmentContext", {})
            if not (assignment_ctx.get("assignmentType") or "").strip():
                assignment_ctx["assignmentType"] = recovered

        if is_known_catalog_gap(purpose_raw):
            # e.g. an intra-company transfer. We serve the employment track because
            # it is close and an empty list would read as "nothing required" — but
            # the ICT route is not modelled, and that is a stated approximation.
            log.info(
                "requirements: purpose %r has no modelled catalog route; serving 'employment' "
                "(known gap) for case %s",
                purpose_raw, case.id,
            )

        # AIQ-1473b: single shared resolver (ISO → catalog name).
        dest_country = resolve_catalog_country(dest_raw)

        sources = crud.list_sources(db, dest_country)
        requirements = crud.list_requirements(db, dest_country, purpose)

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
                # AIQ-1349: None ⇒ applies to all assignment types.
                "appliesToAssignmentTypes": (
                    json.loads(item.applies_to_assignment_types_json)
                    if getattr(item, "applies_to_assignment_types_json", None)
                    else None
                ),
                # None ⇒ applies to all nationality classes.
                "appliesToNationalityClasses": (
                    json.loads(item.applies_to_nationality_classes_json)
                    if getattr(item, "applies_to_nationality_classes_json", None)
                    else None
                ),
                "verificationStatus": getattr(item, "verification_status", None),
            }
            for item in requirements
        ]

        required_fields, expanded, flags = apply_rules(draft, base_items)

        source_map = {record.id: record for record in sources}
        requirement_dtos: List[RequirementItemDTO] = []

        for item in expanded:
            required = item.get("requiredFields", [])
            outcome_type = item.get("outcomeType") or "action"
            # A 'nothing_to_do' item asks nothing of anyone, so the MISSING /
            # PROVIDED / NEEDS_REVIEW ladder doesn't apply — running it through
            # _status_for_case would mark a positive confirmation NEEDS_REVIEW.
            status = "CONFIRMED" if outcome_type == "nothing_to_do" else _status_for_case(required, draft)
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
                    verificationStatus=item.get("verificationStatus"),
                    outcomeType=outcome_type,
                    reason=item.get("reason"),
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
            disclaimer=IMMIGRATION_DISCLAIMER,  # AIQ-1349: recommend, not liable
            verificationStatus=DEFAULT_VERIFICATION_STATUS,
            # AIQ-1349: titles of requirements suppressed for a short-term (STA)
            # assignment, so the UI can explain the shorter list instead of
            # silently dropping items. Empty for LTA/PERMANENT.
            staWaived=sorted({t for t in (flags.get("staWaived") or []) if t}),
            # Same contract as staWaived, for the nationality gate: the titles we
            # suppressed because the person's nationality class doesn't need them,
            # plus the class we resolved. Without these the client gets a shorter
            # list with no way to explain it — which is the silent-drop failure the
            # gate exists to prevent. Empty/None when nationality is unknown.
            nationalityWaived=sorted({t for t in (flags.get("nationalityWaived") or []) if t}),
            nationalityClass=flags.get("nationalityClass"),
            covered=True,  # AIQ-1473c: destination resolved to a known catalog key
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

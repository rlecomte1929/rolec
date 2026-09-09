from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from .. import crud
from ..db import SessionLocal
from ..schemas import CaseRequirementsDTO, RequirementItemDTO, SourceRecordDTO
from . import lawyer_review_gate
from .disclaimers import DEFAULT_VERIFICATION_STATUS, IMMIGRATION_DISCLAIMER
from .knowledge_layer_scorecard import NOT_READY_EMPTY, score_requirement_rows
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


def _canonical_route_fallback(db, case_id: str):
    """(origin, dest) ISO codes from `relocation_cases`, or (None, None).

    [AIQ-1902] `crud.get_case` reads `wizard_cases` only. A case can be fully
    populated in `relocation_cases` — the canonical, HR-facing table — and hold an
    EMPTY `wizard_cases` row, in which case the destination resolved to "UNKNOWN" and
    every requirement lookup fail-closed to `_not_covered`. Measured in production
    2026-08-17 on case 6ecadafe-0fdb-43c5-b8dc-0284e323cf51 (Andrea, ES→IE):
    `wizard_cases.dest_country` empty and `draft_json` `{"relocationBasics": {}, …}`,
    while `relocation_cases.dest_country_code = 'IE'` and IRELAND has 14 approved
    requirement_items. The HR cockpit showed "No permit mapping for this destination"
    on a case whose destination is plainly known.

    This only ADDS a source; it is consulted after the wizard row and the draft, and a
    case with nothing in either table still fail-closes exactly as before.

    Raw SQL because there is no ORM model for `relocation_cases` — the same shape
    `roadmap_entitlement.lookup_entitlement` uses. A DB error is not an answer, so it
    is logged and treated as "no fallback available" rather than as "no destination".
    """
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    cid = (case_id or "").strip()
    if not cid:
        return (None, None)
    try:
        row = db.execute(
            # CAST(... AS TEXT), not the `id::text` shorthand used elsewhere: that is
            # Postgres-only syntax and the backend test lane runs on SQLite, so the
            # shorthand would make this path untestable there (and silently so — the
            # except below would swallow the OperationalError as "no fallback").
            text(
                "SELECT origin_country_code, dest_country_code "
                "FROM relocation_cases WHERE CAST(id AS TEXT) = :cid LIMIT 1"
            ),
            {"cid": cid},
        ).mappings().first()
    except SQLAlchemyError:
        log.warning("requirements_builder: relocation_cases fallback failed for case %s", cid)
        return (None, None)
    if not row:
        return (None, None)
    return (
        (row.get("origin_country_code") or None),
        (row.get("dest_country_code") or None),
    )


def _is_in_country_move(
    draft: Dict[str, Any], case, *, origin_override=None, dest_override=None
) -> bool:
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
    # The overrides are the [AIQ-1902] relocation_cases fallback, applied LAST so the
    # wizard row and the draft keep precedence and existing callers are unaffected.
    origin = to_iso(
        getattr(case, "origin_country", None) or basics.get("originCountry") or origin_override
    )
    dest = to_iso(
        getattr(case, "dest_country", None) or basics.get("destCountry") or dest_override
    )
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
    # Precise about what is waived. No border is crossed, so nothing IMMIGRATION-related
    # applies — but a domestic move usually still means re-registering your address with
    # the local authority (an Anmeldung is required again when moving Berlin -> Munich).
    # Claiming "no registration applies" would trade one wrong answer for another.
    reason = (
        f"This is a move within {where.title()} — you are not crossing a border, so no "
        "visa, residence permit or immigration process applies. You may still need to "
        "update your address with the local authority."
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
        catalogReady=True,
        catalogNotReadyReason=None,
    )


def _not_covered(
    case_id: str,
    dest_raw: str,
    purpose: str,
    *,
    catalog_not_ready_reason: Optional[str] = None,
) -> CaseRequirementsDTO:
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
        catalogReady=False,
        catalogNotReadyReason=catalog_not_ready_reason or NOT_READY_EMPTY,
    )


def compute_case_requirements(case_id: str) -> CaseRequirementsDTO:
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise ValueError("Case not found")

        draft = json.loads(case.draft_json)
        _basics = draft.get("relocationBasics", {}) or {}
        dest_raw = case.dest_country or _basics.get("destCountry")
        origin_raw = case.origin_country or _basics.get("originCountry")

        # [AIQ-1902] Last resort: the canonical `relocation_cases` row. A case whose
        # wizard row is empty still has its route recorded there, and without this the
        # destination resolved to "UNKNOWN" and the whole dossier fail-closed — the HR
        # cockpit's "No permit mapping for this destination". Only consulted when the
        # wizard row and the draft both came up empty, so precedence is unchanged.
        if not dest_raw:
            fallback_origin, fallback_dest = _canonical_route_fallback(db, case.id)
            dest_raw = dest_raw or fallback_dest
            origin_raw = origin_raw or fallback_origin

        dest_raw = dest_raw or "UNKNOWN"
        purpose_raw = case.purpose or _basics.get("purpose") or "employment"

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
        if _is_in_country_move(
            draft, case, origin_override=origin_raw, dest_override=dest_raw
        ):
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
        #
        # Check BOTH the column and the draft. `purpose_raw` prefers the column, and
        # the column is now canonicalised on write (`sta` -> `employment`) — so for a
        # freshly written case the assignment signal survives ONLY in the draft.
        # Reading the column alone silently dropped every STA waiver on new cases;
        # caught by live verification, not by the unit tests, because the unit tests
        # never went through the write path.
        recovered = assignment_type_from_purpose(purpose_raw) or assignment_type_from_purpose(
            (draft.get("relocationBasics", {}) or {}).get("purpose")
        )
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
        source_map = {record.id: record for record in sources}
        catalog_rows = crud.list_requirements(
            db, dest_country, purpose, include_unapproved=True
        )
        requirements = [row for row in catalog_rows if (row.review_status or "approved") == "approved"]
        scorecard = score_requirement_rows(catalog_rows, source_map)

        # AN EMPTY LIST MUST NEVER MAKE A CLAIM.
        #
        # This used to be a third state: the destination IS catalogued but has no rows
        # for this purpose ("a catalog gap — covered=True, empty, deliberately not
        # merged"). The client then had an empty requirements array with covered=True
        # and rendered "No destination requirements apply to your case."
        #
        # For GERMANY + employment — 372 production cases, the single biggest corridor
        # — that was flatly false. Germany was seeded `[other]` only, so every
        # employment relocation there found zero rows and was told nothing was required
        # of them.
        #
        # From the employee's side, "we have no catalogue for your country" and "we have
        # no catalogue for your country and purpose" are the same fact: WE CANNOT TELL
        # YOU WHAT YOU NEED. The distinction was diagnostic, and keeping it split is what
        # produced the lie. Fail closed, as the destination half already does.
        #
        # Note this cannot swallow a legitimate "nothing required": the only case where
        # that is true is an in-country move, which short-circuits above and returns a
        # STATED confirmation — a non-empty list.
        if not requirements:
            log.warning(
                "requirements: catalog gap — no rows for (%s, %s); returning covered=False "
                "for case %s rather than an empty list that reads as 'nothing required'",
                dest_country, purpose, case.id,
            )
            return _not_covered(
                case.id,
                dest_raw,
                purpose,
                catalog_not_ready_reason=scorecard.not_ready_reason,
            )

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
                # Served-with-a-caveat: flagged needs_lawyer_review AND not attested.
                "legalReviewPending": lawyer_review_gate.legal_review_pending(
                    attestation_status=getattr(item, "attestation_status", None),
                    blobs=(
                        getattr(item, "required_fields_json", None),
                        getattr(item, "citations_json", None),
                        getattr(item, "applies_to_assignment_types_json", None),
                        getattr(item, "applies_to_nationality_classes_json", None),
                    ),
                ),
                # getattr-defaulted like its neighbours: test_public_corridor.py feeds
                # SimpleNamespace rows that carry none of these columns.
                "attestationStatus": getattr(item, "attestation_status", None),
                "attestedBy": getattr(item, "attested_by", None),
                "attestedAt": getattr(item, "attested_at", None),
                # getattr-defaulted so a row read before the migration lands degrades to
                # false/None instead of raising. apply_rules carries both through opaquely.
                "nonObvious": bool(getattr(item, "non_obvious", False)),
                "timing": getattr(item, "timing", None),
            }
            for item in requirements
        ]

        required_fields, expanded, flags = apply_rules(draft, base_items)

        requirement_dtos: List[RequirementItemDTO] = []

        for item in expanded:
            required = item.get("requiredFields", [])
            outcome_type = item.get("outcomeType") or "action"
            # A 'nothing_to_do' item asks nothing of anyone, so the MISSING /
            # PROVIDED / NEEDS_REVIEW ladder doesn't apply — running it through
            # _status_for_case would mark a positive confirmation NEEDS_REVIEW.
            status = "CONFIRMED" if outcome_type == "nothing_to_do" else _status_for_case(required, draft)
            citations = _citation_dtos(item.get("citations", []), source_map)
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
                    legalReviewPending=item.get("legalReviewPending"),
        attestationStatus=item.get("attestationStatus"),
        attestedBy=item.get("attestedBy"),
        attestedAt=item.get("attestedAt"),
                    nonObvious=item.get("nonObvious"),
                    timing=item.get("timing"),
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
            catalogReady=scorecard.catalog_ready,
            catalogNotReadyReason=scorecard.not_ready_reason,
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


def _is_web_url(value: str) -> bool:
    """Only `http`/`https` may reach an `href`.

    Both callers render this straight into `<a href=...>` — `Citations.tsx` for the employee and
    `CountryDetail.tsx` for the reviewer — so a `javascript:` scheme here is a click away from
    executing in either. The string branch has always required a web scheme; the dict branch,
    added when the reader learned the inline-object shape, did not, and passed
    `javascript:alert(document.cookie)` through untouched. Citation objects come from research
    NDJSON and generator scripts, which is machine-authored input we do not control the contents
    of, so the shape of the citation must not decide whether the scheme is checked.

    A rejected citation is not silently gone: the review surface lists it as an unresolved
    source, unlinked, which is what a reviewer needs to see before publishing the row.
    """
    return value.lower().startswith(("http://", "https://"))


def citation_dtos(citations: Any, source_map: Dict[str, Any]) -> List[SourceRecordDTO]:
    """Resolve a row's `citations_json` into DTOs, across the three shapes prod holds.

    `citations_json` is not one format, and treating it as one silently cost real citations:

    - **`source_records` id** — the original design, resolvable through `source_map`.
    - **bare URL string** — what `otto.executor.promote()` writes (`mappings.py`, a plain
      `json.dumps([source_url, ...])`).
    - **inline object** — what the corridor generators write
      (`scripts/gen_ie_es_corridor_load.py`), carrying `url`/`name` and, for a flagged claim,
      `needs_lawyer_review`.

    This used to be `[_source_dto(source_map[cid]) for cid in citations if cid in source_map]`,
    which had two failure modes. A bare URL is not a key in `source_map`, so it was **dropped**
    — the requirement served with an empty citation list while
    `check_requirement_provenance.py` still passed, because that guard only asserts
    `citations_json IS NOT NULL`. And a dict is unhashable, so `cid in source_map` raised
    `TypeError: unhashable type: 'dict'` — the 25 IE→ES rows carrying inline objects have
    simply never been served (all `review_status='pending'`), so the crash stayed latent.

    Anything unrecognised is skipped rather than guessed at. `retrievedAt` is left None for
    everything but a real `source_records` row — see the note on `SourceRecordDTO`.
    """
    resolved: List[SourceRecordDTO] = []
    for citation in citations or []:
        if isinstance(citation, str):
            if citation in source_map:
                resolved.append(_source_dto(source_map[citation]))
                continue
            url = citation.strip()
            if not _is_web_url(url):
                # Neither a known id nor a URL — an unresolvable reference, not a source.
                continue
            resolved.append(_inline_source_dto(url, None))
        elif isinstance(citation, dict):
            url = str(citation.get("url") or "").strip()
            if not _is_web_url(url):
                continue
            resolved.append(_inline_source_dto(url, citation.get("name")))
    return resolved


#: Public since the admin review surface needs the same resolution (`routers/admin.py`). The
#: underscored name stays so the existing importers keep working.
_citation_dtos = citation_dtos


def _inline_source_dto(url: str, name: Optional[str]) -> SourceRecordDTO:
    """A citation we hold as a URL rather than a retrieved `source_records` row.

    `id` is the URL itself: it is stable, and the client uses it as a list key. No
    `retrievedAt` — nobody retrieved it.
    """
    domain = urlsplit(url).hostname or ""
    return SourceRecordDTO(
        id=url,
        url=url,
        title=(str(name).strip() if name else "") or domain or url,
        publisherDomain=domain,
        retrievedAt=None,
    )

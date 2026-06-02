"""Policy-gap detector I/O layer (C2-06-FOLLOWUP).

Wraps the SDK-free ``backend.relopass.policy_evidence`` detector with the
Supabase/SQLAlchemy I/O it deliberately omits. Responsibilities:

  * ``sync_documents_to_artefacts`` / ``sync_costs_to_artefacts`` — mirror
    document- and cost-backed artefacts into ``rce.case_artefacts`` (the
    canonical store the detector reads). Idempotent: a no-op re-run writes
    zero rows (ON CONFLICT ... WHERE ... IS DISTINCT FROM).
  * ``hydrate_case`` — project ``rce.cases`` + family + artefacts into the
    detector's ``Case`` value type.
  * ``load_applicable_clauses`` — the employer's effective policy clauses.
  * ``detect_and_persist`` — run the detector, diff against open
    ``rce.policy_gaps`` by dedup key, INSERT new + clear resolved in one
    transaction. Idempotent: a second consecutive run performs no writes.

This module lives in ``backend/app/services/`` per the C2-06-FOLLOWUP
technical constraint — ``backend/relopass/*`` stays SDK-free. Detection logic
is NOT reimplemented here; ``detect_gaps`` is the single source of truth.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..db import engine
from backend.relopass.policy_evidence import (
    Artefact,
    Case,
    FamilyMember,
    Gap,
    PolicyClause,
    detect_gaps,
)

# Canonical mappings for the document/cost mirror (AIQ-568 DECISION block).
HOUSING_LEASE_DOC_CODE = "HOUSING_LEASE"
HOUSING_VENDOR_COST_CATEGORY = "HOUSING_VENDOR"

# subject_kind sentinel used in dedup keys for non-family (CASE/EMPLOYEE) subjects.
_NO_FAMILY_MEMBER = "CASE"


class CaseNotFoundError(Exception):
    """Raised by hydrate_case when the case_id has no rce.cases row."""


@dataclass
class GapDiff:
    """Outcome of a detect_and_persist run, for the caller's audit trail."""

    inserted: List[Gap] = field(default_factory=list)
    cleared_gap_ids: List[str] = field(default_factory=list)
    unchanged: int = 0
    documents_synced: int = 0
    costs_synced: int = 0

    @property
    def wrote_anything(self) -> bool:
        return bool(
            self.inserted
            or self.cleared_gap_ids
            or self.documents_synced
            or self.costs_synced
        )


# ─────────────────────────────────────────────────────────────────────────────
# Projection helpers
# ─────────────────────────────────────────────────────────────────────────────


def _display_name(canonical_form: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not canonical_form:
        return None
    form = canonical_form if isinstance(canonical_form, Mapping) else {}
    name = form.get("display_name") or form.get("full_name")
    if name:
        return str(name)
    given = form.get("given_names")
    if isinstance(given, (list, tuple)):
        given = " ".join(str(g) for g in given)
    surname = form.get("normalized_surname") or form.get("surname")
    joined = " ".join(p for p in (given, surname) if p)
    return joined or None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


# ─────────────────────────────────────────────────────────────────────────────
# Sync helpers — mirror canonical-home rows into rce.case_artefacts
# ─────────────────────────────────────────────────────────────────────────────


def sync_documents_to_artefacts(case_id: uuid.UUID, conn: Connection) -> int:
    """Mirror HOUSING_LEASE documents into rce.case_artefacts. Returns rows written."""
    rows = conn.execute(
        text(
            """
            SELECT d.document_id, d.original_filename, d.storage_uri, d.created_at
            FROM rce.documents d
            JOIN rce.document_types dt ON dt.document_type_id = d.document_type_id
            WHERE d.case_id = :cid AND dt.code = :code
            """
        ),
        {"cid": str(case_id), "code": HOUSING_LEASE_DOC_CODE},
    ).mappings().all()

    written = 0
    for r in rows:
        payload = {
            "original_filename": r.get("original_filename"),
            "storage_uri": r.get("storage_uri"),
        }
        result = conn.execute(
            text(
                """
                INSERT INTO rce.case_artefacts
                  (case_id, kind, subject_kind, payload, delivered_at, source_document_id)
                VALUES
                  (:cid, 'housing_lease_document', 'CASE', CAST(:payload AS jsonb),
                   :delivered_at, :doc)
                ON CONFLICT (source_document_id) DO UPDATE
                  SET payload = EXCLUDED.payload,
                      delivered_at = EXCLUDED.delivered_at,
                      updated_at = now()
                  WHERE rce.case_artefacts.payload IS DISTINCT FROM EXCLUDED.payload
                     OR rce.case_artefacts.delivered_at IS DISTINCT FROM EXCLUDED.delivered_at
                """
            ),
            {
                "cid": str(case_id),
                "payload": json.dumps(payload),
                "delivered_at": r.get("created_at"),
                "doc": str(r["document_id"]),
            },
        )
        written += result.rowcount or 0
    return written


def sync_costs_to_artefacts(case_id: uuid.UUID, conn: Connection) -> int:
    """Mirror HOUSING_VENDOR costs into rce.case_artefacts as housing_invoice."""
    rows = conn.execute(
        text(
            """
            SELECT cost_id, amount, currency, created_at
            FROM rce.costs
            WHERE case_id = :cid AND category = :cat
            """
        ),
        {"cid": str(case_id), "cat": HOUSING_VENDOR_COST_CATEGORY},
    ).mappings().all()

    written = 0
    for r in rows:
        result = conn.execute(
            text(
                """
                INSERT INTO rce.case_artefacts
                  (case_id, kind, subject_kind, magnitude, unit, delivered_at, source_cost_id)
                VALUES
                  (:cid, 'housing_invoice', 'CASE', :magnitude, :unit, :delivered_at, :cost)
                ON CONFLICT (source_cost_id) DO UPDATE
                  SET magnitude = EXCLUDED.magnitude,
                      unit = EXCLUDED.unit,
                      delivered_at = EXCLUDED.delivered_at,
                      updated_at = now()
                  WHERE rce.case_artefacts.magnitude IS DISTINCT FROM EXCLUDED.magnitude
                     OR rce.case_artefacts.unit IS DISTINCT FROM EXCLUDED.unit
                     OR rce.case_artefacts.delivered_at IS DISTINCT FROM EXCLUDED.delivered_at
                """
            ),
            {
                "cid": str(case_id),
                "magnitude": r.get("amount"),
                "unit": r.get("currency"),
                "delivered_at": r.get("created_at"),
                "cost": str(r["cost_id"]),
            },
        )
        written += result.rowcount or 0
    return written


# ─────────────────────────────────────────────────────────────────────────────
# Hydration
# ─────────────────────────────────────────────────────────────────────────────


def hydrate_case(case_id: uuid.UUID, conn: Connection) -> Case:
    """Project rce.cases (+ employee, family, artefacts) into a detector Case."""
    case_row = conn.execute(
        text(
            """
            SELECT c.case_id, c.employer_id, c.primary_employee_id, c.target_arrival_date,
                   e.canonical_entity_id AS emp_canonical_id,
                   ce.canonical_form AS emp_canonical_form
            FROM rce.cases c
            LEFT JOIN rce.employees e ON e.employee_id = c.primary_employee_id
            LEFT JOIN rce.canonical_entities ce ON ce.canonical_entity_id = e.canonical_entity_id
            WHERE c.case_id = :cid
            """
        ),
        {"cid": str(case_id)},
    ).mappings().one_or_none()
    if case_row is None:
        raise CaseNotFoundError(str(case_id))

    family_rows = conn.execute(
        text(
            """
            SELECT fm.family_member_id, fm.relationship_type, fm.canonical_entity_id,
                   ce.canonical_form AS canonical_form
            FROM rce.family_members fm
            LEFT JOIN rce.canonical_entities ce ON ce.canonical_entity_id = fm.canonical_entity_id
            WHERE fm.case_id = :cid
            ORDER BY fm.created_at ASC
            """
        ),
        {"cid": str(case_id)},
    ).mappings().all()

    artefact_rows = conn.execute(
        text(
            """
            SELECT artefact_id, kind, subject_kind, family_member_id,
                   payload, magnitude, unit, delivered_at
            FROM rce.case_artefacts
            WHERE case_id = :cid
            """
        ),
        {"cid": str(case_id)},
    ).mappings().all()

    family_members = tuple(
        FamilyMember(
            family_member_id=r["family_member_id"],
            relationship_type=str(r["relationship_type"]),
            canonical_entity_id=r.get("canonical_entity_id"),
            display_name=_display_name(r.get("canonical_form")),
        )
        for r in family_rows
    )

    artefacts = tuple(
        Artefact(
            artefact_id=r["artefact_id"],
            kind=str(r["kind"]),
            subject_kind=str(r["subject_kind"]),
            family_member_id=r.get("family_member_id"),
            payload=r.get("payload") or {},
            magnitude=_as_float(r.get("magnitude")),
            unit=r.get("unit"),
            delivered_at=r.get("delivered_at"),
        )
        for r in artefact_rows
    )

    target_arrival = case_row.get("target_arrival_date")
    return Case(
        case_id=case_row["case_id"],
        employer_id=case_row["employer_id"],
        primary_employee_id=case_row["primary_employee_id"],
        primary_employee_canonical_id=case_row.get("emp_canonical_id"),
        primary_employee_display_name=_display_name(case_row.get("emp_canonical_form")),
        target_arrival_date=target_arrival.isoformat()
        if isinstance(target_arrival, (datetime,)) or hasattr(target_arrival, "isoformat")
        else target_arrival,
        family_members=family_members,
        artefacts=artefacts,
    )


def load_applicable_clauses(
    employer_id: uuid.UUID, conn: Connection
) -> Tuple[PolicyClause, ...]:
    """Effective policy clauses for the employer (per AIQ-568 sketch)."""
    rows = conn.execute(
        text(
            """
            SELECT pc.policy_clause_id, pc.hr_policy_id, pc.clause_type,
                   pc.parameters_json, pc.bbox_citation
            FROM rce.policy_clauses pc
            JOIN rce.hr_policies hp ON hp.hr_policy_id = pc.hr_policy_id
            WHERE hp.employer_id = :eid AND hp.effective_from <= now()
            """
        ),
        {"eid": str(employer_id)},
    ).mappings().all()
    return tuple(
        PolicyClause(
            policy_clause_id=r["policy_clause_id"],
            hr_policy_id=r["hr_policy_id"],
            clause_type=str(r["clause_type"]),
            parameters_json=r.get("parameters_json") or {},
            bbox_citation=r.get("bbox_citation"),
        )
        for r in rows
    )


# ─────────────────────────────────────────────────────────────────────────────
# Diff + persist
# ─────────────────────────────────────────────────────────────────────────────


def _norm_key(
    case_id: Any, policy_clause_id: Any, gap_type: str, family_member_id: Any
) -> str:
    subj = str(family_member_id) if family_member_id else _NO_FAMILY_MEMBER
    return f"{case_id}|{policy_clause_id}|{gap_type}|{subj}"


def _load_open_gaps(case_id: uuid.UUID, conn: Connection) -> Dict[str, Dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT gap_id, policy_clause_id, gap_type, family_member_id
            FROM rce.policy_gaps
            WHERE case_id = :cid AND cleared_at IS NULL
            """
        ),
        {"cid": str(case_id)},
    ).mappings().all()
    return {
        _norm_key(case_id, r["policy_clause_id"], r["gap_type"], r.get("family_member_id")): dict(r)
        for r in rows
    }


def _persist_diff(
    case_id: uuid.UUID,
    detected: Tuple[Gap, ...],
    existing: Dict[str, Dict[str, Any]],
    conn: Connection,
) -> GapDiff:
    diff = GapDiff()
    detected_keys = set()

    for gap in detected:
        key = _norm_key(
            case_id, gap.policy_clause_id, gap.gap_type, gap.subject.family_member_id
        )
        detected_keys.add(key)
        if key in existing:
            diff.unchanged += 1
            continue
        conn.execute(
            text(
                """
                INSERT INTO rce.policy_gaps
                  (case_id, policy_clause_id, clause_type, family_member_id,
                   subject_kind, gap_type, suggested_action, evidence_payload, citation)
                VALUES
                  (:cid, :clause_id, :clause_type, :fm_id, :subject_kind, :gap_type,
                   :suggested_action, NULL, CAST(:citation AS jsonb))
                """
            ),
            {
                "cid": str(case_id),
                "clause_id": str(gap.policy_clause_id),
                "clause_type": gap.clause_type,
                "fm_id": str(gap.subject.family_member_id)
                if gap.subject.family_member_id
                else None,
                "subject_kind": gap.subject.kind,
                "gap_type": gap.gap_type,
                "suggested_action": gap.suggested_action,
                "citation": json.dumps(gap.citation) if gap.citation is not None else None,
            },
        )
        diff.inserted.append(gap)

    for key, row in existing.items():
        if key in detected_keys:
            continue
        conn.execute(
            text(
                """
                UPDATE rce.policy_gaps
                SET cleared_at = now(), updated_at = now()
                WHERE gap_id = :gid
                """
            ),
            {"gid": str(row["gap_id"])},
        )
        diff.cleared_gap_ids.append(str(row["gap_id"]))

    return diff


def case_ids_for_employer(employer_id: uuid.UUID, conn: Connection) -> List[str]:
    """All case_ids under an employer — fan-out target for policy.published."""
    rows = conn.execute(
        text("SELECT case_id FROM rce.cases WHERE employer_id = :eid"),
        {"eid": str(employer_id)},
    ).all()
    return [str(r[0]) for r in rows]


def detect_and_persist(
    case_id: uuid.UUID, conn: Optional[Connection] = None
) -> GapDiff:
    """Sync artefacts, run the detector, and reconcile rce.policy_gaps.

    Idempotent: a second consecutive run performs zero writes. When ``conn``
    is provided the caller owns the transaction (used by tests); otherwise a
    connection + transaction are opened and committed here.
    """
    if conn is not None:
        return _run(case_id, conn)

    with engine.begin() as owned_conn:
        return _run(case_id, owned_conn)


def _run(case_id: uuid.UUID, conn: Connection) -> GapDiff:
    docs = sync_documents_to_artefacts(case_id, conn)
    costs = sync_costs_to_artefacts(case_id, conn)
    case = hydrate_case(case_id, conn)
    clauses = load_applicable_clauses(case.employer_id, conn)
    detected = detect_gaps(case, clauses)
    existing = _load_open_gaps(case_id, conn)
    diff = _persist_diff(case_id, detected, existing, conn)
    diff.documents_synced = docs
    diff.costs_synced = costs
    return diff

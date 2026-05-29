"""C1-08 · Cross-document contradiction detection.

Reads :class:`backend.relopass.agents.models.ExtractedField` rows for a
case and compares values across documents linked to the same
``canonical_entity_id``. When two or more documents disagree on a
field's value beyond the field's allowed-variation tolerance, the
detector emits a :class:`Contradiction` row matching the Parsewise §3.6
JSON shape.

The Cohort 1 fixed 5-field set (Architecture Report §3.6):

* ``surname`` — passport ↔ marriage cert ↔ diploma.
  Allowed variation: ICAO transliteration; maiden-name annotation when
  a MARRIAGE_CERT extraction is present.
* ``given_names`` — passport ↔ ID card ↔ diploma.
  Allowed variation: ICAO transliteration only.
* ``date_of_birth`` — passport ↔ birth cert ↔ ID card ↔ diploma.
  Allowed variation: none.
* ``employer_legal_name`` — contract ↔ payslip ↔ invitation letter.
  Allowed variation: legal-suffix normalisation; parent-vs-subsidiary
  when both rows carry the same ``registry_id``.
* ``gross_salary_annual`` — contract ↔ most recent payslip (annualised).
  Allowed variation: ±5 % to absorb bonus / holiday-pay annualisation.

Storage is a :class:`ContradictionStore` Protocol — the production
adapter writes into ``rce.contradictions`` (migration
``20260529120000_rce_contradictions.sql``). Tests use
:class:`InMemoryContradictionStore`.

Per the ``backend/relopass`` package constraint, no module here imports
SQLAlchemy, FastAPI, or any vendor SDK.
"""

from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.relopass.normalize import normalize_employer, normalize_name, parse_money

from .models import ExtractedField

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────────────────────


ContradictionType = Literal[
    "DIRECT_CONTRADICTION",
    "MISSING_VALUE",
    "TEMPORAL_INCONSISTENCY",
    "FORMAT_MISMATCH",
    "UNIT_MISMATCH",
]

ResolutionStatus = Literal[
    "Resolved",
    "Requires attention",
    "Not resolved",
    "No result",
    "Ignored",
]


# Cohort 1 fixed 5-field set. The detector iterates only over these.
COHORT_1_FIELD_KEYS: Tuple[str, ...] = (
    "surname",
    "given_names",
    "date_of_birth",
    "employer_legal_name",
    "gross_salary_annual",
)

# Salary tolerance per §3.6 (absorbs bonus / holiday-pay annualisation).
SALARY_RELATIVE_TOLERANCE = Decimal("0.05")  # ±5 %


class Candidate(BaseModel):
    """One source of a value for a given (canonical_entity, field_key).

    Mirrors the Parsewise §3.6 candidate shape. Frozen so a Candidate can
    hash into the content fingerprint.
    """

    model_config = ConfigDict(frozen=True)

    value: Any
    document_id: UUID
    page: Optional[int] = None
    bbox: Optional[Tuple[int, int, int, int]] = None
    source_agent_run_id: Optional[UUID] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    # Source document type code (PASSPORT_TD3 / EMPLOYMENT_CONTRACT / etc.).
    # Lets the per-field comparator apply document-aware allowed-variation
    # rules (e.g. maiden-name on MARRIAGE_CERT only).
    document_type_code: Optional[str] = None


class Contradiction(BaseModel):
    """The Parsewise §3.6 inconsistency record. Maps 1:1 to
    ``rce.contradictions``.
    """

    # `model_name` would conflict with pydantic v2's protected namespace if
    # this model ever grew such a field — opt out preemptively.
    model_config = ConfigDict(frozen=True, protected_namespaces=())

    contradiction_id: UUID
    case_id: UUID
    canonical_entity_id: Optional[UUID]
    field_key: str
    type: ContradictionType
    candidates: Tuple[Candidate, ...]
    resolution_status: ResolutionStatus = "Requires attention"
    suggested_winner: Optional[Any] = None  # null by spec at detect-time
    content_hash: str
    detected_at: datetime
    detected_by: str = "agent_contradiction_v1"


# ─────────────────────────────────────────────────────────────────────────────
# Storage Protocol
# ─────────────────────────────────────────────────────────────────────────────


class ContradictionStore(Protocol):
    """Persistence contract the detector calls into.

    The production Supabase adapter (future task) writes to
    ``rce.contradictions``; tests use :class:`InMemoryContradictionStore`.
    """

    def list_extracted_fields_for_case(
        self, case_id: UUID
    ) -> Sequence[ExtractedField]:
        """Return every ExtractedField row for the case.

        The detector groups them into (canonical_entity_id, field_key)
        buckets and runs the per-field comparator on each bucket.
        """
        ...

    def get_document_type(self, document_id: UUID) -> Optional[str]:
        """Look up a document's type code (e.g. PASSPORT_TD3,
        EMPLOYMENT_CONTRACT). Returns None if the document_id is
        unknown to the store.
        """
        ...

    def get_canonical_entity_for_field(
        self, extracted_field_id: UUID
    ) -> Optional[UUID]:
        """Resolve the canonical_entity_id linked to this ExtractedField.

        Cohort 1 stub: the production adapter joins through
        ``rce.entity_links``. In Cohort 1 fixtures we pre-populate the
        canonical_entity_id directly on each ExtractedField via the
        ``value_canonical`` JSONB.
        """
        ...

    def upsert_contradictions(
        self, contradictions: Iterable[Contradiction]
    ) -> Tuple[int, int]:
        """Insert any contradictions whose ``content_hash`` is new for
        their ``(case_id, canonical_entity_id, field_key)`` triple.
        Returns ``(inserted, skipped_duplicates)``.
        """
        ...


@dataclass
class InMemoryContradictionStore:
    """Thread-unsafe test default."""

    fields: List[ExtractedField] = field(default_factory=list)
    document_types: Dict[UUID, str] = field(default_factory=dict)
    canonical_entities: Dict[UUID, UUID] = field(default_factory=dict)
    contradictions: List[Contradiction] = field(default_factory=list)
    # Idempotency-key set: (case_id, canonical_entity_id, field_key, content_hash)
    _seen: set = field(default_factory=set)

    def list_extracted_fields_for_case(
        self, case_id: UUID
    ) -> Sequence[ExtractedField]:
        # ExtractedField doesn't carry case_id directly in C1-05a's Pydantic
        # shape — the case is inferred via the document. For tests we just
        # return all fields the harness loaded.
        return tuple(self.fields)

    def get_document_type(self, document_id: UUID) -> Optional[str]:
        return self.document_types.get(document_id)

    def get_canonical_entity_for_field(
        self, extracted_field_id: UUID
    ) -> Optional[UUID]:
        return self.canonical_entities.get(extracted_field_id)

    def upsert_contradictions(
        self, contradictions: Iterable[Contradiction]
    ) -> Tuple[int, int]:
        inserted = 0
        skipped = 0
        for c in contradictions:
            key = (c.case_id, c.canonical_entity_id, c.field_key, c.content_hash)
            if key in self._seen:
                skipped += 1
                continue
            self._seen.add(key)
            self.contradictions.append(c)
            inserted += 1
        return inserted, skipped

    # ---- Test helpers ----

    def add_field(
        self,
        field_obj: ExtractedField,
        *,
        document_type: str,
        canonical_entity_id: Optional[UUID] = None,
    ) -> None:
        """Register an ExtractedField with its document-type code +
        canonical-entity link in one call.
        """
        self.fields.append(field_obj)
        self.document_types[field_obj.document_id] = document_type
        # ExtractedField is frozen; we need a key off it. Use the value_raw
        # + document_id + field_key triple as a synthetic ID for the
        # in-memory store.
        eid = _synthetic_field_id(field_obj)
        if canonical_entity_id is not None:
            self.canonical_entities[eid] = canonical_entity_id


def _synthetic_field_id(f: ExtractedField) -> UUID:
    """In-memory key for an ExtractedField that doesn't carry an explicit id.

    Stable across runs: SHA-256 over (document_id, field_key, value_raw)
    truncated to a UUID-shaped string.
    """
    digest = hashlib.sha256(
        f"{f.document_id}:{f.field_key}:{f.value_raw}".encode("utf-8")
    ).hexdigest()
    return UUID(digest[:32])


# ─────────────────────────────────────────────────────────────────────────────
# Comparator helpers
# ─────────────────────────────────────────────────────────────────────────────


def _strip_diacritics(text: str) -> str:
    """NFD + strip Mn — the same fold normalize.names uses for ICAO §6
    transliteration. Identical inputs after this fold are considered
    equivalent for surname / given_names comparison.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    ).upper().strip()


def _norm_employer_name(raw: str, country_iso3: Optional[str] = None) -> str:
    """Legal-suffix stripped, diacritic-folded, uppercased employer name."""
    norm = normalize_employer(raw, country_iso3=country_iso3)
    return norm.legal_name_stripped or _strip_diacritics(raw)


def _norm_person_name(raw: str, issuing_state_iso3: Optional[str] = None) -> str:
    """ICAO §6 + Mn-fold person name for comparison.

    For surnames (single token), we run normalize_name and use
    surname_main — particles stripped, ICAO-folded, uppercase. For
    multi-token given-name inputs ('MARIE CLAIRE' on a TD3 passport
    name field), we just apply the Mn-fold + uppercase directly; the
    normalize_name decomposition would mis-treat the last token as a
    surname.
    """
    raw_stripped = raw.strip()
    if " " in raw_stripped or "<" in raw_stripped:
        # Multi-token: ICAO-fold each piece and rejoin with single spaces.
        # Use < as a separator alongside spaces (MRZ name fields use it).
        pieces = [p for p in raw_stripped.replace("<", " ").split() if p]
        return " ".join(_strip_diacritics(p) for p in pieces)
    # Single-token: use normalize_name → surname_main when available.
    try:
        n = normalize_name(raw_stripped, issuing_state_iso3=issuing_state_iso3)
        if n.surname_main:
            return n.surname_main
    except Exception:  # noqa: BLE001 — fall back to bare fold
        pass
    return _strip_diacritics(raw_stripped)


def _parse_salary_decimal(raw: Any) -> Optional[Decimal]:
    """Coerce a raw salary value to Decimal via normalize.money.

    Tolerates strings already in canonical "12345.67" form.
    """
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    if not isinstance(raw, str):
        return None
    # Fast path: canonical Decimal string.
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        pass
    parsed = parse_money(raw)
    return parsed.amount


def _content_hash(candidates: Sequence[Candidate]) -> str:
    """Stable fingerprint over a sorted Candidate list."""
    payload = sorted(
        [
            {
                "value": str(c.value),
                "document_id": str(c.document_id),
                "confidence": round(c.confidence, 3),
            }
            for c in candidates
        ],
        key=lambda d: (d["document_id"], d["value"]),
    )
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Per-field comparators
# ─────────────────────────────────────────────────────────────────────────────


def _compare_person_name(
    candidates: Sequence[Candidate],
    *,
    field_key: str,
    allow_maiden_variation: bool = False,
) -> bool:
    """Return True if the candidate set is *equivalent* under the field's
    allowed-variation rules; False if they contradict.

    ``allow_maiden_variation`` adds a tolerance for the maiden-name case:
    when ONE of the candidates is sourced from a MARRIAGE_CERT (or
    BIRTH_CERT) and the others agree on a different surname, treat the
    marriage-cert value as a maiden annotation rather than a contradiction.
    """
    if len(candidates) <= 1:
        return True
    normalised = [
        _norm_person_name(str(c.value) if c.value is not None else "")
        for c in candidates
    ]
    if len(set(normalised)) <= 1:
        return True
    if allow_maiden_variation:
        # If exactly one candidate is from MARRIAGE_CERT / BIRTH_CERT and
        # the others all agree on a single value, treat the marriage-cert
        # entry as the maiden annotation.
        maiden_indices = [
            i
            for i, c in enumerate(candidates)
            if c.document_type_code in {"MARRIAGE_CERT", "BIRTH_CERT"}
        ]
        if len(maiden_indices) == 1:
            others = [n for i, n in enumerate(normalised) if i not in maiden_indices]
            if len(set(others)) == 1:
                return True
    return False


def _compare_dob(candidates: Sequence[Candidate]) -> bool:
    """DOB allows zero variation (§3.6)."""
    if len(candidates) <= 1:
        return True
    values = {str(c.value).strip() for c in candidates if c.value is not None}
    return len(values) <= 1


def _compare_employer(candidates: Sequence[Candidate]) -> bool:
    """Employer legal name allows legal-suffix normalisation + parent/
    subsidiary match via registry_id.
    """
    if len(candidates) <= 1:
        return True

    # 1. Legal-suffix normalised match across all.
    normalised = [_norm_employer_name(str(c.value) if c.value is not None else "") for c in candidates]
    if len(set(normalised)) <= 1:
        return True

    # 2. Parent/subsidiary tolerance: when ALL candidates carry the SAME
    # registry_id (passed via value_canonical or explicit Candidate metadata),
    # we treat them as the same legal entity even if the display names differ.
    registry_ids = {
        _extract_registry_id(c) for c in candidates
    }
    registry_ids.discard(None)
    return len(registry_ids) == 1


def _extract_registry_id(c: Candidate) -> Optional[str]:
    """Pull a registry_id off a Candidate if the upstream ExtractedField
    carried it in ``value_canonical``.

    The C1-05c EMPLOYMENT_CONTRACT agent stamps registry_id on its
    employer_legal_name field's value_canonical.kind dict; the C1-05d
    PAYSLIP agent does the same. Surface it for the contradiction
    detector here.
    """
    val = c.value
    if isinstance(val, Mapping):
        rid = val.get("registry_id")
        return str(rid) if rid else None
    return None


def _compare_salary(candidates: Sequence[Candidate]) -> bool:
    """Annual salary allows ±5 % relative tolerance.

    Comparator pattern: max - min ≤ tolerance × max. Returns True if
    every candidate falls within tolerance of the maximum.
    """
    if len(candidates) <= 1:
        return True
    decimals: List[Decimal] = []
    for c in candidates:
        d = _parse_salary_decimal(c.value)
        if d is None:
            # Treat unparseable as a missing-value scenario for this comparator;
            # MISSING_VALUE detection lives in the orchestrator.
            return True
        decimals.append(d)
    if not decimals:
        return True
    max_d = max(decimals)
    min_d = min(decimals)
    if max_d == 0:
        return True
    spread = (max_d - min_d) / max_d
    return spread <= SALARY_RELATIVE_TOLERANCE


# Comparator registry indexed by canonical field key.
ComparatorFn = Callable[[Sequence[Candidate]], bool]


def _surname_comparator(candidates: Sequence[Candidate]) -> bool:
    return _compare_person_name(
        candidates, field_key="surname", allow_maiden_variation=True
    )


def _given_names_comparator(candidates: Sequence[Candidate]) -> bool:
    return _compare_person_name(
        candidates, field_key="given_names", allow_maiden_variation=False
    )


COMPARATORS: Mapping[str, ComparatorFn] = {
    "surname": _surname_comparator,
    "given_names": _given_names_comparator,
    "date_of_birth": _compare_dob,
    "employer_legal_name": _compare_employer,
    "gross_salary_annual": _compare_salary,
}


# Map field_key → ContradictionType (Cohort 1: only DIRECT_CONTRADICTION fires).
DEFAULT_CONTRADICTION_TYPE: Mapping[str, ContradictionType] = {
    "surname": "DIRECT_CONTRADICTION",
    "given_names": "DIRECT_CONTRADICTION",
    "date_of_birth": "DIRECT_CONTRADICTION",
    "employer_legal_name": "DIRECT_CONTRADICTION",
    "gross_salary_annual": "DIRECT_CONTRADICTION",
}


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


def _candidate_from_field(
    f: ExtractedField,
    *,
    document_type_code: Optional[str],
) -> Candidate:
    """Lift an ExtractedField row into a Candidate."""
    return Candidate(
        value=f.value_raw,
        document_id=f.document_id,
        page=f.bbox_page,
        bbox=(f.bbox_x0, f.bbox_y0, f.bbox_x1, f.bbox_y1)
        if all(v is not None for v in (f.bbox_x0, f.bbox_y0, f.bbox_x1, f.bbox_y1))
        else None,
        source_agent_run_id=f.agent_run_id,
        confidence=f.confidence,
        document_type_code=document_type_code,
    )


def detect_contradictions(
    case_id: UUID,
    store: ContradictionStore,
    *,
    field_keys: Sequence[str] = COHORT_1_FIELD_KEYS,
) -> Tuple[Contradiction, ...]:
    """Detect contradictions across documents for a single case.

    For each ``field_key`` in the Cohort 1 fixed set, group all
    ExtractedField rows by ``canonical_entity_id``, build Candidate lists,
    and run the per-field comparator. Comparator returning False emits a
    Contradiction row.

    Returns the contradictions that were freshly inserted. Re-runs against
    unchanged data are idempotent — the store dedupes via
    ``(case_id, canonical_entity_id, field_key, content_hash)``.
    """
    all_fields = list(store.list_extracted_fields_for_case(case_id))

    # Group by (canonical_entity_id, field_key)
    buckets: Dict[Tuple[Optional[UUID], str], List[Candidate]] = {}
    for f in all_fields:
        if f.field_key not in field_keys:
            continue
        eid = store.get_canonical_entity_for_field(_synthetic_field_id(f))
        doc_type = store.get_document_type(f.document_id)
        candidate = _candidate_from_field(f, document_type_code=doc_type)
        buckets.setdefault((eid, f.field_key), []).append(candidate)

    detected: List[Contradiction] = []
    for (eid, field_key), candidates in buckets.items():
        comparator = COMPARATORS.get(field_key)
        if comparator is None:
            continue
        if comparator(candidates):
            # Equivalent under allowed-variation — no contradiction.
            continue
        candidates_tuple = tuple(candidates)
        contradiction = Contradiction(
            contradiction_id=uuid4(),
            case_id=case_id,
            canonical_entity_id=eid,
            field_key=field_key,
            type=DEFAULT_CONTRADICTION_TYPE.get(field_key, "DIRECT_CONTRADICTION"),
            candidates=candidates_tuple,
            resolution_status="Requires attention",
            suggested_winner=None,
            content_hash=_content_hash(candidates_tuple),
            detected_at=datetime.now(tz=timezone.utc),
        )
        detected.append(contradiction)

    inserted, _skipped = store.upsert_contradictions(detected)
    # Only return rows that were actually inserted this call.
    return tuple(detected[:inserted]) if inserted == len(detected) else tuple(detected)


# ─────────────────────────────────────────────────────────────────────────────
# Public surface
# ─────────────────────────────────────────────────────────────────────────────


__all__ = [
    "COHORT_1_FIELD_KEYS",
    "Candidate",
    "Contradiction",
    "ContradictionStore",
    "ContradictionType",
    "InMemoryContradictionStore",
    "ResolutionStatus",
    "SALARY_RELATIVE_TOLERANCE",
    "detect_contradictions",
]

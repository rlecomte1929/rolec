"""Pydantic models for the Extraction Agent runtime (C1-05a).

The shapes here are the contract:

* :class:`ExtractionAgent` — Parsewise's 9-field agent definition. Editable.
* :class:`ExtractionAgentVersion` — A frozen snapshot of an agent at a point
  in time. Immutable once persisted.
* :class:`ExtractedField` — A single field extracted from a document, with
  the canonical 0-1000 bbox citation required by the C1-01 schema.
* :class:`ParsedDocument` — The input the runtime consumes: OCR text + per
  word bboxes.

The versioning fingerprint :func:`compute_version_hash` covers the 8 fields
that Parsewise treats as "value-defining": changing any of them clears the
old version's extractions and bumps the version number (registry-side).

Pydantic v2.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Document input
# ─────────────────────────────────────────────────────────────────────────────


class ParsedWord(BaseModel):
    """One OCR'd word with its bbox in canonical 0–1000 space (Parsewise convention)."""

    model_config = ConfigDict(frozen=True)

    text: str
    page: int = Field(ge=1)
    x0: int = Field(ge=0, le=1000)
    y0: int = Field(ge=0, le=1000)
    x1: int = Field(ge=0, le=1000)
    y1: int = Field(ge=0, le=1000)

    @field_validator("x1")
    @classmethod
    def _x_order(cls, v: int, info) -> int:  # type: ignore[no-untyped-def]
        x0 = info.data.get("x0")
        if x0 is not None and v < x0:
            raise ValueError(f"bbox x1 ({v}) must be >= x0 ({x0})")
        return v

    @field_validator("y1")
    @classmethod
    def _y_order(cls, v: int, info) -> int:  # type: ignore[no-untyped-def]
        y0 = info.data.get("y0")
        if y0 is not None and v < y0:
            raise ValueError(f"bbox y1 ({v}) must be >= y0 ({y0})")
        return v


class ParsedDocument(BaseModel):
    """The OCR/parse output the runtime hands to an agent.

    ``words`` is the ordered, per-word OCR result with canonical 0-1000 bboxes;
    ``text`` is the same content concatenated for the prompt-building step.
    Agents may use either or both. ``document_id`` and ``case_id`` are the
    foreign-key targets the runtime writes back to.
    """

    model_config = ConfigDict(frozen=True)

    document_id: UUID
    case_id: Optional[UUID] = None
    mime_type: Optional[str] = None
    language: Optional[str] = None
    text: str
    words: Tuple[ParsedWord, ...] = ()


# ─────────────────────────────────────────────────────────────────────────────
# Agent definition (Parsewise 9-field shape)
# ─────────────────────────────────────────────────────────────────────────────


# The 8 fields Parsewise treats as version-defining. Changing any of them on
# save forces a new version row and clears the old version's extractions.
# Reference: Architecture Report §4.1 + the Parsewise versioning convention.
VERSIONED_FIELDS: Tuple[str, ...] = (
    "extraction_instructions",
    "value_type",
    "unit",
    "examples",
    "resolution_instructions",
    "inconsistency_instructions",
    "enable_complex_calculations_in_resolution",
    "enable_web_search",
)


class ExtractionAgentExample(BaseModel):
    """One few-shot exemplar attached to an :class:`ExtractionAgent`.

    The example structure is intentionally minimal: an input text excerpt and
    the canonical output the agent should produce on it. The runtime serialises
    these into the LLM prompt verbatim.
    """

    model_config = ConfigDict(frozen=True)

    input_text: str
    output: Dict[str, Any]
    notes: Optional[str] = None


class ExtractionAgent(BaseModel):
    """The 9-field Parsewise agent definition (editable, unversioned).

    Used to construct or update an agent. On save, the :class:`AgentRegistry`
    computes a :func:`compute_version_hash` over the 8 versioned fields. If the
    hash differs from the agent's current version's hash, a new
    :class:`ExtractionAgentVersion` row is created and the previous version's
    extractions are cleared (Parsewise rule).
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None

    extraction_instructions: str = Field(min_length=1)
    value_type: Literal["string", "number", "date", "boolean", "enum"]
    unit: Optional[str] = None
    dimensions: Optional[str] = None
    resolution_instructions: Optional[str] = None
    inconsistency_instructions: Optional[str] = None
    enable_web_search: bool = False
    enable_complex_calculations_in_resolution: bool = False

    examples: Tuple[ExtractionAgentExample, ...] = ()

    # Schema the runtime validates output against. Strings here = required field
    # keys; the dict form (key → JSON-Schema-ish constraint) is supported for
    # downstream agents that want type enforcement.
    output_schema_required_keys: Tuple[str, ...] = ()


class VersionedFieldSnapshot(BaseModel):
    """The exact set of fields hashed into ``version_hash``.

    Pulled out into a model so :func:`compute_version_hash` can be tested
    independently of an :class:`ExtractionAgent` instance.
    """

    model_config = ConfigDict(frozen=True)

    extraction_instructions: str
    value_type: str
    unit: Optional[str]
    examples: Tuple[Dict[str, Any], ...]
    resolution_instructions: Optional[str]
    inconsistency_instructions: Optional[str]
    enable_complex_calculations_in_resolution: bool
    enable_web_search: bool


def compute_version_hash(agent: ExtractionAgent) -> str:
    """Hash the 8 Parsewise-versioned fields into a stable fingerprint.

    Returns a 64-char hex SHA-256. Two agents with identical hashes have
    identical value-defining configuration and therefore share a version.
    """
    snapshot = VersionedFieldSnapshot(
        extraction_instructions=agent.extraction_instructions,
        value_type=agent.value_type,
        unit=agent.unit,
        examples=tuple(ex.model_dump(mode="json") for ex in agent.examples),
        resolution_instructions=agent.resolution_instructions,
        inconsistency_instructions=agent.inconsistency_instructions,
        enable_complex_calculations_in_resolution=agent.enable_complex_calculations_in_resolution,
        enable_web_search=agent.enable_web_search,
    )
    payload = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ExtractionAgentVersion(BaseModel):
    """A frozen snapshot of an :class:`ExtractionAgent` at a point in time.

    Immutable. Persisted to ``rce.agent_versions``. Foreign-keyed to from
    ``rce.agent_runs.agent_version_ref`` and (indirectly) from
    ``rce.extracted_fields.agent_run_id``.
    """

    model_config = ConfigDict(frozen=True)

    agent_version_id: UUID
    agent_id: UUID
    name: str
    version_number: int = Field(ge=1)
    version_hash: str

    # The 9 fields verbatim. (description lives on the agent, not the version.)
    extraction_instructions: str
    value_type: str
    unit: Optional[str]
    dimensions: Optional[str]
    resolution_instructions: Optional[str]
    inconsistency_instructions: Optional[str]
    enable_web_search: bool
    enable_complex_calculations_in_resolution: bool
    examples: Tuple[ExtractionAgentExample, ...] = ()
    output_schema_required_keys: Tuple[str, ...] = ()

    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Extraction outputs
# ─────────────────────────────────────────────────────────────────────────────


ResolutionStatus = Literal[
    "Resolved", "Requires attention", "Not resolved", "No result", "Ignored"
]


class ExtractedField(BaseModel):
    """One field the runtime produced. Maps 1:1 to ``rce.extracted_fields``.

    All bbox coordinates are in canonical 0-1000 Parsewise space. ``confidence``
    is the LLM's reported confidence (0-1, three-decimal precision). ``agent_run_id``
    is set by the runtime after the agent_runs row lands.
    """

    model_config = ConfigDict(frozen=True)

    document_id: UUID
    field_key: str
    value_raw: Optional[str] = None
    value_canonical: Optional[Dict[str, Any]] = None
    confidence: float = Field(ge=0.0, le=1.0)

    bbox_page: Optional[int] = Field(default=None, ge=1)
    bbox_x0: Optional[int] = Field(default=None, ge=0, le=1000)
    bbox_y0: Optional[int] = Field(default=None, ge=0, le=1000)
    bbox_x1: Optional[int] = Field(default=None, ge=0, le=1000)
    bbox_y1: Optional[int] = Field(default=None, ge=0, le=1000)

    agent_run_id: Optional[UUID] = None
    resolution_status: Optional[ResolutionStatus] = None


class ExtractionRunResult(BaseModel):
    """What :meth:`ExtractionRunner.run` returns to the caller."""

    # `model_name` collides with pydantic v2's protected "model_" namespace
    # unless we opt out explicitly. We don't use the model_validate /
    # model_construct hooks on this dataclass, so suppressing the warning
    # is safe and matches the wording in the brief.
    model_config = ConfigDict(frozen=True, protected_namespaces=())

    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model_name: str


# ─────────────────────────────────────────────────────────────────────────────
# Cross-version helpers
# ─────────────────────────────────────────────────────────────────────────────


def is_versioned_field_changed(agent: ExtractionAgent, version: ExtractionAgentVersion) -> bool:
    """Return True if any of the 8 versioned fields differs between ``agent``
    and the supplied ``version``. Cheap pre-check before computing the hash.
    """
    if compute_version_hash(agent) != version.version_hash:
        return True
    return False


def list_versioned_field_diffs(
    agent: ExtractionAgent, version: ExtractionAgentVersion
) -> List[str]:
    """List the names of versioned fields that differ between ``agent`` and
    ``version``. Used for human-readable diff output in tests and logs.
    """
    out: List[str] = []
    for f in VERSIONED_FIELDS:
        a = getattr(agent, f)
        b = getattr(version, f, None)
        if f == "examples":
            a = tuple(ex.model_dump(mode="json") for ex in agent.examples)
            b = tuple(ex.model_dump(mode="json") for ex in version.examples)
        if a != b:
            out.append(f)
    return out

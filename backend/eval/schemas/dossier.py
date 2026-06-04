# AIQ-614 — Pydantic v2 contract models for AI-W dossier evaluation harness
from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, field_validator


class Bbox(BaseModel):
    x0: int
    y0: int
    x1: int
    y1: int

    @field_validator("x0", "y0", "x1", "y1")
    @classmethod
    def in_range(cls, v: int) -> int:
        if not 0 <= v <= 1000:
            raise ValueError(f"Bbox coordinate {v} is outside [0, 1000]")
        return v


class ExtractedField(BaseModel):
    field_key: str
    value: str
    bbox: Bbox
    confidence: float


class CanonicalEntity(BaseModel):
    entity_type: str  # e.g. PERSON | EMPLOYER | SALARY_EUR | …
    canonical_value: str
    source_field_keys: List[str]


class RuleCitation(BaseModel):
    rule_version_id: str
    article: str
    effective_from: date
    effective_to: Optional[date] = None


class EligibilityVerdict(BaseModel):
    outcome_set: List[str]
    citations: List[RuleCitation]


class Step(BaseModel):
    step_id: str
    description: str
    required: bool
    order: int


class StepGraph(BaseModel):
    steps: List[Step]


class SeededContradiction(BaseModel):
    contradiction_type: str  # SURNAME_MISMATCH|DOB_MISMATCH|EMPLOYER_MISMATCH|SALARY_MISMATCH|ADDRESS_MISMATCH
    field_key: str
    affected_documents: List[str]


class GenerationMeta(BaseModel):
    dossier_id: str
    seed: int
    generated_at: str
    schema_version: str = "1.0"


class Dossier(BaseModel):
    dossier_id: str
    extracted_fields: List[ExtractedField]
    canonical_entities: List[CanonicalEntity]
    eligibility_verdict: EligibilityVerdict
    step_graph: StepGraph
    seeded_contradictions: List[SeededContradiction]
    generation_meta: GenerationMeta

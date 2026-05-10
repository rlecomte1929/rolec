"""Shared types for the Recommendation Engine."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AvailabilityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SCARCE = "scarce"


class RecommendationTier(str, Enum):
    BEST_MATCH = "best_match"
    GOOD_FIT = "good_fit"
    OK = "ok"
    WEAK = "weak"


class AvailabilityMetadata(BaseModel):
    availability_level: AvailabilityLevel
    next_available_days: Optional[int] = None
    waitlist_weeks: Optional[int] = None
    notes: Optional[str] = None


class RecommendationExplanation(BaseModel):
    """Structured explanation metadata for each recommendation."""
    match_reasons: List[str] = Field(default_factory=list)
    destination_fit: str = "unknown"
    service_fit: str = "unknown"
    budget_fit: str = "unknown"
    family_fit: str = "unknown"
    policy_fit: str = "unknown"
    coverage_fit: str = "unknown"
    warning_flags: List[str] = Field(default_factory=list)
    explanation_summary: str = ""
    score_dimensions: Dict[str, float] = Field(default_factory=dict)


class RecommendationItem(BaseModel):
    item_id: str
    name: str
    score: float = Field(..., ge=0, le=100)
    tier: RecommendationTier
    summary: str
    rationale: str
    breakdown: Dict[str, float] = Field(default_factory=dict)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[RecommendationExplanation] = None


class RecommendationResponse(BaseModel):
    category: str
    generated_at: str
    criteria_echo: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[RecommendationItem]

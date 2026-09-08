"""Request models for provider estimate comparison against published policy caps."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProviderEstimateLine(BaseModel):
    """Single monetary estimate from any service provider (not tied to a vendor schema)."""

    benefit_key: str = Field(..., min_length=1)
    amount: float = Field(..., description="Estimate in major currency units (e.g. USD dollars)")
    currency: str = Field(..., min_length=3, max_length=8, description="ISO-like currency code")


class CapsCompareRequest(BaseModel):
    assignment_type: Optional[str] = None
    family_status: Optional[str] = None
    estimates: List[ProviderEstimateLine] = Field(default_factory=list)

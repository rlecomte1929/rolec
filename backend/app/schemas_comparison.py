"""
[AIQ-236 / P3-1] Pydantic models for the benefit comparison engine.

Located as a flat `schemas_comparison.py` module (rather than the
`backend/app/schemas/comparison.py` path suggested in the original spec)
because `backend/app/schemas.py` already exists as a module that the rest
of the codebase imports via `from ..schemas import UserRole`. Promoting
that module to a package would risk shadowing the existing imports across
~10 call sites. The flat-file convention matches the sibling
`backend/schemas_policy_caps.py` and `backend/schemas_compensation_allowance.py`.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


CoverageStatus = Literal["Covered", "Partial", "Uncovered"]


class ComparisonResult(BaseModel):
    """
    One row of the employee-vs-tier comparison output.

    `delta` is always >= 0 (absolute over-spend). `Covered` rows carry
    `delta = 0`. `Uncovered` rows (category in ask but not in policy) carry
    `delta = ask_value` so the frontend can show the full unsupported amount.
    """

    category_code: str = Field(..., description="Canonical category code, e.g. 'CAT-01'.")
    category_name: str = Field(..., description="Human-readable category, e.g. 'Housing Allowance'.")
    policy_cap: Optional[float] = Field(None, description="Tier cap; None when category is Uncovered.")
    ask_value: Optional[float] = Field(None, description="Employee-requested amount; None when policy-only.")
    currency: str = Field(..., description="Currency of the row (cap currency wins; ask currency on Uncovered).")
    unit: Optional[str] = Field(None, description="Cap unit, e.g. 'month', 'one-time'.")
    coverage_status: CoverageStatus
    delta: float = Field(..., ge=0.0, description="abs(ask - cap) for Partial, 0 for Covered, ask_value for Uncovered.")
    policy_version: Optional[str] = Field(None, description="Live policy version label (e.g. 'v3').")
    policy_effective_date: Optional[str] = Field(None, description="ISO date the policy version became effective.")
    currency_warning: bool = Field(False, description="True when ask and cap currencies differ; no auto-conversion is performed.")

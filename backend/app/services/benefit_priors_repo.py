"""Read benefit satisfaction/variance priors for a company (Parker-B).

Kept separate from ``benefit_optimizer`` so the optimizer stays DB-free and unit
testable. The router uses these priors to fill in any candidate that arrives
without an explicit ``expected_satisfaction`` / ``variance`` before optimizing.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

# (category, attr_key) -> {"expected_satisfaction": float, "variance": float, "source": str}
PriorMap = Dict[Tuple[str, str], Dict[str, Any]]


def load_company_priors(session: Session, company_id: str) -> PriorMap:
    """Return all admin-seeded priors for ``company_id`` keyed by (category, attr_key)."""
    rows = session.execute(
        text(
            """
            select category, attr_key, expected_satisfaction, variance, source
            from public.benefit_priors
            where company_id = :company_id
            """
        ),
        {"company_id": company_id},
    ).mappings()
    priors: PriorMap = {}
    for r in rows:
        priors[(r["category"], r["attr_key"])] = {
            "expected_satisfaction": float(r["expected_satisfaction"]),
            "variance": None if r["variance"] is None else float(r["variance"]),
            "source": r["source"],
        }
    return priors

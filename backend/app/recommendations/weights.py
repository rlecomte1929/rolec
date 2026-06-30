"""Externalized scoring weights for recommendation plugins.

Single source of truth for the per-factor weights each category plugin applies
in ``score()``. Values were previously hardcoded as literals inside every
plugin; they are lifted here **unchanged** so rankings stay byte-identical while
the weights become inspectable/tunable in one place (and reproducible by the
offline ranking eval).

Plugins that accept a request-supplied ``criteria.weights`` override (``movers``,
``schools``, ``living_areas``) still honor it — these values are only the
fallback when the request omits a weight, matching the prior ``w.get(key, lit)``
behavior exactly.

Each inner dict's weights sum to 1.0.
"""
from __future__ import annotations

from typing import Dict

WEIGHTS: Dict[str, Dict[str, float]] = {
    # banks.py — linear blend, no request override.
    "banks": {
        "language": 0.2,
        "fees": 0.15,
        "onboarding": 0.1,
        "digital": 0.15,
        "expat": 0.15,
        "branch": 0.1,
        "rating": 0.1,
        "availability": 0.05,
    },
    # insurance.py — linear blend, no request override.
    "insurance": {
        "coverage": 0.35,
        "deductible": 0.2,
        "family": 0.2,
        "rating": 0.15,
        "availability": 0.1,
    },
    # movers.py — fallbacks for criteria.weights (request may override per key).
    "movers": {
        "cost": 0.2,
        "speed": 0.2,
        "reliability": 0.2,
        "services": 0.15,
        "rating": 0.15,
        "availability": 0.1,
    },
    # schools.py — fallbacks for criteria.weights (request may override per key).
    "schools": {
        "fit": 0.25,
        "quality": 0.2,
        "language": 0.15,
        "commute": 0.15,
        "availability": 0.15,
        "rating": 0.1,
    },
    # living_areas.py — fallbacks for criteria.weights (request may override per key).
    "living_areas": {
        "budget": 0.25,
        "commute": 0.25,
        "space": 0.15,
        "lifestyle": 0.15,
        "rating": 0.1,
        "availability": 0.1,
    },
    # electricity.py — linear blend, no request override.
    "electricity": {
        "green": 0.3,
        "flexibility": 0.25,
        "transparency": 0.2,
        "rating": 0.15,
        "availability": 0.1,
    },
    # medical.py — linear blend, no request override.
    "medical": {
        "specialty": 0.3,
        "language": 0.2,
        "wait": 0.2,
        "rating": 0.2,
        "availability": 0.1,
    },
    # Stub plugins: simple rating/availability split (rating * 0.7 + avail * 0.3).
    "childcare": {"rating": 0.7, "availability": 0.3},
    "telecom": {"rating": 0.7, "availability": 0.3},
    "transport": {"rating": 0.7, "availability": 0.3},
    "storage": {"rating": 0.7, "availability": 0.3},
    "legal_admin": {"rating": 0.7, "availability": 0.3},
    "tax_finance": {"rating": 0.7, "availability": 0.3},
    "language_integration": {"rating": 0.7, "availability": 0.3},
}

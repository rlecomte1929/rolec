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

import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

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
    # service_area (0.10) added to score destination-city coverage from service_areas dataset field;
    # services and rating reduced by 0.05 each to keep the sum at 1.0.
    "movers": {
        "cost": 0.2,
        "speed": 0.2,
        "reliability": 0.2,
        "services": 0.10,
        "rating": 0.10,
        "availability": 0.10,
        "service_area": 0.10,
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
    "pets": {"rating": 0.7, "availability": 0.3},
}


# ── P2: per-segment learned-weight override layer ───────────────────────────
#
# ``get_weights(category, segment=...)`` is the single accessor every plugin now
# calls instead of indexing ``WEIGHTS`` directly. It returns a per-segment
# override *merged over* the global ``WEIGHTS[category]``, or exactly the global
# dict (the same object) when no override applies. An override only ever applies
# when BOTH (a) the ``SUPPLIER_LEARNED_WEIGHTS`` env flag is on AND (b) the
# learned-weights store holds an entry for (category, segment). With the flag
# OFF (the default) this is byte-identical to the pre-P2 ``w = WEIGHTS[cat]``
# behaviour — the store is never even consulted.
#
# Overrides are produced offline by ``backend/scripts/fit_supplier_weights.py``
# from logged recommendation slates ⋈ selection events and persisted in
# ``supplier_ranking_weights`` (see ranking_weights_store.py). Serving them is a
# deliberate, flag-gated step; the data foundation accrues regardless.


def _learned_weights_enabled() -> bool:
    """True only when SUPPLIER_LEARNED_WEIGHTS is explicitly on (env→DB→default OFF)."""
    env_val = os.environ.get("SUPPLIER_LEARNED_WEIGHTS")
    if env_val is not None:
        return env_val.strip().lower() in {"1", "true", "yes", "on"}
    from ..db import SessionLocal
    from ..services.platform_settings import get_setting as _ps_get
    try:
        with SessionLocal() as _db:
            val = _ps_get("supplier_learned_weights", default="0", db=_db)
    except Exception:
        val = "0"
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def derive_segment(criteria: Any) -> Optional[str]:
    """The learned-ranking segment key for a request (or ``None``).

    Segments are keyed on the normalised destination city — the one location
    field carried by both the request criteria and the destination-aware plugin
    criteria models (movers / schools / living_areas). Categories whose criteria
    omit a destination resolve to ``None`` (the global, un-segmented bucket).
    Accepts either a raw criteria ``dict`` or a parsed pydantic criteria model so
    the write path (slate logging, raw dict) and the serve path (plugins, parsed
    model) derive identical keys.
    """
    if criteria is None:
        return None
    if isinstance(criteria, dict):
        city = criteria.get("destination_city")
    else:
        city = getattr(criteria, "destination_city", None)
    if not city or not isinstance(city, str):
        return None
    norm = city.split(",")[0].strip().lower()
    return norm or None


def _read_segment_override(
    category: str, segment: Optional[str]
) -> Optional[Dict[str, float]]:
    """Best-effort load of a learned per-segment weight override; ``None`` if
    absent or on any error (missing table, unconfigured DB, etc.)."""
    try:
        from .ranking_weights_store import load_segment_weights

        return load_segment_weights(category, segment)
    except Exception as exc:  # never break scoring on a store hiccup
        log.debug("learned-weights store read failed for %s/%s: %s", category, segment, exc)
        return None


def get_weights(category: str, *, segment: Optional[str] = None) -> Dict[str, float]:
    """Scoring weights for ``category``, with an optional per-segment override.

    Returns the global ``WEIGHTS[category]`` (the same object — byte-identical to
    the legacy direct-index behaviour) unless the learned-weights flag is on AND
    the store holds an override for ``(category, segment)``, in which case a copy
    of the global dict is returned with the stored factors merged over it. Only
    factors that already exist in the global dict are blended, so a stale or
    malformed override can never introduce or drop a factor.
    """
    base = WEIGHTS[category]
    if not _learned_weights_enabled():
        return base
    override = _read_segment_override(category, segment)
    if not override:
        return base
    merged = dict(base)
    for k, v in override.items():
        if k in merged:
            try:
                merged[k] = float(v)
            except (TypeError, ValueError):
                continue
    return merged

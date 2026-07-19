"""[F14] Backend reader for the ONE shared service→benefit taxonomy.

The Employee Services catalog (frontend serviceConfig.ts) and the HR Policy
Builder matrix (_CANONICAL_KEYS in policy_config_matrix_service.py) historically
spoke two vocabularies that never intersected, translated by three inconsistent
ad-hoc alias maps (frontend providerServiceBenefitMap.ts, _SERVICE_BENEFIT_KEYS
in cases_read.py, SERVICE_MODULE_BENEFIT_KEYS in policy_config_matrix_service.py).
Result: the caps/compare bridge always answered ``no_cap_for_benefit_in_context``
and over-cap — the trigger for the Policy Exception → HR notification path —
could never fire.

This module is the single backend entry point to the controlled taxonomy at
``shared/service_benefit_taxonomy.json`` (repo root), which the frontend imports
directly as JSON. Do NOT redeclare service→benefit_key maps in code — extend the
JSON instead. Guarded by backend/tests/test_service_benefit_taxonomy.py.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

# backend/app/services/ → backend/app → backend → repo root
_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[3] / "shared" / "service_benefit_taxonomy.json"
)


@lru_cache(maxsize=1)
def _taxonomy() -> Dict[str, Any]:
    """Load the shared taxonomy once. Fail fast — a missing/broken taxonomy file
    means every cap comparison would silently degrade to no_cap, which is exactly
    the F14 failure mode this module exists to prevent."""
    with open(_TAXONOMY_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data.get("services"), dict):
        raise ValueError(
            f"shared taxonomy at {_TAXONOMY_PATH} is missing the 'services' map"
        )
    return data


def normalize_service_key(service_key: Any) -> str:
    """Lowercase, trim, hyphens→underscores, and resolve aliases (backendKeys,
    legacy intake vocabulary, RFQ vocabulary) to the canonical catalog key."""
    k = str(service_key or "").strip().lower().replace("-", "_")
    aliases = _taxonomy().get("aliases") or {}
    return str(aliases.get(k, k))


def benefit_keys_for_service(service_key: Any) -> List[str]:
    """Canonical policy-config benefit_keys whose published caps make up this
    service's budget. [] for services explicitly declared uncapped AND for
    unknown keys (both are an honest no_cap downstream)."""
    canonical = normalize_service_key(service_key)
    keys = (_taxonomy().get("services") or {}).get(canonical) or []
    return [str(k) for k in keys]


def declared_service_keys() -> List[str]:
    """Every canonical service key the taxonomy declares (catalog + legacy)."""
    return sorted((_taxonomy().get("services") or {}).keys())


def service_aliases() -> Dict[str, str]:
    """alias → canonical service key."""
    return dict(_taxonomy().get("aliases") or {})


def module_benefit_keys() -> Dict[str, List[str]]:
    """Service-module → benefit_keys hints (the serviceModule filter of
    GET /api/policy-config/caps). Formerly SERVICE_MODULE_BENEFIT_KEYS."""
    return {
        str(m): [str(k) for k in (keys or [])]
        for m, keys in (_taxonomy().get("modules") or {}).items()
    }


def all_mapped_benefit_keys() -> List[str]:
    """Every benefit_key referenced anywhere in the taxonomy (services + modules).
    Used by the guard test to prove the vocabulary intersection is real."""
    out: set = set()
    for keys in (_taxonomy().get("services") or {}).values():
        out.update(str(k) for k in (keys or []))
    for keys in (_taxonomy().get("modules") or {}).values():
        out.update(str(k) for k in (keys or []))
    return sorted(out)

"""
Canonical assignment type / family status values for the Compensation & Allowance matrix.

- Writes are validated against enums in schemas_compensation_allowance.
- Reads and query params accept legacy synonyms and normalize for matching.
"""
from __future__ import annotations

from typing import Any, List, Optional, Set

# Product canonical values (snake_case)
ASSIGNMENT_TYPES: Set[str] = {"short_term", "long_term", "permanent", "international"}
FAMILY_STATUSES: Set[str] = {"single", "spouse_partner", "dependents"}

_ASSIGNMENT_ALIASES = {
    "short_term": "short_term",
    "shortterm": "short_term",
    "short-term": "short_term",
    "sta": "short_term",
    "long_term": "long_term",
    "longterm": "long_term",
    "long-term": "long_term",
    "lta": "long_term",
    "permanent": "permanent",
    "perm": "permanent",
    "international": "international",
    "intl": "international",
    "global": "international",
    "local_plus": "international",
    "commuter": "short_term",
}

_FAMILY_ALIASES = {
    "single": "single",
    "solo": "single",
    "spouse_partner": "spouse_partner",
    "spouse": "spouse_partner",
    "partner": "spouse_partner",
    "couple": "spouse_partner",
    "married": "spouse_partner",
    "accompanied": "spouse_partner",
    "accompanying": "spouse_partner",
    "dependents": "dependents",
    "dependent": "dependents",
    "with_dependents": "dependents",
    "with dependents": "dependents",
    "with_children": "dependents",
    "family": "dependents",
    "children": "dependents",
}


def _slug(raw: Any) -> str:
    return str(raw).strip().lower().replace("-", "_").replace(" ", "_")


def normalize_assignment_type(raw: Optional[Any]) -> Optional[str]:
    """Map user/query/DB string to canonical assignment type, or None if empty/unknown."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    key = _slug(s)
    if key in ASSIGNMENT_TYPES:
        return key
    mapped = _ASSIGNMENT_ALIASES.get(key) or _ASSIGNMENT_ALIASES.get(s.lower())
    if mapped in ASSIGNMENT_TYPES:
        return mapped
    return None


def normalize_family_status(raw: Optional[Any]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    key = _slug(s)
    if key in FAMILY_STATUSES:
        return key
    mapped = _FAMILY_ALIASES.get(key) or _FAMILY_ALIASES.get(s.lower())
    if mapped in FAMILY_STATUSES:
        return mapped
    return None


def coerce_assignment_match_token(raw: Any) -> str:
    """Stable token for comparing a stored row value to a filter (includes slug fallback)."""
    n = normalize_assignment_type(raw)
    if n:
        return n
    return _slug(raw)


def coerce_family_match_token(raw: Any) -> str:
    n = normalize_family_status(raw)
    if n:
        return n
    return _slug(raw)


def _assignment_row_tokens(raw_at: List[Any]) -> Set[str]:
    out: Set[str] = set()
    for x in raw_at:
        if not str(x).strip():
            continue
        n = normalize_assignment_type(x)
        out.add(n if n else coerce_assignment_match_token(x))
    return out


def _family_row_tokens(raw_fs: List[Any]) -> Set[str]:
    out: Set[str] = set()
    for x in raw_fs:
        if not str(x).strip():
            continue
        n = normalize_family_status(x)
        out.add(n if n else coerce_family_match_token(x))
    return out


def row_matches_targeting(
    b: dict,
    assignment_type: Optional[str],
    family_status: Optional[str],
    *,
    strict_context: bool = False,
) -> bool:
    """
    If strict_context is True (employee-facing), a row with assignment_types set does not match
    when assignment_type context is missing. HR preview uses strict_context=False so an unset
    filter means “do not filter on that axis”.
    """
    raw_at = b.get("assignment_types") or []
    raw_fs = b.get("family_statuses") or []
    if not isinstance(raw_at, list):
        raw_at = []
    if not isinstance(raw_fs, list):
        raw_fs = []

    if raw_at:
        filt_at = normalize_assignment_type(assignment_type) if assignment_type else None
        if filt_at is None:
            if strict_context:
                return False
        else:
            if filt_at not in _assignment_row_tokens(raw_at):
                return False

    if raw_fs:
        filt_fs = normalize_family_status(family_status) if family_status else None
        if filt_fs is None:
            if strict_context:
                return False
        else:
            if filt_fs not in _family_row_tokens(raw_fs):
                return False

    return True


def validate_optional_query_assignment_type(raw: Optional[str]) -> Optional[str]:
    """For FastAPI query params: None, or a canonical value, or raise ValueError."""
    if raw is None or str(raw).strip() == "":
        return None
    n = normalize_assignment_type(raw)
    if not n:
        raise ValueError(f"Invalid assignmentType {raw!r}; expected one of {sorted(ASSIGNMENT_TYPES)}")
    return n


def validate_optional_query_family_status(raw: Optional[str]) -> Optional[str]:
    if raw is None or str(raw).strip() == "":
        return None
    n = normalize_family_status(raw)
    if not n:
        raise ValueError(f"Invalid familyStatus {raw!r}; expected one of {sorted(FAMILY_STATUSES)}")
    return n

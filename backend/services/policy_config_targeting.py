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
EMPLOYEE_LEVELS: Set[str] = {"entry", "manager", "director", "vp", "c_suite"}

# Display labels for the frontend (canonical slug → human label).
EMPLOYEE_LEVEL_LABELS: dict = {
    "entry": "Entry Level",
    "manager": "Manager",
    "director": "Director",
    "vp": "VP",
    "c_suite": "C-suite",
}

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

_LEVEL_ALIASES = {
    # Canonical slugs first
    "entry": "entry",
    "manager": "manager",
    "director": "director",
    "vp": "vp",
    "c_suite": "c_suite",
    # Legacy band labels (absorb the existing hr_policies "Band1..4" scheme
    # and L-style seniority values already seeded in AssignmentContextDTO).
    "band1": "entry",
    "l1": "entry",
    "l-1": "entry",
    "entry_level": "entry",
    "entrylevel": "entry",
    "ic": "entry",
    "junior": "entry",
    "band2": "manager",
    "l2": "manager",
    "l-2": "manager",
    "mid": "manager",
    "mid_level": "manager",
    "team_lead": "manager",
    "lead": "manager",
    "band3": "director",
    "l3": "director",
    "l-3": "director",
    "senior_manager": "director",
    "head_of": "director",
    "band4": "vp",
    "l4": "vp",
    "l-4": "vp",
    "vice_president": "vp",
    "svp": "vp",
    "evp": "vp",
    "c-suite": "c_suite",
    "csuite": "c_suite",
    "ceo": "c_suite",
    "cfo": "c_suite",
    "cto": "c_suite",
    "coo": "c_suite",
    "chro": "c_suite",
    "executive": "c_suite",
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


def normalize_employee_level(raw: Optional[Any]) -> Optional[str]:
    """
    Map user/query/DB string to canonical employee level, or None if empty/unknown.
    Accepts canonical slugs plus legacy aliases (Band1..4, L1..4, job-title variants).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    key = _slug(s)
    if key in EMPLOYEE_LEVELS:
        return key
    mapped = _LEVEL_ALIASES.get(key) or _LEVEL_ALIASES.get(s.lower())
    if mapped in EMPLOYEE_LEVELS:
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


def coerce_level_match_token(raw: Any) -> str:
    n = normalize_employee_level(raw)
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


def _level_row_tokens(raw_el: List[Any]) -> Set[str]:
    out: Set[str] = set()
    for x in raw_el:
        if not str(x).strip():
            continue
        n = normalize_employee_level(x)
        out.add(n if n else coerce_level_match_token(x))
    return out


def row_matches_targeting(
    b: dict,
    assignment_type: Optional[str],
    family_status: Optional[str],
    *,
    strict_context: bool = False,
    employee_level: Optional[str] = None,
) -> bool:
    """
    Filter a matrix row against three targeting axes: assignment_type,
    family_status, and employee_level.

    Contract (unchanged for existing axes):
      - Empty array on the row = "applies to all" on that axis (back-compat).
      - strict_context=True (employee-facing resolution): a row that narrows
        an axis does not match when the context for that axis is missing.
      - strict_context=False (HR preview): a missing filter means
        "do not filter on that axis".

    employee_level is added as a keyword-only argument with default None so
    existing callers that have not yet threaded the level through continue
    to work (axis is skipped). Once all callers are updated we can tighten
    to a positional argument in a follow-up.
    """
    raw_at = b.get("assignment_types") or []
    raw_fs = b.get("family_statuses") or []
    raw_el = b.get("employee_levels") or []
    if not isinstance(raw_at, list):
        raw_at = []
    if not isinstance(raw_fs, list):
        raw_fs = []
    if not isinstance(raw_el, list):
        raw_el = []

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

    if raw_el:
        filt_el = normalize_employee_level(employee_level) if employee_level else None
        if filt_el is None:
            if strict_context:
                return False
        else:
            if filt_el not in _level_row_tokens(raw_el):
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


def validate_optional_query_employee_level(raw: Optional[str]) -> Optional[str]:
    if raw is None or str(raw).strip() == "":
        return None
    n = normalize_employee_level(raw)
    if not n:
        raise ValueError(f"Invalid employeeLevel {raw!r}; expected one of {sorted(EMPLOYEE_LEVELS)}")
    return n

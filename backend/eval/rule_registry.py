# AIQ-582 — rule_registry: effective-date windows for immigration rule versions.
"""
Maps rule version IDs to their effective date windows.

Usage:
    from eval.rule_registry import is_effective
    assert is_effective("DE_AUFENTHG_18G:2026", date(2026, 7, 1))
"""

from datetime import date
from typing import Optional, Tuple

# Maps rule_version_id -> (effective_from, effective_until)
# effective_until=None means the rule is still in force.
RULE_EFFECTIVE_WINDOWS: dict = {
    "DE_AUFENTHG_18G:2026": (date(2026, 1, 1), None),
    "DE_AUFENTHG_18B:2020": (date(2020, 3, 1), None),
    "DE_AUFENTHG_82:2019": (date(2019, 1, 1), None),
    "DE_AUFENTHG_27:2007": (date(2007, 1, 1), None),
    "DE_AUFENTHG_30:2007": (date(2007, 1, 1), None),
    "EU_DIR_2021_1883": (date(2023, 11, 18), None),
    "EU_DIR_2004_38_ART7:2004": (date(2004, 4, 29), None),
    "EU_DIR_2004_38_ART10:2004": (date(2004, 4, 29), None),
    "NO_EOS_UTLENDINGS:2010": (date(2010, 1, 1), None),
}


def is_effective(rule_version_id: str, on_date: date) -> bool:
    """Return True if rule_version_id is in force on on_date.

    Unknown rule IDs always return False.
    """
    window = RULE_EFFECTIVE_WINDOWS.get(rule_version_id)
    if window is None:
        return False
    effective_from, effective_until = window
    if on_date < effective_from:
        return False
    if effective_until is not None and on_date > effective_until:
        return False
    return True

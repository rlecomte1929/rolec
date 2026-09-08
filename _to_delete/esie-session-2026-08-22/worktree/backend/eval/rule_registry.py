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
    # Immigration rule versions for the France and Portugal work-permit routes
    # (US_FR, BR_PT corridors). Both routes were decided by Romain 2026-07-01;
    # the governing article numbers were verified against primary sources
    # (Légifrance for FR; AIMA + Diário da República for PT). Sub-article/route
    # choice is a product+legal decision, now made.
    # France — CESEDA art. L.421-26, "salarié détaché ICT" (intra-corporate
    # transferee, EU Directive 2014/66/EU): multi-year residence card for a
    # temporary intra-group transfer of a non-EU-resident employee.
    # ROUTE CONFIRMED by Romain 2026-07-01 (ICT secondment, NOT direct-hire
    # salarié / Blue Card / Passeport Talent). Article number CONFIRMED against
    # Légifrance (Article L421-26, en vigueur): recodified into force 2021-05-01
    # per Ord. 2020-1733 (16 Dec 2020).
    "FR_CESEDA_L421_26:2021": (date(2021, 5, 1), None),
    # Portugal — Lei n.º 23/2007 art. 88.º n.º 1, residence permit for subordinate
    # work where the assignee enters on a residence visa obtained abroad.
    # ROUTE CONFIRMED by Romain 2026-07-01 (art. 88.º n.º 1 "with residence visa",
    # NOT the visa-exempt n.º 2 / Blue Card / CPLP route). Sub-article n.º 1
    # corroborated by AIMA. Version tag :2024 reflects the consolidated text as
    # amended through DL 37-A/2024 (3 Jun 2024, revoked art. 88 n.º 2/n.º 6) and
    # Lei 40/2024; n.º 1 itself is longstanding and remains in force.
    "PT_LEI_23_2007_ART88_1:2024": (date(2024, 6, 3), None),
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

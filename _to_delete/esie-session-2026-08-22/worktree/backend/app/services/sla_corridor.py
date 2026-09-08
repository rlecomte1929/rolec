"""
I-3 Stage 4 — corridor-aware SLA thresholds for the HR command-center timeline.

App-layer bridge between the corridor registry (app/) and the pure, legacy
``backend/sla_rules.compute_sla_status`` (which must not import app/). The HR
command-center DB query injects ``sla_thresholds_for_corridor`` as a callback so
each row can resolve its corridor's at-risk window / % override; everything stays
fallback-safe — a corridor with no ``sla`` block yields None and the SLA function
keeps its module defaults.
"""
from __future__ import annotations

from typing import Optional, Tuple

from ...sla_rules import AT_RISK_PCT, AT_RISK_WINDOW_DAYS
from . import corridor_registry


def sla_thresholds_for_corridor(
    origin: Optional[str], destination: Optional[str]
) -> Optional[Tuple[int, int]]:
    """(at_risk_window_days, at_risk_pct) for a case's corridor, or None.

    None → the caller keeps the sla_rules module defaults. When a corridor
    declares an ``sla`` block, any field it omits is filled from the module
    default so a complete pair is always returned. Never raises.
    """
    try:
        if not origin or not destination:
            return None
        corridor = corridor_registry.normalize_corridor_id(f"{origin}_{destination}")
        cfg = corridor_registry.get_sla_config(corridor) if corridor else None
        if cfg is None:
            return None
        window = cfg.at_risk_window_days if cfg.at_risk_window_days is not None else AT_RISK_WINDOW_DAYS
        pct = cfg.at_risk_pct if cfg.at_risk_pct is not None else AT_RISK_PCT
        return int(window), int(pct)
    except Exception:  # noqa: BLE001 — never break the cockpit query
        return None

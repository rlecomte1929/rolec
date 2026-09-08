"""
Per-tier crawl cron config (AIQ-689 / P2-02a).

Defines the three freshness tiers and their crawl cadence. Tiers are the
scheduling dimension that turns the corridor data flywheel: critical sources
are re-crawled daily, stable Tier-1 sources weekly, Tier-2 sources monthly.

The crawl source registry tags every source with a ``trust_tier`` (T0..T3).
This module maps those trust tiers onto the three scheduling tiers and onto
deterministic cron expressions so the scheduler can seed one schedule per tier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# Scheduling tier identifiers (stored in crawl_schedules.crawl_tier).
TIER_1_CRITICAL = "tier-1-critical"
TIER_1_STABLE = "tier-1-stable"
TIER_2 = "tier-2"


@dataclass(frozen=True)
class TierConfig:
    """Cron config for a single freshness tier."""

    tier: str
    label: str
    cadence_days: int
    # Cron string used for the schedule. Staggered hours avoid a thundering
    # herd when multiple tiers come due on the same calendar day.
    cron_expression: str
    # trust_tier values (from the crawl source registry) that map to this tier.
    trust_tiers: List[str]


# Daily at 02:00, weekly Mon 03:00, monthly on the 1st at 04:00 (UTC).
TIER_CONFIGS: Dict[str, TierConfig] = {
    TIER_1_CRITICAL: TierConfig(
        tier=TIER_1_CRITICAL,
        label="Tier 1 — critical",
        cadence_days=1,
        cron_expression="0 2 * * *",
        trust_tiers=["T0"],
    ),
    TIER_1_STABLE: TierConfig(
        tier=TIER_1_STABLE,
        label="Tier 1 — stable",
        cadence_days=7,
        cron_expression="0 3 * * 1",
        trust_tiers=["T1"],
    ),
    TIER_2: TierConfig(
        tier=TIER_2,
        label="Tier 2",
        cadence_days=30,
        cron_expression="0 4 1 * *",
        trust_tiers=["T2", "T3"],
    ),
}

# Canonical ordering (highest cadence first) for deterministic iteration.
TIER_ORDER: List[str] = [TIER_1_CRITICAL, TIER_1_STABLE, TIER_2]


def get_tier_config(tier: str) -> Optional[TierConfig]:
    """Return the config for a scheduling tier, or None if unknown."""
    return TIER_CONFIGS.get(tier)


def tier_for_trust_tier(trust_tier: Optional[str]) -> str:
    """Map a source registry trust_tier (T0..T3) to a scheduling tier.

    Unknown / missing trust tiers fall back to the slowest cadence (tier-2) so
    that an unclassified source is still crawled, just conservatively.
    """
    tt = (trust_tier or "").strip().upper()
    for cfg in TIER_CONFIGS.values():
        if tt in cfg.trust_tiers:
            return cfg.tier
    return TIER_2


def schedule_name_for_tier(tier: str) -> str:
    """Deterministic, stable schedule name used to upsert the tier schedule."""
    return f"auto-tier::{tier}"

"""P2-08a (AIQ-702) — staleness helper with per-tier thresholds.

Pure-function shared truth for "is this data stale?" decisions, so the UI badge
and the backend alerts agree. Thresholds are per-rule-tier and come from the
``STALENESS_THRESHOLDS_DAYS`` env var (JSON), with hardcoded fallback defaults.

Mirrors ``frontend/src/utils/staleness.ts`` — same tier names, same defaults,
same "age in whole days >= threshold" semantics.

Env format (override the defaults)::

    STALENESS_THRESHOLDS_DAYS='{"tier1_critical": 30, "tier1_stable": 60, "tier2": 90}'

Tiers
-----
- ``tier1_critical`` — fast-moving, eligibility-critical rules (default 30 days).
- ``tier1_stable``   — stable Tier-1 rules (default 60 days).
- ``tier2``          — Tier-2 supporting rules (default 90 days).

Semantics
---------
``is_stale(last_updated, tier, now=None) -> bool`` returns True iff
``age_in_whole_days >= threshold_for_tier``. So at exactly ``N`` days old, the
record is the first day stale.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal, Mapping, Optional, Union

log = logging.getLogger(__name__)

Tier = Literal["tier1_critical", "tier1_stable", "tier2"]

DEFAULT_THRESHOLDS_DAYS: Mapping[Tier, int] = {
    "tier1_critical": 30,
    "tier1_stable": 60,
    "tier2": 90,
}

ENV_VAR = "STALENESS_THRESHOLDS_DAYS"


@dataclass(frozen=True)
class StalenessConfig:
    thresholds_days: Mapping[Tier, int]

    def threshold(self, tier: Tier) -> int:
        return self.thresholds_days[tier]


def _parse_env(raw: str) -> Optional[Mapping[Tier, int]]:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        log.warning("staleness: %s is not valid JSON; using defaults", ENV_VAR)
        return None
    if not isinstance(parsed, dict):
        log.warning("staleness: %s must be a JSON object; using defaults", ENV_VAR)
        return None
    result: dict = {}
    for tier in DEFAULT_THRESHOLDS_DAYS:
        if tier not in parsed:
            log.warning("staleness: %s missing tier %r; using default", ENV_VAR, tier)
            result[tier] = DEFAULT_THRESHOLDS_DAYS[tier]
            continue
        v = parsed[tier]
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            log.warning(
                "staleness: %s.%s must be a non-negative int (got %r); using default",
                ENV_VAR, tier, v,
            )
            result[tier] = DEFAULT_THRESHOLDS_DAYS[tier]
            continue
        result[tier] = v
    return result


def load_config(env: Optional[Mapping[str, str]] = None) -> StalenessConfig:
    """Build the staleness config from env. Safe to call repeatedly."""
    source = os.environ if env is None else env
    raw = source.get(ENV_VAR)
    if not raw:
        return StalenessConfig(thresholds_days=dict(DEFAULT_THRESHOLDS_DAYS))
    parsed = _parse_env(raw)
    if parsed is None:
        return StalenessConfig(thresholds_days=dict(DEFAULT_THRESHOLDS_DAYS))
    return StalenessConfig(thresholds_days=parsed)


# Module-level cache: read env once at import so callers don't re-parse.
_CONFIG = load_config()


def get_config() -> StalenessConfig:
    """Return the module-level config (env read at import)."""
    return _CONFIG


def _coerce_dt(value: Union[datetime, date, str]) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        # Accept ISO 8601 ("...Z" too).
        s = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    raise TypeError(f"unsupported last_updated type: {type(value).__name__}")


def is_stale(
    last_updated: Union[datetime, date, str],
    tier: Tier,
    now: Optional[Union[datetime, date]] = None,
    config: Optional[StalenessConfig] = None,
) -> bool:
    """Return True if ``last_updated`` is at least ``threshold(tier)`` whole days old.

    ``now`` is injectable for testing; defaults to UTC now. ``config`` is
    injectable to override the module-level (env-loaded) config.
    """
    cfg = config or _CONFIG
    if tier not in cfg.thresholds_days:
        raise ValueError(f"unknown tier: {tier!r}")

    updated_dt = _coerce_dt(last_updated)
    if now is None:
        now_dt: datetime = datetime.now(timezone.utc)
    else:
        now_dt = _coerce_dt(now)

    age_days = (now_dt - updated_dt).days  # whole-day floor; matches the FE
    return age_days >= cfg.threshold(tier)

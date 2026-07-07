"""autopilot_governor.py — the kill-switch + budget gate for the Feedback Autopilot.

Every autopilot stage (ingest / dispatch / fix / merge / cc-agent) calls ``gate(stage)``
before doing any billable work. Two independent controls, both fail-safe (default OFF /
pause), so the automation can never quietly run away:

  1. Flag kill-switch — ``AUTOPILOT_ENABLED`` master + a per-stage flag, resolved via
     ``feature_flags.resolve_flag_safe`` (DB ``feature_flags`` row → same-named env var →
     default False). Admins can flip it at runtime with no redeploy.
  2. Monthly USD ceiling — month-to-date autopilot spend (``policy_assistant_traces`` rows
     whose ``feature_key`` starts with ``autopilot.``) vs ``AUTOPILOT_MONTHLY_USD_CAP``.
     Reaching the cap halts spend. Fail-CLOSED: if spend can't be read, we pause (for a
     cost cap, "unknown spend" must mean "don't spend"), unlike the coordinator breaker
     which fails open to never block a user turn.

Per-night COUNT caps (dispatch/fixes/merges) are read here as env ints but ENFORCED by
each stage against that night's event count in Phase 1+. This module is additive and
unwired in Phase 0 — nothing calls ``gate()`` yet.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text

from ..db import SessionLocal
from .ai_unit_economics import _current_month_start
from .feature_flags import resolve_flag_safe

log = logging.getLogger(__name__)

# ── flags ────────────────────────────────────────────────────────────────────
MASTER_FLAG = "AUTOPILOT_ENABLED"
STAGE_FLAGS = {
    "ingest": "AUTOPILOT_INGEST_ENABLED",
    "dispatch": "AUTOPILOT_DISPATCH_ENABLED",
    "fix": "AUTOPILOT_FIX_ENABLED",
    "merge": "AUTOPILOT_MERGE_ENABLED",
    "cc": "AUTOPILOT_CC_ENABLED",
}

# ── budget ───────────────────────────────────────────────────────────────────
FEATURE_KEY_PREFIX = "autopilot."           # cost-trace feature_key namespace for all stages
BUDGET_CAP_ENV = "AUTOPILOT_MONTHLY_USD_CAP"
DEFAULT_MONTHLY_CAP_USD = 25.0
CC_NIGHTLY_CAP_ENV = "AUTOPILOT_CC_NIGHTLY_USD_CAP"   # the expensive Claude Code lane (Phase 3)
DEFAULT_CC_NIGHTLY_CAP_USD = 8.0

# ── per-night count caps (enforced by stages against tonight's event count) ──
NIGHTLY_CAPS = {
    "dispatch": ("AUTOPILOT_MAX_DISPATCH_PER_NIGHT", 40),
    "fixes": ("AUTOPILOT_MAX_FIXES_PER_NIGHT", 15),
    "merges": ("AUTOPILOT_MAX_MERGES_PER_NIGHT", 15),
    "cc_tasks": ("AUTOPILOT_MAX_CC_TASKS_PER_NIGHT", 3),
}


def stage_feature_key(stage: str) -> str:
    """Cost-trace feature_key for a stage, e.g. 'autopilot.dispatch'. Wrap every autopilot
    LLM call in TraceSession(feature_key=stage_feature_key(stage)) so spend is attributable."""
    return f"{FEATURE_KEY_PREFIX}{stage}"


def monthly_cap_usd() -> float:
    try:
        return float(os.getenv(BUDGET_CAP_ENV, "") or DEFAULT_MONTHLY_CAP_USD)
    except (TypeError, ValueError):
        return DEFAULT_MONTHLY_CAP_USD


def nightly_cap(name: str) -> int:
    """Per-night count cap (e.g. nightly_cap('fixes'))."""
    env_name, default = NIGHTLY_CAPS[name]
    try:
        return int(os.getenv(env_name, "") or default)
    except (TypeError, ValueError):
        return default


def month_to_date_spend_usd(session: Any = None) -> float:
    """Sum of month-to-date autopilot spend across all stages. Raises on DB error so the
    caller can fail CLOSED (unknown spend → pause). Portable SQL (SQLite + Postgres)."""
    own = session is None
    s = session or SessionLocal()
    try:
        row = s.execute(
            text(
                "SELECT COALESCE(SUM(cost_usd_estimated), 0) FROM policy_assistant_traces "
                "WHERE feature_key LIKE :pfx AND created_at >= :ms"
            ),
            {"pfx": f"{FEATURE_KEY_PREFIX}%", "ms": _current_month_start()},
        ).fetchone()
        return float((row[0] if row else 0) or 0.0)
    finally:
        if own:
            s.close()


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    spend_usd: float
    cap_usd: float

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.spend_usd)


def gate(stage: str, *, session: Any = None) -> GateDecision:
    """Master decision an autopilot stage checks before doing billable work.

    Order: master flag → per-stage flag → monthly budget. Fail-safe throughout
    (default OFF; unknown spend → pause).
    """
    cap = monthly_cap_usd()

    if not resolve_flag_safe(MASTER_FLAG, env_default=False):
        return GateDecision(False, "autopilot master flag off", 0.0, cap)

    stage_flag = STAGE_FLAGS.get(stage)
    if stage_flag is None:
        return GateDecision(False, f"unknown stage {stage!r}", 0.0, cap)
    if not resolve_flag_safe(stage_flag, env_default=False):
        return GateDecision(False, f"stage flag {stage_flag} off", 0.0, cap)

    try:
        spend = month_to_date_spend_usd(session=session)
    except Exception:  # fail-CLOSED: don't spend when spend is unknown
        log.warning("autopilot_governor: month-to-date spend unreadable — pausing (fail-closed)")
        return GateDecision(False, "month-to-date spend unreadable (fail-closed)", 0.0, cap)

    if spend >= cap:
        return GateDecision(False, f"monthly budget reached (${spend:.2f} ≥ ${cap:.2f})", spend, cap)

    return GateDecision(True, "ok", spend, cap)

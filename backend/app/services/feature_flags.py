"""P2-01a — backend-native feature flags (DB-backed, no redeploy to toggle).

Establishes the pattern for gating backend behaviour behind a flag scoped to an
allowlist of selected accounts. The first consumer is the live AI EEA roadmap
(`LIVE_EEA_ROADMAP_FLAG`), gated in `cases_read.get_case_roadmap`.

A flag is active for an account only when the flag row is `enabled` AND the
account is present in `feature_flag_accounts` — i.e. "selected test accounts
initially". Absent flag or empty account → not active (fail-closed).
"""
from __future__ import annotations

import os
from typing import Optional

from ..db import SessionLocal
from ..models import FeatureFlag, FeatureFlagAccount

# The live EEA roadmap (France → Norway first) gate — see P2-01 (AIQ-203).
LIVE_EEA_ROADMAP_FLAG = "live_eea_roadmap"


def is_flag_enabled_for(
    account_id: str,
    key: str = LIVE_EEA_ROADMAP_FLAG,
    *,
    db: Optional[object] = None,
) -> bool:
    """True iff `key` is enabled and `account_id` is on its allowlist.

    Pass `db` to reuse an open Session; otherwise a short-lived one is opened.
    """
    if not account_id:
        return False
    if db is not None:
        return _check(db, account_id, key)
    with SessionLocal() as session:
        return _check(session, account_id, key)


def _check(db, account_id: str, key: str) -> bool:
    flag = db.get(FeatureFlag, key)
    if flag is None or not flag.enabled:
        return False
    return db.get(FeatureFlagAccount, (key, account_id)) is not None


def _env_truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def resolve_flag(
    key: str,
    account_id: Optional[str] = None,
    *,
    env_default: bool = False,
    db: Optional[object] = None,
) -> bool:
    """Unified flag resolution: **DB flag wins, else the same-named env var, else default.**

    - A DB `feature_flags` row that is `enabled`: active globally when no `account_id`
      is given, or account-scoped when one is (allowlist via `feature_flag_accounts`).
      A disabled row is off.
    - No DB row → fall back to `os.getenv(key)` (the existing ~80-toggle convention),
      else `env_default`.

    Additive — does NOT touch `is_flag_enabled_for` or any existing `os.getenv` site;
    lets env toggles migrate to DB-managed flags one at a time without code churn.
    """

    def _resolve(session) -> bool:
        flag = session.get(FeatureFlag, key)
        if flag is not None:
            if not flag.enabled:
                return False
            if account_id is None:
                return True  # enabled global flag
            return session.get(FeatureFlagAccount, (key, account_id)) is not None
        env = os.getenv(key)
        if env is not None:
            return _env_truthy(env)
        return bool(env_default)

    if db is not None:
        return _resolve(db)
    with SessionLocal() as session:
        return _resolve(session)


def resolve_flag_safe(key: str, *, env_default: bool = False) -> bool:
    """Like `resolve_flag` but never raises: on any DB error, fall back to the
    same-named env var (then `env_default`).

    For flag checks on request paths that may run without a live DB (e.g. router
    unit tests that mount the router over a bare app, or a transient DB blip).
    A DB `feature_flags` row still wins when the DB is reachable — so admins get
    runtime control — but the check degrades to the pre-existing env behaviour
    instead of 500-ing when it isn't.
    """
    try:
        return resolve_flag(key, env_default=env_default)
    except Exception:  # pragma: no cover - defensive DB-unavailable fallback
        env = os.getenv(key)
        return _env_truthy(env) if env is not None else bool(env_default)

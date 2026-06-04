"""P2-01a — backend-native feature flags (DB-backed, no redeploy to toggle).

Establishes the pattern for gating backend behaviour behind a flag scoped to an
allowlist of selected accounts. The first consumer is the live AI EEA roadmap
(`LIVE_EEA_ROADMAP_FLAG`), gated in `cases_read.get_case_roadmap`.

A flag is active for an account only when the flag row is `enabled` AND the
account is present in `feature_flag_accounts` — i.e. "selected test accounts
initially". Absent flag or empty account → not active (fail-closed).
"""
from __future__ import annotations

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

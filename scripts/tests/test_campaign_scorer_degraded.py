"""Unit tests for the degraded-run guard in campaign_scorer.

When a campaign run coincides with a deploy window, environmental (ENV) failures pile
up. Such a run must NOT be scored GREEN (it's inconclusive, not healthy) and must file
NOTHING to the Work Queue. This guards Signal B (correlated environmental failure) and
the readiness marker (Phase 3). Pure functions — no I/O.
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import campaign_scorer as cs  # noqa: E402


def _per_test(statuses):
    return {f"T{i}": {"status": s, "points": cs.POINTS.get(s)} for i, s in enumerate(statuses)}


def test_env_is_non_scoring():
    # ENV must map to None points (excluded from denominator, never 'bad')
    assert cs.POINTS.get("ENV", "MISSING") is None


def test_count_env():
    pt = _per_test(["PASS", "ENV", "ENV", "FAIL", "SKIP"])
    assert cs.count_env(pt) == 2


def test_is_degraded_by_env_threshold():
    assert cs.is_degraded(env_count=cs.DEGRADED_ENV_THRESHOLD) is True
    assert cs.is_degraded(env_count=cs.DEGRADED_ENV_THRESHOLD - 1) is False


def test_is_degraded_forced_by_readiness_marker():
    # Phase 3 passes forced=True when the readiness gate reports the data path never warmed
    assert cs.is_degraded(env_count=0, forced=True) is True


def test_degraded_run_suppresses_all_candidates():
    cands = [{"test_id": "CORE-RLS", "priority": "P0"}, {"test_id": "PER-H1", "priority": "P0"}]
    assert cs.finalize_candidates(cands, degraded=True) == []
    assert cs.finalize_candidates(cands, degraded=False) == cands


def test_degraded_band_is_inconclusive():
    band, _msg = cs.degraded_band()
    assert band == "INCONCLUSIVE"

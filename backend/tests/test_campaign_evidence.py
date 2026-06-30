"""
H4 · Tests for scripts/build_campaign_evidence.py.

The evidence builder distils a scorer report into a committable, sanitized
per-category summary so a campaign's headline score is reproducible from the repo
rather than only self-reported in campaigns.json. These tests pin:
  - the recomputed overall score agrees with the scorer's reported score
    (the self-validating property the artifact exists to provide), and
  - PII/token scrubbing on the defense-in-depth path.

Standalone script under scripts/ (no package) — add the dir to sys.path and import
by module name.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_campaign_evidence as bce  # noqa: E402


def _report(per_test, **extra):
    base = {
        "current_file": "results/test_results_x.json",
        "scorer_version": "1.1",
        "health_band": "GREEN",
        "overall_score": extra.pop("overall_score", 100.0),
        "current_summary": {"total": len(per_test), "pass": len(per_test), "fail": 0},
        "per_test": per_test,
        "regressions": [],
        "fixed": [],
        "new_failures": [],
    }
    base.update(extra)
    return base


def test_recomputed_score_matches_reported_all_pass():
    per_test = {
        "AT1": {"status": "PASS", "domain": "Authentication", "priority": "P0"},
        "CM1": {"status": "PASS", "domain": "Case Management", "priority": "P0"},
    }
    ev = bce.build_evidence(_report(per_test, overall_score=100.0))
    assert ev["overall_score_recomputed"] == 100.0
    assert ev["overall_score_matches"] is True
    assert ev["test_totals_by_status"]["PASS"] == 2
    assert ev["categories"]["Authentication"]["score_pct"] == 100.0


def test_recomputed_score_reflects_mixed_statuses():
    # One domain weight 4 at 50% (1 PASS, 1 FAIL), one weight 1 at 100%.
    per_test = {
        "A1": {"status": "PASS", "domain": "Authentication", "priority": "P0"},
        "A2": {"status": "FAIL", "domain": "Authentication", "priority": "P0"},
        "AD1": {"status": "PASS", "domain": "Admin Console", "priority": "P1"},
    }
    ev = bce.build_evidence(_report(per_test, overall_score=60.0))
    # weighted: (50*4 + 100*1) / 5 = 60.0
    assert ev["overall_score_recomputed"] == 60.0
    assert ev["categories"]["Authentication"]["counts"]["FAIL"] == 1


def test_skip_excluded_from_denominator():
    per_test = {
        "A1": {"status": "PASS", "domain": "Authentication", "priority": "P0"},
        "S1": {"status": "SKIP", "domain": "Suppliers & Vendors", "priority": "P2"},
    }
    ev = bce.build_evidence(_report(per_test))
    # SKIP-only domain is unscored (score_pct None) and dropped from the weighted mean.
    assert ev["categories"]["Suppliers & Vendors"]["score_pct"] is None
    assert ev["overall_score_recomputed"] == 100.0


def test_scrub_redacts_email_and_token():
    assert "[redacted-email]" in bce._scrub("login as hr@company.test now")
    assert "alice@x.io" not in bce._scrub("alice@x.io")
    token = "abcdefghijklmnopqrstuvwxyz123456.signaturepart"
    assert "[redacted-token]" in bce._scrub(f"Bearer {token}")


def test_evidence_is_deterministic_and_carries_digest():
    per_test = {"A1": {"status": "PASS", "domain": "Authentication", "priority": "P0"}}
    a = bce.build_evidence(_report(per_test))
    b = bce.build_evidence(_report(per_test))
    assert a["evidence_sha256"] == b["evidence_sha256"]
    assert len(a["evidence_sha256"]) == 64

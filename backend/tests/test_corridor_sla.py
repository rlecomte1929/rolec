"""
I-3 Stage 4 — per-corridor timeline-SLA tunables.

Covers the parameterized pure SLA rule (override window / pct, defaults
preserved), the registry `sla` block parsing, and the app-layer resolver that
bridges the registry to the legacy sla_rules function. Fallback-safe: no `sla`
block → module defaults.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.sla_rules import AT_RISK_PCT, AT_RISK_WINDOW_DAYS, compute_sla_status  # noqa: E402
from backend.app.services import corridor_registry as reg  # noqa: E402
from backend.app.services.sla_corridor import sla_thresholds_for_corridor  # noqa: E402

_TODAY = date(2026, 1, 1)


def _set_registry_dir(case, tmp):
    prev = os.environ.get("CORRIDOR_REGISTRY_DIR")
    os.environ["CORRIDOR_REGISTRY_DIR"] = tmp
    reg._reset_cache_for_tests()

    def restore():
        reg._reset_cache_for_tests()
        if prev is None:
            os.environ.pop("CORRIDOR_REGISTRY_DIR", None)
        else:
            os.environ["CORRIDOR_REGISTRY_DIR"] = prev
    case.addCleanup(restore)


def _write(tmp, cid, body):
    d = os.path.join(tmp, cid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "corridor.yaml"), "w", encoding="utf-8") as f:
        f.write(body)


# --------------------------------------------------------------------------- #
# Parameterized pure SLA rule                                                 #
# --------------------------------------------------------------------------- #
class ComputeSlaOverrideTests(unittest.TestCase):
    def test_defaults_unchanged_when_no_override(self):
        # 40 days out, 0% done → beyond the default 30-day window → on_track.
        self.assertEqual(
            compute_sla_status("2026-02-10", 0, "active", today=_TODAY),
            ("on_track", 40),
        )

    def test_wider_window_flips_to_at_risk(self):
        # Same case, but a corridor with a 60-day window → at_risk.
        self.assertEqual(
            compute_sla_status("2026-02-10", 0, "active", today=_TODAY,
                               at_risk_window_days=60),
            ("at_risk", 40),
        )

    def test_lower_pct_threshold_flips_to_on_track(self):
        # 10 days out, 50% done: default pct=80 → at_risk; pct=40 → on_track.
        self.assertEqual(
            compute_sla_status("2026-01-11", 50, "active", today=_TODAY),
            ("at_risk", 10),
        )
        self.assertEqual(
            compute_sla_status("2026-01-11", 50, "active", today=_TODAY, at_risk_pct=40),
            ("on_track", 10),
        )

    def test_none_overrides_equal_module_constants(self):
        self.assertEqual(
            compute_sla_status("2026-01-20", 0, "active", today=_TODAY),
            compute_sla_status("2026-01-20", 0, "active", today=_TODAY,
                               at_risk_window_days=AT_RISK_WINDOW_DAYS, at_risk_pct=AT_RISK_PCT),
        )


# --------------------------------------------------------------------------- #
# Registry sla parsing                                                        #
# --------------------------------------------------------------------------- #
class SlaConfigParsingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _set_registry_dir(self, self.tmp)

    def test_sla_block_parsed(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  sla:\n    at_risk_window_days: 45\n    at_risk_pct: 70\n")
        cfg = reg.get_sla_config("XX_YY")
        self.assertEqual((cfg.at_risk_window_days, cfg.at_risk_pct), (45, 70))

    def test_partial_block_keeps_other_none(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  sla:\n    at_risk_window_days: 45\n")
        cfg = reg.get_sla_config("XX_YY")
        self.assertEqual(cfg.at_risk_window_days, 45)
        self.assertIsNone(cfg.at_risk_pct)

    def test_absent_sla_is_none(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n")
        self.assertIsNone(reg.get_sla_config("XX_YY"))


class RealFrNoSlaTests(unittest.TestCase):
    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def test_fr_no_declares_default_mirroring_sla(self):
        cfg = reg.get_sla_config("FR_NO")
        self.assertIsNotNone(cfg)
        self.assertEqual((cfg.at_risk_window_days, cfg.at_risk_pct), (30, 80))


# --------------------------------------------------------------------------- #
# App-layer resolver                                                          #
# --------------------------------------------------------------------------- #
class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _set_registry_dir(self, self.tmp)

    def test_resolves_full_pair_from_partial_block(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  sla:\n    at_risk_window_days: 60\n")
        # Missing pct filled from module default.
        self.assertEqual(sla_thresholds_for_corridor("XX", "YY"), (60, AT_RISK_PCT))

    def test_no_block_returns_none(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n")
        self.assertIsNone(sla_thresholds_for_corridor("XX", "YY"))

    def test_unknown_corridor_or_missing_geo_returns_none(self):
        self.assertIsNone(sla_thresholds_for_corridor("ZZ", "QQ"))
        self.assertIsNone(sla_thresholds_for_corridor("FR", None))
        self.assertIsNone(sla_thresholds_for_corridor(None, "NO"))


if __name__ == "__main__":
    unittest.main()

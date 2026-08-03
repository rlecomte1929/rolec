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


# --------------------------------------------------------------------------- #
# AIQ-1750 / AIQ-1753 — permit-first SLA windows, against the REAL committed     #
# registry. Every permit corridor runs on its own derived pre-arrival runway;    #
# free movement keeps the module defaults.                                       #
# --------------------------------------------------------------------------- #

# (corridor_id, pathway_id, origin, destination) for the corridors whose graphs
# carry a real pre-arrival chain. Free movement roots AT arrival, so it has none.
_PERMIT_CORRIDORS = (
    ("ES_IE", "CSEP_2026", "ES", "IE"),
    ("IN_DE", "BLUECARD_2026", "IN", "DE"),
)


class PermitCorridorSlaWindowTests(unittest.TestCase):
    """Permit corridors run on their own pre-arrival runway; free movement doesn't."""

    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def test_permit_windows_match_their_derived_pre_arrival_runway(self):
        from backend.relopass.corridors import load_corridor
        from backend.relopass.corridors.feasibility import required_lead_time_days

        for corridor_id, pathway_id, origin, dest in _PERMIT_CORRIDORS:
            path = reg.get_pathway_file(corridor_id, pathway_id)
            self.assertIsNotNone(path, f"{corridor_id}/{pathway_id} did not resolve")
            derived = required_lead_time_days(load_corridor(path).step_graph)

            resolved = sla_thresholds_for_corridor(origin, dest)
            self.assertIsNotNone(resolved, f"{corridor_id} declares no sla block")
            window, pct = resolved
            self.assertEqual(
                window, derived,
                f"{corridor_id}'s at_risk_window_days has drifted from its step "
                f"graph — re-derive it with required_lead_time_days rather than "
                f"hand-editing.",
            )
            self.assertGreater(window, AT_RISK_WINDOW_DAYS)  # materially wider than 30
            self.assertEqual(pct, AT_RISK_PCT)

    def test_free_movement_corridors_keep_the_module_defaults(self):
        # Named explicitly in AIQ-1750's Validation Criteria as the no-regression
        # check. Asserted for every free-movement corridor, not just FR_NO / ES_NL.
        for origin, dest in (
            ("FR", "NO"), ("ES", "NL"), ("DE", "NO"), ("FR", "CH"),
            ("FR", "DE"), ("FR", "ES"), ("FR", "NL"), ("NO", "FR"),
        ):
            self.assertEqual(
                sla_thresholds_for_corridor(origin, dest),
                (AT_RISK_WINDOW_DAYS, AT_RISK_PCT),
                f"{origin}->{dest} SLA window changed; only permit corridors differ",
            )

    def test_in_de_flags_at_risk_where_the_old_window_reported_on_track(self):
        # IN_DE's runway (158d) is the longest of any corridor — longer than ES_IE's
        # 104 — so a case 90 days out was the most badly mis-reported of all.
        move = date(2026, 4, 1)  # 90 days after _TODAY
        new_window = sla_thresholds_for_corridor("IN", "DE")
        self.assertIsNotNone(new_window)

        old_status, _ = compute_sla_status(
            move, 10, "in_progress", today=_TODAY,
            at_risk_window_days=AT_RISK_WINDOW_DAYS, at_risk_pct=AT_RISK_PCT,
        )
        new_status, _ = compute_sla_status(
            move, 10, "in_progress", today=_TODAY,
            at_risk_window_days=new_window[0], at_risk_pct=new_window[1],
        )
        self.assertEqual(old_status, "on_track")
        self.assertEqual(new_status, "at_risk")

    def test_es_ie_flags_at_risk_where_the_old_window_reported_on_track(self):
        # 60 days out, 10% done. Under the old 30-day window this was 'on_track';
        # under the derived window it is correctly 'at_risk'.
        move = date(2026, 3, 2)  # 60 days after _TODAY
        old_window = (AT_RISK_WINDOW_DAYS, AT_RISK_PCT)
        new_window = sla_thresholds_for_corridor("ES", "IE")

        old_status, _ = compute_sla_status(
            move, 10, "in_progress", today=_TODAY,
            at_risk_window_days=old_window[0], at_risk_pct=old_window[1],
        )
        new_status, _ = compute_sla_status(
            move, 10, "in_progress", today=_TODAY,
            at_risk_window_days=new_window[0], at_risk_pct=new_window[1],
        )
        self.assertEqual(old_status, "on_track")
        self.assertEqual(new_status, "at_risk")


if __name__ == "__main__":
    unittest.main()

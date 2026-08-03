"""
I-3 Stage 5 — eligibility pathways folded under the corridor identity.

The eligibility Corridor Agent spec now lives at
corridors/IN_DE/pathways/BLUECARD_2026/v1.yaml, declared by the IN_DE registry
profile. The registry is the single source for where a pathway file lives; the
dependency-free loader loads the resolved path.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import corridor_registry as reg  # noqa: E402
from backend.relopass.corridors import load_corridor  # noqa: E402


class RealInDePathwaysTests(unittest.TestCase):
    """Against the committed corridors/IN_DE/ profile (no registry override)."""

    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def test_in_de_declares_bluecard_pathway(self):
        pathways = reg.get_pathways("IN_DE")
        self.assertEqual(len(pathways), 1)
        self.assertEqual(pathways[0].id, "BLUECARD_2026")
        self.assertEqual(pathways[0].file, "pathways/BLUECARD_2026/v1.yaml")

    def test_in_de_listed_as_corridor(self):
        self.assertIn("IN_DE", reg.list_corridors())

    def test_pathway_file_resolves_and_loads_via_eligibility_loader(self):
        path = reg.get_pathway_file("IN_DE", "BLUECARD_2026")
        self.assertIsNotNone(path)
        self.assertTrue(path.is_file())
        # The dependency-free loader loads the registry-resolved path; the
        # pathway's internal corridor_id is preserved (it keys rce.* rows).
        corridor = load_corridor(path)
        self.assertEqual(corridor.corridor_id, "IN_DE_BLUECARD_2026")

    def test_unknown_pathway_or_corridor_is_none(self):
        self.assertIsNone(reg.get_pathway_file("IN_DE", "NOPE"))
        self.assertIsNone(reg.get_pathway_file("ZZ_QQ", "BLUECARD_2026"))
        self.assertEqual(reg.get_pathways("ZZ_QQ"), ())


class PathwayParsingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._prev = os.environ.get("CORRIDOR_REGISTRY_DIR")
        os.environ["CORRIDOR_REGISTRY_DIR"] = self.tmp
        reg._reset_cache_for_tests()

        def restore():
            reg._reset_cache_for_tests()
            if self._prev is None:
                os.environ.pop("CORRIDOR_REGISTRY_DIR", None)
            else:
                os.environ["CORRIDOR_REGISTRY_DIR"] = self._prev
        self.addCleanup(restore)

    def _write(self, cid, body):
        d = os.path.join(self.tmp, cid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "corridor.yaml"), "w", encoding="utf-8") as f:
            f.write(body)

    def test_absent_pathways_is_empty_tuple(self):
        self._write("XX_YY", "corridor:\n  id: XX_YY\n")
        self.assertEqual(reg.get_pathways("XX_YY"), ())

    def test_malformed_entries_skipped(self):
        self._write("XX_YY",
                    "corridor:\n  id: XX_YY\n  pathways:\n"
                    "    - id: GOOD\n      file: pathways/g/v1.yaml\n"
                    "    - id: ''\n      file: bad.yaml\n"
                    "    - notamapping\n")
        pw = reg.get_pathways("XX_YY")
        self.assertEqual([p.id for p in pw], ["GOOD"])

    def test_missing_file_resolves_none(self):
        self._write("XX_YY",
                    "corridor:\n  id: XX_YY\n  pathways:\n    - id: P1\n      file: pathways/p1/v1.yaml\n")
        self.assertIsNone(reg.get_pathway_file("XX_YY", "P1"))  # declared but no file on disk


# AIQ-1747 — the arrival anchor marks where the PRE-arrival runway ends. Downstream
# feasibility work measures the longest path to it, so exactly one step per pathway
# must carry it, and it must be the SEMANTICALLY right step: step-id spelling is not
# a safe proxy (NO_FR anchors on A0_DEPART_NO, and IN_DE's graph roots at
# ZAB_STATEMENT, so a TRAVEL_TO_* prefix match would mis-anchor both).
_EXPECTED_ARRIVAL_ANCHOR = {
    "DE_NO": "TRAVEL_TO_NO",
    "ES_IE": "TRAVEL_TO_IE",
    "ES_NL": "TRAVEL_TO_NL",
    "FR_CH": "TRAVEL_TO_CH",
    "FR_DE": "TRAVEL_TO_DE",
    "FR_ES": "TRAVEL_TO_ES",
    "FR_NL": "TRAVEL_TO_NL",
    "FR_NO": "TRAVEL_TO_NO",
    "IN_DE": "TRAVEL_TO_DE",
    # No "arrive in France" step exists: a returning citizen needs no visa, permit
    # or registration, so departure IS the move and the runway is legitimately zero.
    "NO_FR": "A0_DEPART_NO",
}


class ArrivalAnchorTests(unittest.TestCase):
    """Every committed pathway declares exactly one arrival_anchor step."""

    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def _load_all(self):
        for corridor_id in _EXPECTED_ARRIVAL_ANCHOR:
            pathways = reg.get_pathways(corridor_id)
            self.assertTrue(pathways, f"{corridor_id} declares no pathways")
            for pathway in pathways:
                path = reg.get_pathway_file(corridor_id, pathway.id)
                self.assertIsNotNone(path, f"{corridor_id}/{pathway.id} did not resolve")
                yield corridor_id, load_corridor(path)

    def test_every_pathway_declares_exactly_one_anchor(self):
        seen = set()
        for corridor_id, corridor in self._load_all():
            anchors = [s.step_id for s in corridor.step_graph if s.arrival_anchor]
            self.assertEqual(
                len(anchors), 1,
                f"{corridor_id} declares {len(anchors)} arrival_anchor steps: {anchors}",
            )
            seen.add(corridor_id)
        self.assertEqual(seen, set(_EXPECTED_ARRIVAL_ANCHOR), "a corridor was not covered")

    def test_anchor_is_the_semantically_correct_step(self):
        for corridor_id, corridor in self._load_all():
            anchor = next(s for s in corridor.step_graph if s.arrival_anchor)
            self.assertEqual(
                anchor.step_id, _EXPECTED_ARRIVAL_ANCHOR[corridor_id],
                f"{corridor_id} anchored on {anchor.step_id}",
            )

    def test_unmarked_steps_default_to_false(self):
        for corridor_id, corridor in self._load_all():
            for step in corridor.step_graph:
                if step.step_id != _EXPECTED_ARRIVAL_ANCHOR[corridor_id]:
                    self.assertIs(
                        step.arrival_anchor, False,
                        f"{corridor_id}.{step.step_id} should default to False",
                    )


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

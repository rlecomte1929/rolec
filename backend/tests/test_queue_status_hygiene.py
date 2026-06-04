"""
Unit tests for scripts/check_queue_status_hygiene.py (HYGIENE-2).

Pure-Python, no network: exercises the tag parser and the find_false_ready
logic with synthetic queue records. The regression fixture proves the guard
WOULD flag the P3-01d / FU3 false-ready cases (Ready for AI while a dependency
is not Done) that motivated this guard.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# scripts/ is not a package — load the module directly by path.
_spec = importlib.util.spec_from_file_location(
    "check_queue_status_hygiene",
    _REPO_ROOT / "scripts" / "check_queue_status_hygiene.py",
)
qsh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qsh)


class ParseTitleTagTests(unittest.TestCase):
    def test_dot_separator_form(self):
        self.assertEqual(qsh.parse_title_tag("P3-01d · Build outcome evaluator"), "P3-01D")

    def test_bracket_form(self):
        self.assertEqual(qsh.parse_title_tag("[P1-3] Trigger Engine"), "P1-3")

    def test_followup_form(self):
        self.assertEqual(qsh.parse_title_tag("P3-01b-FU3 · Run baseline"), "P3-01B-FU3")

    def test_no_tag_returns_none(self):
        self.assertIsNone(qsh.parse_title_tag("Some untagged task"))


class ParseDependencyTagsTests(unittest.TestCase):
    def test_single_tag(self):
        self.assertEqual(qsh.parse_dependency_tags("P1-07"), ["P1-07"])

    def test_comma_list_with_prose(self):
        self.assertEqual(
            qsh.parse_dependency_tags("P3-01a, P1-01c (real verifier)"),
            ["P3-01A", "P1-01C"],
        )

    def test_deduped_and_ordered(self):
        self.assertEqual(
            qsh.parse_dependency_tags("needs P2-06d then P2-06d again, plus P3-01b-FU1"),
            ["P2-06D", "P3-01B-FU1"],
        )

    def test_none_yields_empty(self):
        self.assertEqual(qsh.parse_dependency_tags("none"), [])


class FindFalseReadyTests(unittest.TestCase):
    def _tasks(self):
        return [
            {"tag": "P1-07", "title": "P1-07 · Outcome pipeline", "aiq": "AIQ-1",
             "url": "u1", "status": "Ready for AI", "dependencies": "none"},
            {"tag": "P3-01D", "title": "P3-01d · Outcome evaluator", "aiq": "AIQ-710",
             "url": "u2", "status": "Ready for AI", "dependencies": "P1-07"},
            {"tag": "P3-01A", "title": "P3-01a · Golden set", "aiq": "AIQ-707",
             "url": "u3", "status": "Done", "dependencies": "none"},
            {"tag": "P3-01B", "title": "P3-01b · Precision eval", "aiq": "AIQ-708",
             "url": "u4", "status": "Ready for AI", "dependencies": "P3-01a"},
        ]

    def test_flags_ready_task_with_not_done_dependency(self):
        flagged = qsh.find_false_ready(self._tasks(), allowlist=set())
        tags = {f["tag"] for f in flagged}
        # P3-01D depends on P1-07 (Ready for AI, not Done) → flagged.
        self.assertIn("P3-01D", tags)
        # P3-01B depends on P3-01A which IS Done → not flagged.
        self.assertNotIn("P3-01B", tags)
        # P1-07 has no deps → not flagged.
        self.assertNotIn("P1-07", tags)

    def test_unmet_reason_carries_dependency_status(self):
        flagged = qsh.find_false_ready(self._tasks(), allowlist=set())
        p301d = next(f for f in flagged if f["tag"] == "P3-01D")
        self.assertEqual(p301d["unmet"], ["P1-07 [Ready for AI]"])

    def test_unknown_dependency_tag_is_ignored(self):
        tasks = [
            {"tag": "P9-99", "title": "P9-99 · x", "aiq": "AIQ-9", "url": "u",
             "status": "Ready for AI", "dependencies": "P0-00"},  # P0-00 not in queue
        ]
        self.assertEqual(qsh.find_false_ready(tasks, allowlist=set()), [])

    def test_allowlist_suppresses_whole_task(self):
        flagged = qsh.find_false_ready(self._tasks(), allowlist={"P3-01D"})
        self.assertNotIn("P3-01D", {f["tag"] for f in flagged})

    def test_allowlist_suppresses_single_edge(self):
        flagged = qsh.find_false_ready(self._tasks(), allowlist={"P3-01D:P1-07"})
        self.assertNotIn("P3-01D", {f["tag"] for f in flagged})

    def test_non_ready_tasks_not_flagged(self):
        tasks = [
            {"tag": "P1-07", "title": "x", "aiq": "1", "url": "u",
             "status": "Done", "dependencies": "none"},
            {"tag": "P3-01D", "title": "y", "aiq": "2", "url": "u",
             "status": "Blocked", "dependencies": "P1-07"},  # already Blocked → ok
        ]
        self.assertEqual(qsh.find_false_ready(tasks, allowlist=set()), [])


class LoadAllowlistTests(unittest.TestCase):
    def test_comment_aware(self, ):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "al.txt"
            p.write_text("# header\nP3-01D  # blocked on data, tracked manually\n\nP5-2:P5-1\n")
            self.assertEqual(qsh.load_allowlist(p), {"P3-01D", "P5-2:P5-1"})

    def test_missing_file_is_empty(self):
        self.assertEqual(qsh.load_allowlist(Path("/nonexistent/al.txt")), set())


if __name__ == "__main__":
    unittest.main()

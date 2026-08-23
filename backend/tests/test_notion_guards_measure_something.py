"""The Notion guards must never report a pass on a queue they did not read.

WHAT HAPPENED. On 2026-08-23 both `check_queue_status_hygiene.py` and
`check_deliverable_integrity.py` were reporting **pass** on every PR while examining nothing.
The CI job log said so plainly:

    Queue status hygiene   NOTION_TOKEN: ***
    Queue status hygiene   [WARN] Notion query failed (HTTP Error 404: Not Found); skipping (exit 0).

`vars.NOTION_QUEUE_TOKEN_SET` was `true`, the jobs ran, the integration had never been given
access to the database, and both scripts turned every Notion error into `return 0`. Two
`--strict` guards, green, blind.

Behind that sat a second defect that would have survived fixing the token: all three Notion
scripts read `props.get("Task Title")`, but this database's title property is **`fable`**.
`check_queue_status_hygiene` would have fetched rows, got `title == ""` for every one, and
`parse_title_tag` would have returned None for all of them — leaving `status_by_tag` empty so
that NO dependency edge could ever resolve. It would have gone from measuring nothing to
measuring half of nothing, still green.

`backend/tests/test_notion_work_queue_target.py` already pins `fable` for the WRITE path. This
file pins it for the READ path, and pins the exit-code contract that makes an unmeasurable run
visible.

THE CONTRACT
    exit 0 — measured, clean
    exit 1 — measured, a violation was found (with --strict)
    exit 3 — DID NOT MEASURE (no token / no access / unreachable / schema drift)

Exit 3 is the whole point: 0 and 3 used to be the same value.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_deliverable_integrity as deliverable  # noqa: E402
import check_queue_status_hygiene as hygiene  # noqa: E402
import notion_ready_queue as reader  # noqa: E402


def _title_prop(text: str) -> dict:
    """A Notion `title` property as the REST API returns it."""
    return {"id": "title", "type": "title", "title": [{"plain_text": text}]}


class TheTitlePropertyIsFable(unittest.TestCase):
    """All three readers must look up `fable`. This is the drift that went unnoticed."""

    def test_hygiene_reads_fable(self):
        self.assertEqual(hygiene._rich_text(_title_prop("AIQ-1 something")), "AIQ-1 something")

    def test_reader_reads_fable(self):
        self.assertEqual(reader._plain_text(_title_prop("AIQ-2 other")), "AIQ-2 other")

    def test_task_title_is_not_a_property_of_this_database(self):
        """Documents WHY the old key was wrong, so nobody reintroduces it.

        A page's `properties` dict is keyed by property NAME. Asking for a name that does not
        exist yields None, and every extractor turns None into "" — silently, with no error.
        That silence is the entire bug.
        """
        props = {"fable": _title_prop("the real title")}
        self.assertIsNone(props.get("Task Title"))
        self.assertEqual(hygiene._rich_text(props.get("Task Title")), "")
        self.assertEqual(reader._plain_text(props.get("Task Title")), "")
        self.assertEqual(hygiene._rich_text(props.get("fable")), "the real title")

    def test_the_CALL_SITE_reads_fable_not_just_the_helper(self):
        """The assertion that actually catches the drift.

        An earlier version of this file tested `_rich_text` with a property handed to it
        directly. That passes whichever key the call site looks up, so reverting
        `fable` -> `Task Title` left all of it green — a test that documented the bug
        without detecting it, which is the very failure mode this whole change is about.
        `extract_task` was made pure so the lookup itself could be pinned.
        """
        page = {
            "url": "https://notion.so/x",
            "properties": {
                "fable": _title_prop("[P1-1] the real title"),
                "Status": {"select": {"name": "Ready for AI"}},
                "Dependencies": {"rich_text": [{"plain_text": "[P1-0]"}]},
                "Execution Notes": {"rich_text": [{"plain_text": "notes"}]},
            },
        }
        row = hygiene.extract_task(page)
        self.assertEqual(row["title"], "[P1-1] the real title")
        self.assertEqual(row["tag"], "P1-1", "the tag is derived from the title — no title, no tag")

    def test_the_call_site_yields_nothing_when_pointed_at_a_missing_property(self):
        """Same page, but the title stored under the OLD key. This is what CI was reading."""
        page = {
            "url": "",
            "properties": {
                "Task Title": _title_prop("[P1-1] the real title"),
                "Status": {"select": {"name": "Ready for AI"}},
            },
        }
        row = hygiene.extract_task(page)
        self.assertEqual(row["title"], "")
        self.assertIsNone(row["tag"])

    def test_an_empty_title_makes_every_dependency_edge_unresolvable(self):
        """The mechanism, pinned. Empty titles → no tags → no edges → vacuous PASS."""
        self.assertIsNone(hygiene.parse_title_tag(""))
        tasks = [
            {"tag": hygiene.parse_title_tag(""), "title": "", "aiq": "AIQ-1", "url": "",
             "status": "Ready for AI", "dependencies": "[P1-1]", "notes": ""},
            {"tag": hygiene.parse_title_tag(""), "title": "", "aiq": "AIQ-2", "url": "",
             "status": "Ready for AI", "dependencies": "", "notes": ""},
        ]
        # With no resolvable tags the guard finds nothing — which is exactly how it passed.
        self.assertEqual(hygiene.find_false_ready(tasks, set()), [])


class ADegenerateScanIsNotAPass(unittest.TestCase):
    """`assert_non_degenerate` is the canary neither guard had."""

    def _rows(self, n, *, title="AIQ-1 t", status="Done", notes="x"):
        return [{"tag": None, "title": title, "aiq": f"AIQ-{i}", "url": "",
                 "status": status, "dependencies": "", "notes": notes} for i in range(n)]

    def test_too_few_rows_raises(self):
        with self.assertRaises(hygiene.QueueUnavailable) as ctx:
            hygiene.assert_non_degenerate(self._rows(10))
        self.assertEqual(ctx.exception.kind, "schema-drift")

    def test_rows_but_no_titles_raises_naming_the_likely_cause(self):
        """The exact shape a property rename produces."""
        with self.assertRaises(hygiene.QueueUnavailable) as ctx:
            hygiene.assert_non_degenerate(self._rows(2000, title=""))
        self.assertIn("fable", ctx.exception.detail)

    def test_rows_but_no_status_raises(self):
        with self.assertRaises(hygiene.QueueUnavailable):
            hygiene.assert_non_degenerate(self._rows(2000, status=""))

    def test_a_healthy_scan_passes(self):
        hygiene.assert_non_degenerate(self._rows(2000))  # must not raise

    def test_deliverable_guard_flags_a_task_type_filter_that_matched_nothing(self):
        """1,530 Done rows in and zero out is a renamed Task Type, not a clean queue."""
        with self.assertRaises(deliverable.QueueUnavailable) as ctx:
            deliverable.assert_non_degenerate([], done_seen=1530)
        self.assertIn("Task Type", ctx.exception.detail)

    def test_deliverable_guard_flags_tasks_with_no_execution_notes(self):
        """It parses ONLY Execution Notes, so a rename there blinds it completely."""
        tasks = [{"title": "t", "aiq": "AIQ-1", "url": "", "paths": [], "notes": ""}]
        with self.assertRaises(deliverable.QueueUnavailable) as ctx:
            deliverable.assert_non_degenerate(tasks, done_seen=1530)
        self.assertIn("Execution Notes", ctx.exception.detail)

    def test_deliverable_guard_accepts_a_healthy_scan(self):
        tasks = [{"title": "t", "aiq": "AIQ-1", "url": "", "paths": ["backend/x.py"],
                  "notes": "CREATED: `backend/x.py`"}]
        deliverable.assert_non_degenerate(tasks, done_seen=1530)  # must not raise


class UnmeasurableExitsThree(unittest.TestCase):
    """0 and 3 must not be the same value."""

    def test_exit_codes_are_distinct(self):
        for mod in (hygiene, deliverable):
            with self.subTest(mod=mod.__name__):
                self.assertEqual(mod.EXIT_OK, 0)
                self.assertEqual(mod.EXIT_VIOLATION, 1)
                self.assertEqual(mod.EXIT_NOT_MEASURED, 3)

    def test_no_token_returns_three_not_zero(self):
        for mod in (hygiene, deliverable):
            with self.subTest(mod=mod.__name__):
                self.assertEqual(mod._not_measured("no-token", "x"), 3)

    def test_no_access_returns_three_and_names_the_fix(self):
        """Today's live cause. The remediation is one click, so print it."""
        import io
        from contextlib import redirect_stdout
        for mod in (hygiene, deliverable):
            with self.subTest(mod=mod.__name__):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = mod._not_measured("no-access", "HTTP 404")
                out = buf.getvalue()
                self.assertEqual(code, 3)
                self.assertIn("NOT A PASS", out)
                self.assertIn("Connections", out)


if __name__ == "__main__":
    unittest.main()

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


class TheDeliverableCanaryMustNotFireOnAHealthyScan(unittest.TestCase):
    """The bug this class exists for was in the CANARY, not in the queue.

    Shipped in the same change that added `assert_non_degenerate`: `fetch_done_tasks`
    appended tasks as {title, aiq, url, paths} — with NO `notes` key — while the canary
    asserted `any(t.get("notes", "").strip() ...)`. Every healthy run therefore raised
    "NOT ONE had Execution Notes" and exited 3.

    It went unnoticed because the tests handed `assert_non_degenerate` synthetic dicts
    that DID carry a `notes` key. That is the identical mistake
    `test_the_CALL_SITE_reads_fable_not_just_the_helper` was written to catch one function
    over, and it was not applied here. So these tests drive the real
    `fetch_done_tasks` against a stubbed HTTP response instead of hand-built rows.

    The canary was also asking the wrong question. A task only reaches `tasks` if paths
    were parsed OUT of its notes, so notes are non-empty for every member by construction
    — the check could never fail for a real reason. Meanwhile the blindness it was meant
    to catch (Execution Notes renamed -> every note empty -> no paths -> no tasks) fell
    through to the Task Type branch and got misdiagnosed as a Task Type rename. It now
    counts the two stages separately.
    """

    def _page(self, *, task_type="Backend Implementation", notes="CREATED: `backend/x.py`"):
        return {
            "url": "https://notion.so/p",
            "properties": {
                "fable": _title_prop("AIQ-1 t"),
                "Task Type": {"select": {"name": task_type}},
                "Execution Notes": {"rich_text": [{"plain_text": notes}]},
            },
        }

    def _run(self, pages):
        """Drive the REAL fetch_done_tasks against a stubbed Notion response."""
        import io, json
        from contextlib import contextmanager
        from unittest import mock

        payload = json.dumps({"results": pages, "has_more": False}).encode()

        @contextmanager
        def fake_urlopen(req, timeout=None):
            yield io.BytesIO(payload)

        with mock.patch.object(deliverable.urllib.request, "urlopen", fake_urlopen):
            return deliverable.fetch_done_tasks("tok", "db")

    def test_a_healthy_scan_does_not_raise(self):
        """600 ordinary Done rows with real notes. Before the fix this raised."""
        tasks, done_seen, fp_seen, with_notes = self._run([self._page() for _ in range(600)])
        self.assertEqual(done_seen, 600)
        self.assertEqual(fp_seen, 600)
        self.assertEqual(with_notes, 600)
        deliverable.assert_non_degenerate(tasks, done_seen, fp_seen, with_notes)  # must not raise

    def test_the_call_site_actually_populates_notes(self):
        """The precise omission. Asserted on the REAL return value, not a fixture."""
        tasks, *_ = self._run([self._page()])
        self.assertTrue(tasks, "the page should have produced a task")
        self.assertIn("notes", tasks[0], "fetch_done_tasks must carry the notes it parsed")
        self.assertIn("CREATED:", tasks[0]["notes"])

    def test_notes_all_empty_is_reported_as_a_NOTES_problem_not_a_task_type_one(self):
        """The blindness the canary is actually for: the property renamed."""
        pages = [self._page(notes="") for _ in range(600)]
        tasks, done_seen, fp_seen, with_notes = self._run(pages)
        self.assertEqual(fp_seen, 600)
        self.assertEqual(with_notes, 0)
        with self.assertRaises(deliverable.QueueUnavailable) as ctx:
            deliverable.assert_non_degenerate(tasks, done_seen, fp_seen, with_notes)
        self.assertIn("Execution Notes", ctx.exception.detail)
        self.assertNotIn("Task Type", ctx.exception.detail)

    def test_task_type_renamed_is_still_reported_as_a_task_type_problem(self):
        pages = [self._page(task_type="Something Unknown") for _ in range(600)]
        tasks, done_seen, fp_seen, with_notes = self._run(pages)
        self.assertEqual(fp_seen, 0)
        with self.assertRaises(deliverable.QueueUnavailable) as ctx:
            deliverable.assert_non_degenerate(tasks, done_seen, fp_seen, with_notes)
        self.assertIn("Task Type", ctx.exception.detail)

    def test_notes_present_but_carrying_no_paths_is_NOT_degenerate(self):
        """A legitimately empty result. Notes were read; they just named no files."""
        pages = [self._page(notes="Investigated; nothing shipped.") for _ in range(600)]
        tasks, done_seen, fp_seen, with_notes = self._run(pages)
        self.assertEqual(tasks, [])
        self.assertEqual(with_notes, 600)
        deliverable.assert_non_degenerate(tasks, done_seen, fp_seen, with_notes)  # must not raise

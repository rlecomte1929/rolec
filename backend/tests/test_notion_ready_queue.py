"""
Unit tests for scripts/notion_ready_queue.py — the deterministic "Ready for AI"
reader. The HTTP layer is mocked, so these run offline / in CI with no token.

Proves: server-side select-filter on Status, pagination is followed, and the
P0>P1>P2>P3 → easiest-complexity → ascending-AIQ ranking is correct.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

import notion_ready_queue as nrq  # noqa: E402


def _row(num: int, prio: str, comp: str) -> dict:
    return {
        "url": f"https://notion.so/{num}",
        "properties": {
            "ID": {"unique_id": {"prefix": "AIQ", "number": num}},
            "Task Title": {"title": [{"plain_text": f"task {num}"}]},
            "Priority": {"select": {"name": prio}},
            "Estimated Complexity": {"select": {"name": comp}},
            "Task Type": {"select": {"name": "Backend Implementation"}},
            "Status": {"select": {"name": "Ready for AI"}},
            "Dependencies": {"rich_text": []},
        },
    }


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return self._b


class TestReadyQueue(unittest.TestCase):
    def test_ranks_and_paginates_and_filters(self) -> None:
        page1 = {
            "results": [_row(840, "P1", "Medium"), _row(838, "P0", "High")],
            "has_more": True,
            "next_cursor": "cursor-1",
        }
        page2 = {"results": [_row(839, "P0", "Low")], "has_more": False}
        captured: list[dict] = []

        def fake_urlopen(req, timeout=30):  # noqa: ARG001
            captured.append(json.loads(req.data.decode()))
            return _FakeResp(page1 if len(captured) == 1 else page2)

        with mock.patch.object(nrq.urllib.request, "urlopen", fake_urlopen):
            tasks = nrq.rank(nrq.query_queue("tok", "Ready for AI"))

        # Ranking: P0 (Low) -> P0 (High) -> P1 (Medium)
        self.assertEqual([t["aiq"] for t in tasks], ["AIQ-839", "AIQ-838", "AIQ-840"])
        # Pagination followed: two requests, second carried the cursor.
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[1]["start_cursor"], "cursor-1")
        # Server-side filter is a SELECT filter on Status (not a status-type filter).
        self.assertEqual(
            captured[0]["filter"], {"property": "Status", "select": {"equals": "Ready for AI"}}
        )

    def test_helpers(self) -> None:
        self.assertEqual(nrq._unique_id({"unique_id": {"prefix": "AIQ", "number": 5}}), "AIQ-5")
        self.assertEqual(nrq._unique_id({"unique_id": {"prefix": None, "number": 7}}), "7")
        self.assertEqual(nrq._plain_text({"select": {"name": "P0"}}), "P0")
        self.assertEqual(
            nrq._plain_text({"rich_text": [{"plain_text": "a"}, {"plain_text": "b"}]}), "ab"
        )


if __name__ == "__main__":
    unittest.main()

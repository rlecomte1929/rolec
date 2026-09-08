"""AIQ-1331 — admin CMS dashboard counts must reflect real rows.

The count tiles read 0 for every status even with 57 published resources live.
Root cause: get_admin_dashboard_counts queried with `count="exact", head=True`,
which returns 0 in the installed supabase-py — while the list endpoint, which uses
`count="exact"` WITHOUT head, returns the real total. These tests inject a fake
supabase client and assert (a) the counts aggregate correctly and (b) the query
no longer passes head=True (the regression guard that fails on the old code).
"""
from __future__ import annotations

import types

import backend.app.services.admin_resources as svc


class _FakeQuery:
    def __init__(self, table_name, recorder, data):
        self._table = table_name
        self._rec = recorder
        self._data = data
        self._filters = {}

    def select(self, *_args, **kwargs):
        self._rec["select_kwargs"] = kwargs
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def limit(self, _n):
        self._rec["limit_called"] = True
        return self

    def execute(self):
        status = self._filters.get("status")
        count = self._data.get((self._table, status), 0)
        return types.SimpleNamespace(count=count, data=[])


class _FakeClient:
    def __init__(self, recorder, data):
        self._rec = recorder
        self._data = data

    def table(self, name):
        return _FakeQuery(name, self._rec, self._data)


def test_counts_reflect_rows_and_avoid_head(monkeypatch):
    data = {
        ("country_resources", "published"): 57,
        ("country_resources", "draft"): 3,
        ("country_resources", "in_review"): 1,
        ("country_resources", "archived"): 0,
        ("rkg_country_events", "published"): 4,
        ("rkg_country_events", "draft"): 2,
    }
    recorder: dict = {}
    monkeypatch.setattr(svc, "_get_supabase", lambda: _FakeClient(recorder, data))

    counts = svc.get_admin_dashboard_counts()

    # (a) real rows are reflected (was 0 for everything before the fix)
    assert counts["resources_published"] == 57
    assert counts["resources_draft"] == 3
    assert counts["resources_in_review"] == 1
    assert counts["resources_archived"] == 0
    assert counts["events_published"] == 4
    assert counts["events_draft"] == 2

    # (b) regression guard: the broken pattern was count="exact" + head=True.
    assert recorder["select_kwargs"] == {"count": "exact"}
    assert "head" not in recorder["select_kwargs"]
    assert recorder.get("limit_called") is True

"""Three writes that succeeded and could never be read back.

Each bound the RAW route param into a canonically-keyed table. Route params are routinely
ASSIGNMENT ids (`HrDashboard.tsx` navigates with `assignment.id`), and every reader resolves
first — so the row was committed, the endpoint returned success, and nothing ever showed it:

  cases_write.register_prefilled   -> case_form_documents.case_id   read by cases_read (resolved)
  cases_write.post_case_message    -> case_messages.case_id         read via _canonical_case_id_or_404
  case_forms_adhoc.create_adhoc    -> case_forms.case_id            read by list_case_forms (resolved)

Two of the three had a sibling in the SAME file already doing it right — `upload_form_document`
binds `resolved_case_id` with a comment saying the raw id "would make the row invisible to every
reader that resolves", and `replace_adhoc_pdf` was fixed for exactly this by AIQ-1776.

`test_adhoc_refetch_uses_the_same_id_it_inserted` guards the trap this fix could have created:
`create_adhoc` re-fetches through `_fetch_single_form_summary`, which filters
`WHERE cf.id = :form_id AND cf.case_id = :case_id`. Before the fix BOTH sides were raw, so they
matched each other while being invisible to everyone else. Changing only the INSERT would have
turned an invisible row into a 404 on create.
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402

ASSIGNMENT = "ec13fc07-47a8-4179-8958-f286e950c890"
CANONICAL = "a839d6f4-dc82-4e68-9eaf-f893c3206c27"
_USER = {"id": "u1", "role": "EMPLOYEE"}


class _Conn:
    """Records every bind dict so a test can assert which id was written."""

    def __init__(self, sink):
        self.sink = sink

    def execute(self, _stmt, params=None):
        if params:
            self.sink.append(dict(params))
        return _Result()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def begin(self):
        return self

    def connect(self):
        return self


class _Result:
    def mappings(self):
        return self

    def first(self):
        return {
            "id": "doc-1", "case_form_id": "form-1", "case_id": CANONICAL,
            "file_name": "f.pdf", "content_type": "application/pdf", "size_bytes": 1,
            "uploaded_by": "u1", "doc_key": None, "created_at": "2026-08-12T00:00:00",
        }


def _run_adhoc(mod):
    """Drive the async handler without pytest-asyncio.

    The plugin is in CI's requirements but not necessarily in a local venv, and a test that
    silently doesn't run is worse than one that needs no plugin.
    """
    return asyncio.run(
        mod.create_adhoc_form(
            ASSIGNMENT, name="Birth certificate", authority=None, person_id=None,
            deadline=None, notes=None, file=None, user=_USER,
        )
    )


def _binds_for_case_id(binds):
    """Every bound value that looks like a case id, under any of its parameter names."""
    out = []
    for b in binds:
        for key in ("cid", "case_id"):
            if key in b:
                out.append(b[key])
    return out


def test_a_prefilled_document_is_stored_under_the_canonical_id(monkeypatch):
    from backend.app.routers import cases_write as mod

    binds: list = []
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod, "_load_form_with_template", lambda *a, **k: {"id": "form-1", "fields": []})
    monkeypatch.setattr(mod.main_db, "engine", _Conn(binds))
    monkeypatch.setattr(mod, "insert_audit_log", lambda *a, **k: None)

    payload = mock.Mock(file_name="f.pdf", fill_report={}, advance_status=False)
    mod.register_prefilled_document(ASSIGNMENT, "form-1", payload, user=_USER)

    assert CANONICAL in _binds_for_case_id(binds)
    assert ASSIGNMENT not in _binds_for_case_id(binds), (
        "the raw route param was written to case_form_documents — the row is invisible to "
        "every reader, which all resolve"
    )


def test_a_message_is_stored_under_the_canonical_id(monkeypatch):
    from backend.app.routers import cases_write as mod

    binds: list = []
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod, "_detect_sender_role", lambda _u: "EMPLOYEE")
    monkeypatch.setattr(mod.main_db, "engine", _Conn(binds))

    body = mock.Mock(content="hello")
    try:
        mod.post_case_message(ASSIGNMENT, body, user=_USER)
    except Exception:
        pass  # the fake row shape isn't the point; the bind is

    written = _binds_for_case_id(binds)
    assert CANONICAL in written
    assert ASSIGNMENT not in written, (
        "the message was stored under the assignment id — it returns 201 and never appears "
        "in the thread, which reads via _canonical_case_id_or_404"
    )


def test_an_adhoc_form_is_stored_under_the_canonical_id(monkeypatch):
    from backend.app.routers import case_forms_adhoc as mod

    binds: list = []
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod.main_db, "engine", _Conn(binds))
    monkeypatch.setattr(mod, "_fetch_single_form_summary", lambda cid, fid: {"cid": cid})

    _run_adhoc(mod)

    written = _binds_for_case_id(binds)
    assert CANONICAL in written
    assert ASSIGNMENT not in written, (
        "the ad-hoc form was stored under the assignment id — it never appears in the Dossier"
    )


def test_adhoc_refetch_uses_the_same_id_it_inserted(monkeypatch):
    """The trap this fix could have created.

    `_fetch_single_form_summary` filters on `cf.case_id`, so re-fetching with the raw param
    after inserting the resolved one would 404 the row we just created.
    """
    from backend.app.routers import case_forms_adhoc as mod

    binds: list = []
    seen = {}
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod.main_db, "engine", _Conn(binds))
    monkeypatch.setattr(
        mod, "_fetch_single_form_summary",
        lambda cid, fid: seen.update(refetched=cid) or {"cid": cid},
    )

    _run_adhoc(mod)

    inserted = [v for v in _binds_for_case_id(binds)]
    assert seen["refetched"] == CANONICAL
    assert seen["refetched"] in inserted, (
        "the create re-fetches with a different id than it inserted — 404 after a successful write"
    )

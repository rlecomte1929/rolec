"""The rest of the raw-route-param sites, and one endpoint that had no tenant guard at all.

Closes the sweep that began at #1833. Every fix here is the same shape — capture
`_assert_case_access`'s RESOLVED return value instead of keying on the raw route param —
because route params are routinely ASSIGNMENT ids (`HrDashboard.tsx` navigates with
`assignment.id`) while the tables are keyed canonically.

Three distinct symptoms, all of which fail QUIETLY:

  404 on a case that exists       get_case_roadmap, start_research, create_case
                                  (`crud.get_case` keys on the raw value)
  404 AFTER a committed write     patch_form_fields, patch_form_status, replace_adhoc_pdf
                                  (the write resolves, the response re-fetch does not)
  a permanently empty list        get_rule_updates — rows are written by active_case_finder
                                  from rce.cases (canonical) and were read raw, so the
                                  "Rule updated — please review" banner never appeared

And `update_household`, which is a different and worse thing: it had authentication and NO
authorization, while writing family members and pets into the case draft. It was the only
handler in cases_write.py without a tenant guard, and it is live (frontend calls it from
api/roadmap.ts). See test_household_requires_case_access.
"""
from __future__ import annotations

import os
import sys
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

ASSIGNMENT = "ec13fc07-47a8-4179-8958-f286e950c890"
CANONICAL = "a839d6f4-dc82-4e68-9eaf-f893c3206c27"
_USER = {"id": "u1", "role": "EMPLOYEE"}


class _Case:
    draft_json = '{"relocationBasics": {"destCountry": "NO", "purpose": "employment"}}'
    status = "draft"
    id = CANONICAL


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def commit(self):
        pass


def _only_canonical(seen):
    """A get_case that behaves like the real one: it matches the CANONICAL id only."""
    def _get(_db, cid):
        seen.append(cid)
        return _Case() if cid == CANONICAL else None
    return _get


# ── 404 on a case that exists ────────────────────────────────────────────────────────

def test_roadmap_resolves_an_assignment_id(monkeypatch):
    """The live employee RoadmapScreen. This route is NOT shadowed by compat.py."""
    from backend.app.routers import cases_read as mod

    seen: list = []
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod, "assert_roadmap_access", lambda _c: None)
    monkeypatch.setattr(mod, "SessionLocal", lambda: _NullSession())
    monkeypatch.setattr(mod.crud, "get_case", _only_canonical(seen))
    monkeypatch.setattr(mod, "is_flag_enabled_for", lambda *a, **k: False)
    monkeypatch.setattr(mod, "build_roadmap", lambda *a, **k: {"tracks": []}, raising=False)

    try:
        mod.get_case_roadmap(ASSIGNMENT, user=_USER)
    except Exception:
        pass  # downstream roadmap construction isn't what's under test

    assert seen == [CANONICAL], (
        f"crud.get_case received {seen} — a raw assignment id 404s a case that exists"
    )


def test_start_research_resolves_an_assignment_id(monkeypatch):
    from backend.app.routers import cases_write as mod

    seen: list = []
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod, "SessionLocal", lambda: _NullSession())
    monkeypatch.setattr(mod.crud, "get_case", _only_canonical(seen))
    monkeypatch.setattr(mod, "run_country_research", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_audit_case", lambda **k: None)

    mod.start_research(ASSIGNMENT, user=_USER)
    assert seen == [CANONICAL]


def test_create_case_resolves_before_lookup_and_snapshot(monkeypatch):
    """The snapshot insert was also storing the raw id into a canonically-keyed table."""
    from backend.app.routers import cases_write as mod

    seen: list = []
    snapshots: list = []
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod, "SessionLocal", lambda: _NullSession())
    monkeypatch.setattr(mod.crud, "get_case", _only_canonical(seen))
    monkeypatch.setattr(mod.crud, "create_snapshot", lambda _db, p: snapshots.append(p["case_id"]))
    monkeypatch.setattr(
        mod, "compute_case_requirements",
        lambda _c: mock.Mock(model_dump_json=lambda: "{}", sources=[]),
    )
    monkeypatch.setattr(mod, "_audit_case", lambda **k: None)

    case = _Case()
    case.draft_json = (
        '{"relocationBasics": {"originCountry":"FR","originCity":"Paris","destCountry":"NO",'
        '"destCity":"Oslo","purpose":"employment","targetMoveDate":"2026-09-01"}}'
    )
    monkeypatch.setattr(mod.crud, "get_case", lambda _db, cid: seen.append(cid) or (case if cid == CANONICAL else None))

    try:
        mod.create_case(ASSIGNMENT, mock.Mock(state=mock.Mock(request_id="r1")), user=_USER)
    except Exception:
        pass

    assert seen == [CANONICAL]
    assert snapshots == [CANONICAL], (
        "the requirements snapshot was stored under the raw route param"
    )


# ── 404 after a committed write ──────────────────────────────────────────────────────

@pytest.mark.parametrize("handler", ["bulk_update_form_fields", "patch_form_status"])
def test_form_handlers_refetch_with_the_id_they_wrote(monkeypatch, handler):
    """The write path resolves; the response re-fetch must use the same id.

    `_fetch_single_form_summary` ends `WHERE cf.id = :form_id AND cf.case_id = :case_id`, so
    a raw re-fetch 404s the caller after their update has already committed.
    """
    import inspect

    from backend.app.routers import cases_write as mod

    src = inspect.getsource(getattr(mod, handler))
    assert "case_id = _assert_case_access(user, case_id)" in src, (
        f"{handler} does not capture the resolved id, so its re-fetch keys on the raw param"
    )


def test_replace_adhoc_pdf_refetches_with_the_resolved_id():
    """AIQ-1776 resolved both SQL statements here and left the re-fetch raw."""
    import inspect

    from backend.app.routers import case_forms_adhoc as mod

    src = inspect.getsource(mod.replace_adhoc_pdf)
    assert "_fetch_single_form_summary(resolved_case_id" in src, (
        "the PDF swap commits and then 404s the caller"
    )


# ── a permanently empty list ─────────────────────────────────────────────────────────

def test_rule_updates_reads_with_the_resolved_id(monkeypatch):
    from backend.app.routers import case_rule_updates as mod

    seen: list = []
    monkeypatch.setattr(mod, "_assert_case_access", lambda _u, _c: CANONICAL)
    monkeypatch.setattr(mod, "list_active_rule_updates", lambda _c, cid: seen.append(cid) or [])

    class _Eng:
        def connect(self):
            return _NullSession()

    monkeypatch.setattr(mod, "engine", _Eng())
    mod.get_rule_updates(ASSIGNMENT, user=_USER)

    assert seen == [CANONICAL], (
        'rows are written canonically by active_case_finder, so a raw read left the '
        '"Rule updated — please review" banner permanently empty'
    )


# ── the missing guard ────────────────────────────────────────────────────────────────

def test_household_requires_case_access(monkeypatch):
    """`POST /api/cases/{id}/household` had authentication and NO authorization.

    It writes family members and pets into the case draft, it is live (api/roadmap.ts calls
    it), and it was the only handler in cases_write.py with no tenant guard. A caller from
    another tenant must now be refused before anything is written.
    """
    from backend.app.routers import cases_write as mod

    def _deny(_user, _cid):
        raise HTTPException(status_code=403, detail="Not authorised for this case")

    monkeypatch.setattr(mod, "_assert_case_access", _deny)
    monkeypatch.setattr(mod, "SessionLocal", lambda: _NullSession())
    monkeypatch.setattr(
        mod.crud, "get_case",
        lambda *a, **k: pytest.fail("the case was read before the tenant guard ran"),
    )

    with pytest.raises(HTTPException) as exc:
        mod.update_household(CANONICAL, mock.Mock(family_members=[], pets=[]), user=_USER)
    assert exc.value.status_code == 403

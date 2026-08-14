"""`PATCH /api/cases/{case_id}` must not turn an existing case into a second one.

`crud.get_case` looks `wizard_cases` up by the RAW id, but route params are routinely
ASSIGNMENT ids (`HrDashboard.tsx` navigates with `assignment.id`). Handed one, `get_case`
returned `None` for a case that plainly exists, so the handler took the create-on-missing
branch — which by design skips the access check (SEC-CASES-2: *"a brand-new case can't be
access-checked"*). Two things followed:

  * `_assert_case_access` never ran for a case that EXISTS and may belong to another tenant;
  * a second `wizard_cases` row was created under the assignment id, forking the case, with
    the side effects and the audit row all firing on the wrong id.

The create-on-missing path itself is deliberate and must survive: it is how the wizard
creates a case (PATCH a fresh uuid). So the fix resolves FIRST and only then decides which
branch it is in — `resolve_case_forms_case_id` returns its input unchanged when nothing
resolves, so a genuinely new id still creates.

`test_a_brand_new_case_is_still_created` is the regression that matters most here: it is the
flow SEC-CASES-2 exists to protect and the easiest thing to break while fixing the other half.
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

ASSIGNMENT = "ec13fc07-47a8-4179-8958-f286e950c890"
CANONICAL = "a839d6f4-dc82-4e68-9eaf-f893c3206c27"
BRAND_NEW = "11111111-2222-3333-4444-555555555555"

_USER = {"id": "u1"}


class _Draft:
    """Stands in for a wizard_cases row."""

    draft_json = "{}"


def _patch_env(monkeypatch, mod, *, existing_ids, resolver):
    """Wire the handler's collaborators; return the call log."""
    log = {"created": [], "guarded": [], "updated": [], "side_effects": []}

    monkeypatch.setattr(mod, "resolve_case_forms_case_id", resolver)
    monkeypatch.setattr(
        mod.crud, "get_case", lambda _db, cid: _Draft() if cid in existing_ids else None
    )

    def _create(_db, cid, _incoming):
        log["created"].append(cid)
        return _Draft()

    monkeypatch.setattr(mod.crud, "create_case", _create)
    monkeypatch.setattr(mod.crud, "update_case", lambda _db, case, *a, **k: case)
    monkeypatch.setattr(
        mod, "_assert_case_access", lambda _u, cid: log["guarded"].append(cid) or cid
    )
    monkeypatch.setattr(mod, "_case_dto", lambda case, draft: {"ok": True})
    monkeypatch.setattr(mod, "_audit_case", lambda **kw: log["updated"].append(kw.get("entity_id")))
    monkeypatch.setattr(mod, "resolve_test_drive_route", lambda _u: None)
    monkeypatch.setattr(mod, "invalidate_relocation_plan_cache", lambda **kw: None)
    monkeypatch.setattr(
        mod.main_db, "apply_wizard_patch_side_effects",
        lambda cid, *a, **k: log["side_effects"].append(cid),
    )
    monkeypatch.setattr(mod, "SessionLocal", lambda: _NullSession())
    return log


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Tasks:
    def add_task(self, *a, **k):
        pass


def _call(mod, case_id):
    from backend.app import schemas

    return mod.patch_case(
        case_id,
        schemas.CaseDraftDTO(),
        _Tasks(),
        user=_USER,
    )


def test_an_assignment_id_for_an_existing_case_is_guarded_not_created(monkeypatch):
    """The bug: the guard was skipped and a second row was minted."""
    from backend.app.routers import cases_write as mod

    log = _patch_env(
        monkeypatch, mod,
        existing_ids={CANONICAL},                       # only the canonical row exists
        resolver=lambda cid: CANONICAL if cid == ASSIGNMENT else cid,
    )

    _call(mod, ASSIGNMENT)

    assert log["created"] == [], "a second wizard_cases row was created for an existing case"
    assert log["guarded"] == [CANONICAL], (
        "the tenant guard did not run — an assignment id skipped authorisation entirely"
    )


def test_the_side_effects_fire_on_the_resolved_id(monkeypatch):
    from backend.app.routers import cases_write as mod

    log = _patch_env(
        monkeypatch, mod,
        existing_ids={CANONICAL},
        resolver=lambda cid: CANONICAL if cid == ASSIGNMENT else cid,
    )

    _call(mod, ASSIGNMENT)

    assert log["side_effects"] == [CANONICAL]
    assert log["updated"] == [CANONICAL], "the audit row recorded the raw route param"


def test_a_brand_new_case_is_still_created(monkeypatch):
    """SEC-CASES-2's flow: the wizard creates a case by PATCHing a fresh uuid.

    `resolve_case_forms_case_id` returns its input when nothing resolves, so an unknown id
    must still reach `create_case` — and must NOT be access-checked, because there is
    nothing yet to own.
    """
    from backend.app.routers import cases_write as mod

    log = _patch_env(
        monkeypatch, mod,
        existing_ids=set(),                             # nothing exists yet
        resolver=lambda cid: cid,                       # nothing resolves
    )

    _call(mod, BRAND_NEW)

    assert log["created"] == [BRAND_NEW], "the wizard can no longer create a case"
    assert log["guarded"] == [], "a brand-new case must not be access-checked"


def test_a_canonical_id_for_an_existing_case_is_unchanged(monkeypatch):
    """The common path must behave exactly as before the fix."""
    from backend.app.routers import cases_write as mod

    log = _patch_env(
        monkeypatch, mod,
        existing_ids={CANONICAL},
        resolver=lambda cid: cid,
    )

    _call(mod, CANONICAL)

    assert log["created"] == []
    assert log["guarded"] == [CANONICAL]

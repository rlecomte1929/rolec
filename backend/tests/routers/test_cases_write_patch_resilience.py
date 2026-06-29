"""AIQ-1379 (+ follow-up) — the wizard PATCH saves fast and never 5xx's on a side effect.

patch_case saves the draft, then DEFERS the heavy fire_roadmap_events to a background task (so the
~8s work is off the response path and can't 5xx the save), and synchronously invalidates the plan
cache (fast, best-effort). Calls the handler directly. No DATABASE_URL at import.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from unittest import mock  # noqa: E402

from fastapi import BackgroundTasks  # noqa: E402

import backend.app.routers.cases_write as cw  # noqa: E402
from backend.app import schemas  # noqa: E402


def test_patch_case_defers_roadmap_events_and_survives_failing_invalidate():
    fake_case = mock.MagicMock()
    fake_crud = mock.MagicMock()
    fake_crud.get_case.return_value = None          # → create-on-missing path (skips _assert_case_access)
    fake_crud.create_case.return_value = fake_case
    fake_crud.update_case.return_value = fake_case

    fire = mock.MagicMock(side_effect=RuntimeError("cold roadmap downstream"))
    inval = mock.MagicMock(side_effect=RuntimeError("cache down"))
    bg = BackgroundTasks()

    patch = schemas.CaseDraftDTO(relocationBasics={"originCountry": "FR", "destCountry": "DE"})

    with mock.patch.object(cw, "SessionLocal", mock.MagicMock()), \
         mock.patch.object(cw, "crud", fake_crud), \
         mock.patch.object(cw, "fire_roadmap_events", fire), \
         mock.patch.object(cw, "invalidate_relocation_plan_cache", inval), \
         mock.patch.object(cw, "_audit_case", mock.MagicMock()), \
         mock.patch.object(cw, "_case_dto", mock.MagicMock(return_value={"ok": True})), \
         mock.patch.object(cw.main_db, "apply_wizard_patch_side_effects", mock.MagicMock()):
        # Must NOT raise (a raised exception → FastAPI 500), even though invalidate fails.
        result = cw.patch_case(case_id="case-1", patch=patch, background_tasks=bg, user={"id": "emp-1"})

    assert result == {"ok": True}                       # the saved draft is returned
    fake_crud.update_case.assert_called_once()          # the save happened synchronously
    # fire_roadmap_events is DEFERRED off the response path (the ~8s + cold-5xx fix), not run inline:
    fire.assert_not_called()
    assert any(t.func is fire for t in bg.tasks), "fire_roadmap_events must be queued as a background task"
    # invalidate is synchronous + best-effort: it raised, was swallowed, no 5xx:
    inval.assert_called_once()

"""AIQ-1379 — the wizard PATCH must not 5xx when a post-save side effect fails.

patch_case saves the draft, then fires roadmap events + invalidates the plan cache. Those are
side effects: a failure there (e.g. a cold downstream service) must never 5xx an already-saved
wizard draft. Calls the handler directly with the side effects mocked to raise. No DATABASE_URL at import.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from unittest import mock  # noqa: E402

import backend.app.routers.cases_write as cw  # noqa: E402
from backend.app import schemas  # noqa: E402


def test_patch_case_survives_failing_side_effects():
    fake_case = mock.MagicMock()
    fake_crud = mock.MagicMock()
    fake_crud.get_case.return_value = None          # → create-on-missing path (skips _assert_case_access)
    fake_crud.create_case.return_value = fake_case
    fake_crud.update_case.return_value = fake_case

    fire = mock.MagicMock(side_effect=RuntimeError("cold roadmap downstream"))
    inval = mock.MagicMock(side_effect=RuntimeError("cache down"))

    patch = schemas.CaseDraftDTO(relocationBasics={"originCountry": "FR", "destCountry": "DE"})

    with mock.patch.object(cw, "SessionLocal", mock.MagicMock()), \
         mock.patch.object(cw, "crud", fake_crud), \
         mock.patch.object(cw, "fire_roadmap_events", fire), \
         mock.patch.object(cw, "invalidate_relocation_plan_cache", inval), \
         mock.patch.object(cw, "_audit_case", mock.MagicMock()), \
         mock.patch.object(cw, "_case_dto", mock.MagicMock(return_value={"ok": True})), \
         mock.patch.object(cw.main_db, "apply_wizard_patch_side_effects", mock.MagicMock()):
        # Must NOT raise (a raised exception → FastAPI 500). Both side effects fail.
        result = cw.patch_case(case_id="case-1", patch=patch, user={"id": "emp-1"})

    assert result == {"ok": True}            # the saved draft is returned
    fire.assert_called_once()                # the side effect ran (and failed, swallowed)
    inval.assert_called_once()
    fake_crud.update_case.assert_called_once()  # the save happened

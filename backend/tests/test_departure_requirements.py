"""departure_requirements — approved origin-country EXIT requirements.

crud.list_requirements is mocked, so this covers the service's own logic: the direction
gate (only rows whose corridor ORIGIN is the mover's origin — reverse-corridor arrival
rows and topic-keyed ids are withheld), nationality gating, and the fail-safe
short-circuits (same-country move, missing origin).
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import departure_requirements as dr


def _row(id, *, pillar="IDENTITY", title="T", desc="D", non_obvious=False, nat_json=None, timing=None):
    return types.SimpleNamespace(
        id=id, pillar=pillar, title=title, description=desc,
        non_obvious=non_obvious, applies_to_nationality_classes_json=nat_json, timing=timing,
    )


def _case(origin="ES", dest="IE", nationality="VE"):
    return {
        "draft": {
            "relocationBasics": {"originCountry": origin, "destCountry": dest},
            "employeeProfile": {"nationality": nationality},
        }
    }


class DepartureRequirementRecordsTests(unittest.TestCase):
    def test_exit_rows_pass_and_reverse_or_untagged_rows_are_withheld(self) -> None:
        rows = [
            _row("ES:ES-IE:baja_padron", nat_json=None, non_obvious=True),  # exit (ES is corridor origin) → keep
            _row("ES:IE-ES:empadronamiento", nat_json=None),               # arrival (ES is corridor dest) → drop
            _row("ES:tax:modelo_030", nat_json=None),                      # topic-keyed, no corridor → drop
        ]
        with mock.patch.object(dr.crud, "list_requirements", return_value=rows):
            recs = dr.departure_requirement_records(object(), _case())
        self.assertEqual({r["id"] for r in recs}, {"ES:ES-IE:baja_padron"})
        self.assertTrue(recs[0]["non_obvious"])

    def test_eu_scoped_exit_row_withheld_from_third_country_mover(self) -> None:
        rows = [_row("ES:ES-IE:a", nat_json=None), _row("ES:ES-IE:b", nat_json='["EU_EEA"]')]
        with mock.patch.object(dr.crud, "list_requirements", return_value=rows):
            recs = dr.departure_requirement_records(object(), _case(nationality="VE"))
        ids = {r["id"] for r in recs}
        self.assertIn("ES:ES-IE:a", ids, "null-scoped exit row applies to all classes")
        self.assertNotIn("ES:ES-IE:b", ids, "EU_EEA-scoped row withheld from a third-country mover")

    def test_same_country_move_short_circuits_before_db(self) -> None:
        with mock.patch.object(dr.crud, "list_requirements", return_value=[_row("ES:ES-IE:a")]) as m:
            recs = dr.departure_requirement_records(object(), _case(origin="ES", dest="ES"))
        self.assertEqual(recs, [])
        m.assert_not_called()

    def test_missing_origin_returns_empty(self) -> None:
        recs = dr.departure_requirement_records(object(), {"draft": {"relocationBasics": {"destCountry": "IE"}}})
        self.assertEqual(recs, [])

    def test_no_approved_rows_returns_empty(self) -> None:
        with mock.patch.object(dr.crud, "list_requirements", return_value=[]):
            self.assertEqual(dr.departure_requirement_records(object(), _case()), [])


if __name__ == "__main__":
    unittest.main()

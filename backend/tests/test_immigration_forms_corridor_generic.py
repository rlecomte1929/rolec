"""AIQ-1771: available-forms must resolve the corridor, never default to Germany.

The old signature was `visa_type: str = "blue_card"` with
`corridor_to = case.dest_country or "DE"`. That produced two DIFFERENT wrong
answers, which is why both are asserted separately below:

  * a FR case queried FR+blue_card. Prod carries DE/blue_card and FR/long_stay,
    so FR+blue_card matches NOTHING — the French user saw no forms at all and the
    feature looked absent. A silent empty, not a visible error.
  * a case with no dest_country became "DE" and was offered the German Blue Card:
    a wrong form presented as the right one.

The fix resolves both from data. A corridor with no mapped forms returns an empty
list rather than an error, because that is the correct answer for a portal /
data-sheet corridor like Norway (FINDINGS.md Appendix A.1).

No DB: get_available_forms / visa_types_for_corridor are patched, so these assert
the ROUTER's resolution logic, which is where the defect lived.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite://")
# RouteRegistrationTests mounts the prod app (`from backend.main import app`).
# conftest mocks backend.database, and the query counter then tries to attach a
# SQLAlchemy `before_cursor_execute` event to a MagicMock engine, which raises.
# Both flags must be set BEFORE that import — CI does not set them. Same prelude
# as test_auth_login_identifier.py / test_hr_export.py.
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi import HTTPException  # noqa: E402

from backend.app.routers import immigration_forms as mod  # noqa: E402

# Mirrors prod as measured 2026-08-04:
#   DE / blue_card  (15 mappings, 1 form)
#   FR / long_stay  (12 mappings, 1 form)
_PROD_CATALOGUE = {"DE": ["blue_card"], "FR": ["long_stay"], "NO": []}


def _fake_visa_types(corridor_to):
    return list(_PROD_CATALOGUE.get(corridor_to, []))


class _Form:
    def __init__(self, form_id):
        self.form_id = form_id

    def to_dict(self):
        return {"form_id": self.form_id}


def _fake_get_available_forms(corridor_to, visa_type):
    if visa_type in _PROD_CATALOGUE.get(corridor_to, []):
        return [_Form(f"{corridor_to}-{visa_type}-form")]
    return []


def _call(case_id="case-1", visa_type=None, corridor_to=None, case_details=None):
    with mock.patch.object(mod, "visa_types_for_corridor", _fake_visa_types), \
         mock.patch.object(mod, "get_available_forms", _fake_get_available_forms), \
         mock.patch.object(mod, "_get_case_details", lambda cid, org: case_details):
        return mod.list_available_forms(
            case_id=case_id,
            visa_type=visa_type,
            corridor_to=corridor_to,
            hr_user={"id": "hr-1"},
            org_id="org-1",
        )


class CorridorResolutionTests(unittest.TestCase):
    def test_fr_case_gets_the_french_form_not_an_empty_list(self):
        """The regression: FR previously queried FR+blue_card and got nothing."""
        out = _call(case_details={"dest_country": "FR"})
        self.assertEqual(out["corridor_to"], "FR")
        self.assertEqual(out["visa_type"], "long_stay")
        self.assertEqual([f["form_id"] for f in out["forms"]], ["FR-long_stay-form"])

    def test_de_case_is_unchanged(self):
        """No-regression: the corridor that always worked still works."""
        out = _call(case_details={"dest_country": "DE"})
        self.assertEqual(out["visa_type"], "blue_card")
        self.assertEqual([f["form_id"] for f in out["forms"]], ["DE-blue_card-form"])

    def test_case_with_no_destination_422s_instead_of_becoming_german(self):
        """The wrong-form regression: `or "DE"` offered a German form to a case
        that had no destination at all."""
        with self.assertRaises(HTTPException) as ctx:
            _call(case_details={"dest_country": None})
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("destination corridor", str(ctx.exception.detail))

    def test_missing_case_422s_rather_than_defaulting(self):
        with self.assertRaises(HTTPException) as ctx:
            _call(case_details=None)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_norway_returns_no_forms_and_is_not_an_error(self):
        """NO is a portal/data-sheet corridor (FINDINGS A.1). An empty list is
        the right answer — it must not 4xx, and must never fall back to DE."""
        out = _call(case_details={"dest_country": "NO"})
        self.assertEqual(out["corridor_to"], "NO")
        self.assertIsNone(out["visa_type"])
        self.assertEqual(out["forms"], [])

    def test_explicit_visa_type_is_honoured(self):
        out = _call(case_details={"dest_country": "DE"}, visa_type="blue_card")
        self.assertEqual(out["visa_type"], "blue_card")

    def test_explicit_corridor_overrides_the_case(self):
        out = _call(case_details={"dest_country": "DE"}, corridor_to="FR")
        self.assertEqual(out["corridor_to"], "FR")
        self.assertEqual(out["visa_type"], "long_stay")

    def test_ambiguous_visa_type_422s_rather_than_picking(self):
        """If a corridor grows a second visa type, resolution must stop, not
        silently take the first."""
        with mock.patch.dict(_PROD_CATALOGUE, {"DE": ["blue_card", "eu_ict"]}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                _call(case_details={"dest_country": "DE"})
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertIn("more than one visa type", str(ctx.exception.detail))

    def test_no_blue_card_default_remains_in_the_signature(self):
        """Pin the defect itself: a default here reintroduces the bug even if the
        body is later rewritten."""
        import inspect

        sig = inspect.signature(mod.list_available_forms)
        self.assertIsNone(
            sig.parameters["visa_type"].default,
            "visa_type must not carry a default — a corridor-specific value "
            "cannot be defaulted (prod: DE/blue_card, FR/long_stay).",
        )


class RouteRegistrationTests(unittest.TestCase):
    """CLAUDE.md hard gate: a router registered in only one app 405s in prod.

    This is the repo's most-repeated incident, and this PR changes a handler
    signature, so assert both entry points still expose both routes.
    """

    def test_both_routes_present_on_the_prod_app(self):
        from backend.main import app

        paths = {r.path for r in app.routes if "immigration" in r.path}
        self.assertIn("/api/hr/cases/{case_id}/immigration/available-forms", paths)
        self.assertIn("/api/hr/cases/{case_id}/immigration/generate-form", paths)


if __name__ == "__main__":
    unittest.main()

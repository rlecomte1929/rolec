"""
AIQ-1754 criterion 6 — the golden FR->NO case.

The criterion is: *"A human-verified golden FR->NO case asserts every identifier
value correct (0 wrong)."* Only a human can do the verifying. What this file does
is make that signature cheap: it renders the whole data-sheet as a table — field,
value, provenance and the official citation behind each section — so signing off
is *read and confirm*, not a research project.

Two things make it trustworthy rather than decorative:

  1. **It loads the REAL template out of the shipped migration**, not a copy. The
     `fields` JSON is parsed straight from
     `supabase/migrations/20261015000000_seed_frno_data_sheet.sql`, so if the seed
     drifts, this test drifts with it and fails — a copy would silently rot.
  2. **It asserts 0 blank and 0 wrong.** Every field carrying a `prefill_source`
     must resolve, and must resolve to the exact expected golden value. A sheet
     that renders with holes, or with a plausible-but-wrong identifier, is the
     precise failure this corridor artifact exists to prevent.

Run it as a sign-off artifact:

    cd backend && pytest tests/test_golden_case_fr_no_datasheet.py -s

`-s` prints the table. Without it the assertions still run in CI.

NOT built on `tests/fixtures/pilot/generators/fr_no_french_spouse.py`: that
generator emits PDF stubs plus document-extraction `extracted_fields`, not a
prefill intake context. Deriving the golden case from it would add a PDF layer
between the reviewer and the values they must confirm. An explicit, readable
golden case is the more reviewable artifact — which is the whole point here.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
# `tests` is a package (tests/__init__.py), so importing the sibling test module
# needs backend/ on the path — the repo root alone only resolves `backend.*`.
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from backend.app.services import prefill_engine  # noqa: E402
from backend.app.services.prefill_engine import run_prefill  # noqa: E402
from tests.test_prefill_engine import (  # noqa: E402
    SCHEMA,
    _insert_case,
    _insert_case_form,
    _insert_profile,
    _insert_template,
    _uuid,
)

_MIGRATION = os.path.join(
    _REPO_ROOT, "supabase", "migrations",
    "20261015000000_seed_frno_data_sheet.sql",
)

# ---------------------------------------------------------------------------
# The golden case — a French EEA citizen moving to Norway under free movement.
# Deliberately explicit: every value below is what a reviewer confirms.
# 18 months of intended stay puts this case on the national-ID (>=6mo) path
# rather than D-number-only, so the folkeregister branch is actually exercised.
# ---------------------------------------------------------------------------
GOLDEN_INTAKE = {
    "profile": {
        "legal_full_name": "Camille Moreau",
        "date_of_birth": "1990-04-17",
        "nationality": "FR",
        "passport_number": "18AB45678",
        "passport_expiry": "2031-06-30",
    },
    "contract": {
        "employer_name": "Nordisk Teknologi AS",
        "employer_org_number": "923456789",
        "job_title": "Senior Software Engineer",
        "employment_start_date": "2026-09-15",
        "salary_amount_nok": 780000,
    },
}
GOLDEN_CASE_COLUMNS = {
    "target_move_date": "2026-09-01",
    "expected_duration_months": 18,
}

# field id -> the exact value the sheet must carry. This IS the "0 wrong" check.
EXPECTED = {
    "full_name": "Camille Moreau",
    "date_of_birth": "1990-04-17",
    "nationality": "FR",
    "id_document_number": "18AB45678",
    "id_document_expiry": "2031-06-30",
    "employer_name": "Nordisk Teknologi AS",
    "employer_org_number": "923456789",
    "job_title": "Senior Software Engineer",
    "employment_start_date": "2026-09-15",
    "salary_amount_nok": "780000",
    "arrival_date": "2026-09-01",
    "intended_stay_months": "18",
}

# Section -> the official source behind it, from ReloPass_FR-NO_Requirements_
# VERIFICATION.md. Printed beside each value so the reviewer confirms against the
# authority, not against our own prose.
CITATIONS = {
    "d_number": (
        "Item 2 — D-number issued by Skatteetaten inside the tax-card process, "
        "in-person ID check · udi.no/en/word-definitions/d-number/"
    ),
    "eea_registration": (
        "Item 3 — register with the police no later than three months after "
        "arriving; registration is free · udi.no EU/EEA regulations"
    ),
    "skattekort": (
        "Item 1 — without a tax deduction card the employer must deduct 50 percent "
        "· skatteetaten.no tax-deduction-cards"
    ),
    "folkeregister": (
        "Item 5 — report a move and obtain a national identity number if staying at "
        "least six months · skatteetaten.no fodselsnummer"
    ),
    "a1": (
        "Item 4 — A1 issued by FRANCE (URSSAF/CLEISS); 24-month standard posting "
        "limit, Art. 16 exception may extend · cleiss.fr detachement/ue883"
    ),
}


def _template_fields_from_migration():
    """Parse the shipped seed's `fields` JSON — the real thing, not a copy."""
    with open(_MIGRATION, encoding="utf-8") as fh:
        sql = fh.read()
    blocks = re.findall(r"'(\[\s*\{.*?\}\s*\])'::jsonb", sql, re.S)
    if not blocks:
        raise AssertionError(f"no fields jsonb found in {_MIGRATION}")
    return json.loads(blocks[0])


class GoldenCaseFrNoDataSheet(unittest.TestCase):

    def setUp(self):
        self.fields = _template_fields_from_migration()
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False},
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.patcher = mock.patch.object(prefill_engine.db, "engine", self.engine)
        self.patcher.start()

        self.case_id = _uuid()
        self.emp_id = _uuid()
        self.cf_id = _uuid()
        tmpl = _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, self.case_id, self.emp_id, GOLDEN_INTAKE,
                         dest="NO", origin="FR", **GOLDEN_CASE_COLUMNS)
            _insert_profile(conn, self.emp_id, full_name="Camille Moreau")
            _insert_template(conn, tmpl, "RP-NO-DATASHEET", self.fields)
            _insert_case_form(conn, self.cf_id, self.case_id, tmpl,
                              person_id=self.emp_id)
        run_prefill(self.cf_id, self.case_id)

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()

    def _values(self):
        with self.engine.begin() as conn:
            rows = conn.execute(text(
                "SELECT field_id, value, source FROM case_form_field_values "
                "WHERE case_form_id = :cf"
            ), {"cf": self.cf_id}).mappings().all()
        return {r["field_id"]: r for r in rows}

    # -- the sign-off artifact ------------------------------------------------

    def test_render_golden_data_sheet_for_signoff(self):
        vals = self._values()
        print("\n\n" + "=" * 100)
        print("GOLDEN FR->NO DATA SHEET  ·  RP-NO-DATASHEET  ·  AIQ-1754 criterion 6")
        print("Confirm each value against the citation, then sign off in Notion.")
        print("=" * 100)
        current = None
        for f in self.fields:
            if f["section"] != current:
                current = f["section"]
                print(f"\n[{current}]  {CITATIONS.get(current, '(no citation mapped)')}")
            row = vals.get(f["id"])
            if f.get("consult_professional"):
                state = "CONSULT PROFESSIONAL — never pre-filled"
            elif row and row["value"]:
                state = f"{row['value']}   (source: {row['source']})"
            else:
                state = "(blank — no derivable source)"
            print(f"   {f['id']:<26} {state}")
        print("\n" + "=" * 100 + "\n")
        self.assertTrue(vals, "prefill produced no values at all")

    # -- the mechanical guarantees -------------------------------------------

    def test_zero_blank_every_sourced_field_resolves(self):
        vals = self._values()
        missing = [
            f["id"] for f in self.fields
            if f.get("prefill_source")
            and not (vals.get(f["id"]) or {}).get("value")
        ]
        self.assertEqual(
            missing, [],
            f"sourced fields left BLANK on the golden case: {missing}. A sheet with "
            f"holes is exactly what this corridor artifact exists to prevent.",
        )

    def test_zero_wrong_every_value_matches_the_golden_expectation(self):
        vals = self._values()
        wrong = {
            fid: (vals.get(fid, {}).get("value"), expected)
            for fid, expected in EXPECTED.items()
            if (vals.get(fid) or {}).get("value") != expected
        }
        self.assertEqual(
            wrong, {},
            f"identifier values differ from the golden case (got, expected): {wrong}",
        )

    def test_consult_determinations_are_never_prefilled(self):
        vals = self._values()
        leaked = [
            f["id"] for f in self.fields
            if f.get("consult_professional") and (vals.get(f["id"]) or {}).get("value")
        ]
        self.assertEqual(
            leaked, [],
            f"a regulated determination was pre-populated: {leaked}. These must "
            f"always be made by an advisor.",
        )

    def test_unsourced_field_stays_blank_rather_than_guessed(self):
        # norwegian_address has no derivable source. Blank is correct; a plausible
        # guess on an accuracy-critical sheet is worse than a gap.
        vals = self._values()
        self.assertIsNone(
            (vals.get("norwegian_address") or {}).get("value"),
            "norwegian_address was filled — there is no source for it",
        )

    def test_golden_case_covers_every_expected_identifier(self):
        # Guards the guard: if the seed gains a sourced field, EXPECTED must gain
        # it too, or "0 wrong" would silently stop covering the new field.
        sourced = {f["id"] for f in self.fields if f.get("prefill_source")}
        uncovered = sourced - set(EXPECTED)
        self.assertEqual(
            uncovered, set(),
            f"seed has sourced fields with no golden expectation: {uncovered}",
        )

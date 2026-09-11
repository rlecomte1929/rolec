"""End-to-end fill of the REAL France-Visas CERFA 14571-*05 AcroForm (form-fill Phase 1).

Everything else in the form-fill suite fills a synthetic stand-in. This fills the actual
government PDF committed at docs/form-autofill/artifacts/fr_cerfa_14571-05.pdf (172 named
fields, downloaded from france-visas.gouv.fr), through the real code path
(build_fill_plan + build_choice_fill + fill_acroform), and verifies at the PDF level that:

  * the mapped text fields land with their format rules applied;
  * the gender / marital radio buttons tick with the form's REAL on-state (/On, not the
    reportlab /Yes) — proving _resolve_checkbox_states;
  * nothing a mapping addressed is missing from the delivered PDF (reconcile: 0 not-in-pdf).

DB-free / Storage-free: the template is the repo fixture; the mappings are parsed from the
re-seed migration so the test tracks what production actually loads.
"""
import io
import re
import unittest
from pathlib import Path

from pypdf import PdfReader

from backend.app.services import form_prefill_service as fps

_ROOT = Path(__file__).resolve().parents[2]
_PDF = _ROOT / "docs" / "form-autofill" / "artifacts" / "fr_cerfa_14571-05.pdf"
_MIGRATION = _ROOT / "supabase" / "migrations" / "20261135000000_fr_cerfa_14571_real_acroform_fields.sql"
FORM = "FR_cerfa_14571_v2024"

_ROW = re.compile(
    r"'FR_cerfa_14571_v2024',\s*'[^']*',\s*'FR',\s*'long_stay',\s*"
    r"'([^']+)',\s*'([^']*)',\s*'([^']+)',\s*'([^']*)',\s*(TRUE|FALSE)",
    re.I,
)


def _text_mappings():
    text = _MIGRATION.read_text(encoding="utf-8")
    return [
        {"form_field_id": fid, "form_field_label": label, "vault_field_path": vault,
         "format_rule": fmt or None, "exact_match_required": exact.upper() == "TRUE"}
        for fid, label, vault, fmt, exact in _ROW.findall(text)
    ]


_PROFILE = {
    "legal_last_name": "Diallo",
    "legal_first_name": "Awa",
    "date_of_birth": "1990-05-12",
    "place_of_birth": "Dakar",
    "nationality": "Senegalese",
    "passport_number": "ab 123 4567",
    "passport_issue_date": "2021-03-01",
    "passport_expiry": "2031-03-01",
    "job_title": "Software Engineer",
    "gender": "female",
    "marital_status": "married",
}


class FrCerfaRealPdfFill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert _PDF.exists(), f"real CERFA fixture missing: {_PDF}"
        cls.pdf_bytes = _PDF.read_bytes()

    def test_fixture_is_the_real_172_field_acroform(self):
        fields = PdfReader(io.BytesIO(self.pdf_bytes)).get_fields() or {}
        self.assertEqual(len(fields), 172, "fixture is not the expected France-Visas *05 AcroForm")
        self.assertIn("applicantSurname", fields)
        self.assertIn("travelDocNumber", fields)

    def test_full_fill_lands_text_and_radio_fields_in_the_real_form(self):
        # The real production path, minus DB/Storage: text mappings + choice groups → fill.
        field_values, report = fps.build_fill_plan(_text_mappings(), _PROFILE)
        choice_values, choice_report = fps.build_choice_fill(FORM, _PROFILE)
        field_values.update(choice_values)
        report.extend(choice_report)

        filled = fps.fill_acroform(self.pdf_bytes, field_values)
        report, pdf_count, _unmapped = fps.reconcile_report_against_pdf(filled, report)

        not_in_pdf = [f.form_field_id for f in report if f.status == fps.STATUS_NOT_IN_PDF]
        self.assertEqual(not_in_pdf, [], f"mapped fields that did not land in the real PDF: {not_in_pdf}")
        self.assertEqual(pdf_count, 172)

        fields = PdfReader(io.BytesIO(filled)).get_fields() or {}

        def _v(name):
            return fields.get(name, {}).get("/V")

        def _ticked(name):
            v = _v(name)
            return v is not None and str(v) not in ("", "/Off")

        # text, with format rules applied
        self.assertEqual(str(_v("applicantSurname")), "Diallo")
        self.assertEqual(str(_v("travelDocNumber")), "AB1234567")       # passport_format
        self.assertEqual(str(_v("applicantDateOfBirth")), "12/05/1990")  # dd/mm/yyyy
        self.assertEqual(str(_v("applicantNationality")), "SENEGALESE")  # uppercase
        # radios: the selected button ticks with the form's real /On state; siblings stay off
        self.assertTrue(_ticked("applicantGenderF"))
        self.assertTrue(_ticked("applicantMaritalMAR"))
        self.assertEqual(str(_v("applicantGenderF")), "/On", "real CERFA on-state must resolve to /On")
        self.assertFalse(_ticked("applicantGenderM"))
        self.assertFalse(_ticked("applicantMaritalCEL"))


if __name__ == "__main__":
    unittest.main()

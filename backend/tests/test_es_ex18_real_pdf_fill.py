"""End-to-end fill of the REAL Spanish EX-18 (RCE) AcroForm — third fillable government form.

The official Ministerio de Inclusión editable PDF uses Acrobat default field names
(TextoN / Casilla de verificaciónN). This fills the committed fixture through the
production path and checks the mapped identity fields land.

DB-free / Storage-free: template is the repo fixture; mappings parsed from the seed.
"""
import io
import re
import unittest
from pathlib import Path

from pypdf import PdfReader

from backend.app.services import form_prefill_service as fps

_ROOT = Path(__file__).resolve().parents[2]
_PDF = _ROOT / "docs" / "form-autofill" / "artifacts" / "es_ex18_rce_editable.pdf"
_MIGRATION = _ROOT / "supabase" / "migrations" / "20261143000000_es_ex18_rce_acroform_fields.sql"
FORM = "ES_ex18_v2024"

_TEXT = re.compile(
    r"'ES_ex18_v2024',\s*'[^']*',\s*'ES',\s*'eea_registration',\s*"
    r"'([^']+)',\s*'([^']*)',\s*'([^']+)',\s*'([^']*)',\s*(TRUE|FALSE),\s*'text'",
)


def _text_mappings():
    out = []
    for fid, label, vault, fmt, exact in _TEXT.findall(_MIGRATION.read_text(encoding="utf-8")):
        out.append({
            "form_field_id": fid,
            "form_field_label": label,
            "vault_field_path": vault,
            "format_rule": fmt or None,
            "exact_match_required": exact == "TRUE",
        })
    return out


_PROFILE = {
    "legal_last_name": "Diallo",
    "legal_first_name": "Awa",
    "passport_number": "ab 123 4567",
    "nationality": "French",
    "place_of_birth": "Dakar",
    "date_of_birth": "1990-05-12",
    "gender": "female",
    "marital_status": "married",
}


class EsEx18RealPdfFill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert _PDF.exists(), f"EX-18 fixture missing: {_PDF}"
        cls.pdf_bytes = _PDF.read_bytes()
        cls.mappings = _text_mappings()

    def test_fixture_is_the_real_ex18_acroform(self):
        reader = PdfReader(io.BytesIO(self.pdf_bytes))
        fields = reader.get_fields() or {}
        self.assertEqual(len(fields), 105)
        self.assertIn("Texto1", fields)
        self.assertIn("Casilla de verificación3", fields)
        text = (reader.pages[0].extract_text() or "")
        self.assertIn("EX-18", text)
        self.assertIn("Registro", text)

    def test_full_fill_lands_text_dob_and_checkboxes_in_the_real_form(self):
        field_values, report = fps.build_fill_plan(self.mappings, _PROFILE)
        choice_values, choice_report = fps.build_choice_fill(FORM, _PROFILE)
        field_values.update(choice_values)
        report.extend(choice_report)

        filled = fps.fill_acroform(self.pdf_bytes, field_values)
        report, _pdf_count, _unmapped = fps.reconcile_report_against_pdf(filled, report)

        not_in_pdf = [f.form_field_id for f in report if f.status == fps.STATUS_NOT_IN_PDF]
        self.assertEqual(not_in_pdf, [], f"mapped fields that did not land: {not_in_pdf}")

        fields = PdfReader(io.BytesIO(filled)).get_fields() or {}

        def _v(name):
            return str(fields.get(name, {}).get("/V"))

        self.assertEqual(_v("Texto5"), "Diallo")
        self.assertEqual(_v("Texto7"), "Awa")
        self.assertEqual(_v("Texto1"), "AB1234567")
        self.assertEqual(_v("Texto13"), "FRENCH")
        self.assertEqual(_v("Texto8"), "12")
        self.assertEqual(_v("Texto9"), "05")
        self.assertEqual(_v("Texto10"), "1990")
        self.assertEqual(_v("Texto11"), "Dakar")
        self.assertEqual(_v("Casilla de verificación3"), "/Yes")  # Mujer
        self.assertEqual(_v("Casilla de verificación5"), "/Yes")  # Casado
        # Unmapped sibling boxes stay off
        self.assertIn(_v("Casilla de verificación2"), ("None", "/Off"))
        self.assertIn(_v("Casilla de verificación1"), ("None", "/Off"))


if __name__ == "__main__":
    unittest.main()

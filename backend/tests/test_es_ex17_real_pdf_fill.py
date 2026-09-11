"""End-to-end fill of the REAL Spanish EX-17 (TIE) AcroForm — form-fill Build A, second form.

Proves the fill pipeline generalises past the France-Visas CERFA to a second real government
form with a different language and field-naming convention (Spanish, spaces/accents in field
names). Fills the official Punto de Acceso General form F94803 committed at
docs/form-autofill/artifacts/es_ex17_F94803.pdf through the production path and verifies at the
PDF level that the mapped text fields land with their format rules.

Only the clean /Tx fields the migration 20261136000000 seeds are exercised here; the split
date-of-birth and the Sexo / Estado Civil single-radio fields are a documented follow-up.

DB-free / Storage-free: the template is the repo fixture; mappings parsed from the migration.
"""
import io
import re
import unittest
from pathlib import Path

from pypdf import PdfReader

from backend.app.services import form_prefill_service as fps
from backend.app.services import fact_dictionary as fd

_ROOT = Path(__file__).resolve().parents[2]
_PDF = _ROOT / "docs" / "form-autofill" / "artifacts" / "es_ex17_F94803.pdf"
_MIGRATION = _ROOT / "supabase" / "migrations" / "20261136000000_es_ex17_tie_acroform_fields.sql"

# ES field ids carry spaces/accents, so match any single-quoted run (no escaped quotes in the seed).
_ROW = re.compile(
    r"'ES_ex17_v2024',\s*'[^']*',\s*'ES',\s*'residence',\s*"
    r"'([^']+)',\s*'([^']*)',\s*'([^']+)',\s*'([^']*)',\s*(TRUE|FALSE)",
)


def _mappings():
    text = _MIGRATION.read_text(encoding="utf-8")
    return [
        {"form_field_id": fid, "form_field_label": label, "vault_field_path": vault,
         "format_rule": fmt or None, "exact_match_required": exact == "TRUE"}
        for fid, label, vault, fmt, exact in _ROW.findall(text)
    ]


def _fact_governs(vault_path: str) -> bool:
    for f in fd._FACTS:
        if f.prefill_source and f.prefill_source.split(".")[-1] == vault_path:
            return True
        if vault_path in f.field_ids:
            return True
    return False


_PROFILE = {
    "legal_last_name": "Diallo",
    "legal_first_name": "Awa",
    "passport_number": "ab 123 4567",
    "nationality": "Senegalese",
    "place_of_birth": "Dakar",
}


class EsEx17RealPdfFill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert _PDF.exists(), f"EX-17 fixture missing: {_PDF}"
        cls.pdf_bytes = _PDF.read_bytes()
        cls.mappings = _mappings()

    def test_fixture_is_the_real_ex17_acroform(self):
        reader = PdfReader(io.BytesIO(self.pdf_bytes))
        fields = reader.get_fields() or {}
        self.assertGreaterEqual(len(fields), 60, "fixture is not the expected EX-17 AcroForm")
        self.assertIn("1er Apellido", fields)
        self.assertIn("PASAPORTE", fields)
        title = (reader.metadata or {}).get("/Title") or ""
        self.assertIn("TIE", title)

    def test_migration_seeds_real_fields_governed_by_the_dictionary(self):
        self.assertGreaterEqual(len(self.mappings), 5)
        real = set((PdfReader(io.BytesIO(self.pdf_bytes)).get_fields() or {}).keys())
        bogus = [m["form_field_id"] for m in self.mappings if m["form_field_id"] not in real]
        self.assertEqual(bogus, [], f"mapping field ids not in the real EX-17: {bogus}")
        ungoverned = [m["vault_field_path"] for m in self.mappings if not _fact_governs(m["vault_field_path"])]
        self.assertEqual(ungoverned, [], f"vault paths not governed by Build B: {ungoverned}")

    def test_full_fill_lands_text_fields_in_the_real_form(self):
        field_values, report = fps.build_fill_plan(self.mappings, _PROFILE)
        filled = fps.fill_acroform(self.pdf_bytes, field_values)
        report, _pdf_count, _unmapped = fps.reconcile_report_against_pdf(filled, report)

        not_in_pdf = [f.form_field_id for f in report if f.status == fps.STATUS_NOT_IN_PDF]
        self.assertEqual(not_in_pdf, [], f"mapped fields that did not land in the real EX-17: {not_in_pdf}")

        fields = PdfReader(io.BytesIO(filled)).get_fields() or {}
        self.assertEqual(str(fields.get("1er Apellido", {}).get("/V")), "Diallo")
        self.assertEqual(str(fields.get("Nombre", {}).get("/V")), "Awa")
        self.assertEqual(str(fields.get("PASAPORTE", {}).get("/V")), "AB1234567")       # passport_format
        self.assertEqual(str(fields.get("Nacionalidad", {}).get("/V")), "SENEGALESE")   # uppercase


if __name__ == "__main__":
    unittest.main()

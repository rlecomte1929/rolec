"""FR CERFA 14571 form-fill: the mapping must match the REAL AcroForm (form-fill Phase 1).

docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md proved the fillable France-Visas long-stay
form (ls_14571-05_fr_09) uses semantic English AcroForm field names, and that our original
mapping's French ids (nom, prenoms, …) had ZERO overlap — so a fill wrote nothing. The re-seed
migration 20261135000000 fixes that. These guards lock it to reality so it can't regress:

  1. every seeded form_field_id is a real field in the committed AcroForm artifact;
  2. every seeded vault_field_path is governed by the Build B fact dictionary;
  3. filling a template that has those real field names actually lands every value
     (reconcile_report_against_pdf reports 0 not-in-pdf).

DB-free and Storage-free: parses the migration SQL + the field artifact, uses the pure
form_prefill_service helpers against a synthetic AcroForm built with the real field names.
"""
import json
import re
import unittest
from pathlib import Path

from backend.app.services import form_prefill_service as fps
from backend.app.services import fact_dictionary as fd

_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION = _ROOT / "supabase" / "migrations" / "20261135000000_fr_cerfa_14571_real_acroform_fields.sql"
_ARTIFACT = _ROOT / "docs" / "form-autofill" / "artifacts" / "fr_cerfa_14571-05_acroform_fields.json"

# One INSERT row: form_id, form_name, 'FR', 'long_stay', field_id, label, vault_path, format, exact
_ROW = re.compile(
    r"'FR_cerfa_14571_v2024',\s*'[^']*',\s*'FR',\s*'long_stay',\s*"
    r"'([^']+)',\s*'([^']*)',\s*'([^']+)',\s*'([^']*)',\s*(TRUE|FALSE)",
    re.I,
)


def _seeded_mappings():
    """The FR CERFA mappings as build_fill_plan expects them, parsed from the migration."""
    text = _MIGRATION.read_text(encoding="utf-8")
    out = []
    for fid, label, vault, fmt, exact in _ROW.findall(text):
        out.append({
            "form_field_id": fid,
            "form_field_label": label,
            "vault_field_path": vault,
            "format_rule": fmt or None,
            "exact_match_required": exact.upper() == "TRUE",
        })
    return out


def _real_field_names():
    data = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    return {f["name"] for f in data["fields"]}


def _fact_governs(vault_path: str) -> bool:
    for f in fd._FACTS:
        if f.prefill_source and f.prefill_source.split(".")[-1] == vault_path:
            return True
        if vault_path in f.field_ids:
            return True
    return False


class FrCerfaRealAcroform(unittest.TestCase):
    def setUp(self):
        self.mappings = _seeded_mappings()

    def test_migration_seeds_the_expected_fields(self):
        self.assertTrue(_MIGRATION.exists(), "re-seed migration missing")
        self.assertGreaterEqual(len(self.mappings), 9, "expected the 9 real text-field mappings")

    def test_every_form_field_id_is_a_real_acroform_field(self):
        real = _real_field_names()
        bogus = sorted(m["form_field_id"] for m in self.mappings if m["form_field_id"] not in real)
        self.assertEqual(bogus, [], f"mapping field ids not present in the real CERFA AcroForm: {bogus}")

    def test_every_vault_path_is_governed_by_the_fact_dictionary(self):
        ungoverned = sorted({m["vault_field_path"] for m in self.mappings if not _fact_governs(m["vault_field_path"])})
        self.assertEqual(ungoverned, [], f"vault paths with no governing FactEntry (Build B): {ungoverned}")

    def test_fill_lands_every_value_in_a_real_field_name_template(self):
        # A case's vault profile, keyed by the imm_employee_profiles columns the mappings resolve.
        profile = {
            "legal_last_name": "Diallo",
            "legal_first_name": "Awa",
            "date_of_birth": "1990-05-12",
            "place_of_birth": "Dakar",
            "nationality": "Senegalese",
            "passport_number": "ab 123 4567",
            "passport_issue_date": "2021-03-01",
            "passport_expiry": "2031-03-01",
            "job_title": "Software Engineer",
        }
        field_values, report = fps.build_fill_plan(self.mappings, profile)
        # Every mapping resolved a value from the profile above.
        self.assertEqual(
            sorted(field_values), sorted(m["form_field_id"] for m in self.mappings),
            "a mapping did not resolve a value — check the profile keys match the vault paths",
        )
        # Build a template carrying the REAL field names and fill it.
        template = fps.build_synthetic_acroform(sorted(field_values))
        pdf = fps.fill_acroform(template, field_values)
        report, pdf_count, unmapped = fps.reconcile_report_against_pdf(pdf, report)

        not_in_pdf = [f.form_field_id for f in report if f.status == fps.STATUS_NOT_IN_PDF]
        self.assertEqual(not_in_pdf, [], f"values that did not land in the PDF: {not_in_pdf}")
        self.assertEqual(unmapped, 0, "every template field was addressed by a mapping")
        # format rules fired: passport uppercased + de-spaced, date reformatted dd/mm/yyyy.
        self.assertEqual(field_values["travelDocNumber"], "AB1234567")
        self.assertEqual(field_values["applicantDateOfBirth"], "12/05/1990")


if __name__ == "__main__":
    unittest.main()

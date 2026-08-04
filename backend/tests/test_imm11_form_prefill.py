"""
IMM-11 (AIQ-117) — immigration form library + PDF pre-fill service.

Covers the pure logic (format rules, fill planning, exact-match warnings), the
AcroForm fill round-trip against a synthetic template, and the
generate_prefilled_pdf orchestration with DB + Storage mocked.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.services import form_prefill_service as fps  # noqa: E402

DE_FIELDS = [
    "family_name", "given_names", "date_of_birth", "passport_number",
    "passport_country", "gross_annual_salary",
]

DE_MAPPINGS = [
    {"form_field_id": "family_name", "form_field_label": "Family name",
     "vault_field_path": "legal_last_name", "format_rule": "name_normalise",
     "exact_match_required": True, "max_length": None},
    {"form_field_id": "given_names", "form_field_label": "Given names",
     "vault_field_path": "legal_first_name", "format_rule": "name_normalise",
     "exact_match_required": True, "max_length": None},
    {"form_field_id": "date_of_birth", "form_field_label": "Date of birth",
     "vault_field_path": "date_of_birth", "format_rule": "dd/mm/yyyy",
     "exact_match_required": False, "max_length": None},
    {"form_field_id": "passport_number", "form_field_label": "Passport number",
     "vault_field_path": "passport_number", "format_rule": "passport_format",
     "exact_match_required": True, "max_length": None},
    {"form_field_id": "passport_country", "form_field_label": "Passport country",
     "vault_field_path": "passport_country", "format_rule": "uppercase",
     "exact_match_required": False, "max_length": 3},
    {"form_field_id": "gross_annual_salary", "form_field_label": "Salary",
     "vault_field_path": "salary_amount", "format_rule": None,
     "exact_match_required": False, "max_length": None},
]


class TestFormatRules(unittest.TestCase):
    def test_uppercase(self):
        self.assertEqual(fps.apply_format_rule("müller", "uppercase"), "MÜLLER")

    def test_dd_mm_yyyy(self):
        self.assertEqual(fps.apply_format_rule("1990-05-01", "dd/mm/yyyy"), "01/05/1990")

    def test_yyyy_mm_dd(self):
        self.assertEqual(fps.apply_format_rule("1990-05-01T00:00:00", "yyyy-mm-dd"), "1990-05-01")

    def test_passport_format(self):
        self.assertEqual(fps.apply_format_rule("x1 234 567", "passport_format"), "X1234567")

    def test_name_normalise_collapses_whitespace(self):
        self.assertEqual(fps.apply_format_rule("  Jean   Pierre  ", "name_normalise"), "Jean Pierre")

    def test_bool_renders_yes_no(self):
        self.assertEqual(fps.apply_format_rule(True, None), "Yes")
        self.assertEqual(fps.apply_format_rule(False, None), "No")

    def test_unknown_rule_falls_through(self):
        self.assertEqual(fps.apply_format_rule("abc", "no_such_rule"), "abc")


class TestBuildFillPlan(unittest.TestCase):
    def test_filled_blank_and_truncation(self):
        profile = {
            "legal_last_name": "Smith",
            "legal_first_name": "Jane",
            # date_of_birth missing -> blank
            "passport_number": "p1234567",
            "passport_country": "FRANCE",   # max_length 3 -> truncated
            "salary_amount": 60000,
        }
        values, report = fps.build_fill_plan(DE_MAPPINGS, profile)

        self.assertEqual(values["family_name"], "Smith")
        self.assertEqual(values["passport_number"], "P1234567")
        self.assertEqual(values["passport_country"], "FRA")   # truncated to 3
        self.assertEqual(values["gross_annual_salary"], "60000")
        self.assertNotIn("date_of_birth", values)

        by_id = {r.form_field_id: r for r in report}
        self.assertEqual(by_id["date_of_birth"].status, fps.STATUS_BLANK)
        self.assertEqual(by_id["family_name"].status, fps.STATUS_FILLED)

    def test_exact_match_apostrophe_triggers_warning(self):
        profile = {"legal_last_name": "O'Brien", "legal_first_name": "Sean",
                   "passport_number": "AB123", "passport_country": "IE",
                   "salary_amount": 50000}
        _, report = fps.build_fill_plan(DE_MAPPINGS, profile)
        by_id = {r.form_field_id: r for r in report}

        self.assertEqual(by_id["family_name"].status, fps.STATUS_WARNING)
        self.assertIsNotNone(by_id["family_name"].warning)
        # A clean exact-match field stays "filled", not warned.
        self.assertEqual(by_id["given_names"].status, fps.STATUS_FILLED)


class TestAcroformRoundTrip(unittest.TestCase):
    def test_synthetic_template_fills_and_reads_back(self):
        from pypdf import PdfReader
        import io

        template = fps.build_synthetic_acroform(["family_name", "given_names"])
        filled = fps.fill_acroform(template, {"family_name": "OBRIEN", "given_names": "SEAN"})

        fields = PdfReader(io.BytesIO(filled)).get_fields() or {}
        self.assertEqual(str(fields["family_name"].get("/V")), "OBRIEN")
        self.assertEqual(str(fields["given_names"].get("/V")), "SEAN")


class TestGeneratePrefilledPdf(unittest.TestCase):
    def test_orchestration_with_mocks(self):
        profile = {
            "id": "p-1",
            "legal_last_name": "Smith", "legal_first_name": "Jane",
            "date_of_birth": "1990-05-01", "passport_number": "p1234567",
            "passport_country": "FR", "salary_amount": 60000,
        }
        template = fps.build_synthetic_acroform(DE_FIELDS)

        with patch.object(fps, "_load_field_mappings", return_value=DE_MAPPINGS), \
             patch.object(fps, "_download_template", return_value=template), \
             patch.object(fps, "_upload_output", return_value="case-1/prefilled/DE_blue_card_v2024.pdf") as up, \
             patch.object(fps, "_signed_url", return_value="https://signed.example/x.pdf"):
            result = fps.generate_prefilled_pdf("DE_blue_card_v2024", "case-1", profile)

        self.assertEqual(result.download_url, "https://signed.example/x.pdf")
        self.assertTrue(result.pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(result.filled_count, 0)
        self.assertEqual(result.blank_count, 0)  # all DE fields present in profile
        up.assert_called_once()
        d = result.to_dict()
        self.assertEqual(d["form_id"], "DE_blue_card_v2024")
        self.assertIn("fields", d)

    def test_missing_mappings_raises(self):
        with patch.object(fps, "_load_field_mappings", return_value=[]):
            with self.assertRaises(ValueError):
                fps.generate_prefilled_pdf("nope", "case-1", {})


class TestFillReportTellsTheTruth(unittest.TestCase):
    """AIQ-1759. The report used to be derived from the VAULT before the PDF was opened, and
    unmatched field names are dropped silently by pypdf — so a mapping whose names don't match
    the template produced a blank PDF with an all-filled report and a working download link.
    On a government form carried to an appointment that is the worst failure available."""

    def test_flattened_template_raises_instead_of_returning_a_blank(self):
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
        import io as _io

        buf = _io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)   # a print form: no AcroForm at all
        c.drawString(50, 750, "DEMANDE DE VISA POUR UN LONG SEJOUR")
        c.save()

        with self.assertRaises(fps.TemplateNotFillableError):
            fps.fill_acroform(buf.getvalue(), {"nom": "LEBLANC"})

    def test_name_mismatch_is_reported_not_counted_as_filled(self):
        """The real CERFA calls it `applicantSurname`; our mapping says `nom`. Zero overlap."""
        template = fps.build_synthetic_acroform(["applicantSurname", "applicantFirstname"])
        # Deliberately write names the template does not have.
        filled = fps.fill_acroform(template, {"nom": "LEBLANC", "prenoms": "SOPHIE"})

        report = [
            fps.FieldFillStatus("nom", "legal_last_name", "Nom", fps.STATUS_FILLED, "LEBLANC"),
            fps.FieldFillStatus("prenoms", "legal_first_name", "Prenoms", fps.STATUS_FILLED, "SOPHIE"),
        ]
        report, pdf_count, unmapped = fps.reconcile_report_against_pdf(filled, report)

        self.assertTrue(all(f.status == fps.STATUS_NOT_IN_PDF for f in report))
        self.assertTrue(all(f.warning for f in report), "each must say why it didn't land")
        self.assertEqual(pdf_count, 2)
        self.assertEqual(unmapped, 2, "neither template field was addressed by the mapping")

        result = fps.PrefilledPdfResult(
            form_id="FR_cerfa_14571_v2024", case_id="c1", storage_path="p",
            download_url=None, field_fill_report=report,
        )
        self.assertEqual(result.filled_count, 0, "nothing reached the PDF")
        self.assertEqual(result.not_in_pdf_count, 2)
        self.assertEqual(result.to_dict()["not_in_pdf_count"], 2)

    def test_matching_names_still_report_filled(self):
        template = fps.build_synthetic_acroform(["family_name", "given_names"])
        filled = fps.fill_acroform(template, {"family_name": "OBRIEN", "given_names": "SEAN"})
        report = [
            fps.FieldFillStatus("family_name", "legal_last_name", "Family name",
                                fps.STATUS_FILLED, "OBRIEN"),
            fps.FieldFillStatus("given_names", "legal_first_name", "Given names",
                                fps.STATUS_WARNING, "SEAN", warning="exact-match check"),
        ]
        report, pdf_count, unmapped = fps.reconcile_report_against_pdf(filled, report)

        self.assertEqual(report[0].status, fps.STATUS_FILLED)
        self.assertEqual(report[1].status, fps.STATUS_WARNING, "a pre-existing warning survives")
        self.assertEqual(pdf_count, 2)
        self.assertEqual(unmapped, 0)

    def test_verification_failure_leaves_the_report_alone(self):
        """A corrupt output must not silently mark every field as missing."""
        report = [fps.FieldFillStatus("a", "a", "A", fps.STATUS_FILLED, "x")]
        out, pdf_count, unmapped = fps.reconcile_report_against_pdf(b"not a pdf", report)
        self.assertEqual(out[0].status, fps.STATUS_FILLED)
        self.assertEqual((pdf_count, unmapped), (0, 0))


if __name__ == "__main__":
    unittest.main()

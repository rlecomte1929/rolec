"""Radio/checkbox choice groups for AcroForm fill (form-fill Phase 1 follow-up).

FR CERFA gender + marital status are GROUPS of independent /Btn checkboxes (applicantGenderM/F/
Other; applicantMaritalCEL/MAR/SEP/DIV/VEU/AUT). One vault value ticks exactly one button — the
scalar text pipeline can't express that. build_choice_fill closes it. These lock:

  * value normalisation (English/French synonyms) → the correct button, one per group;
  * a missing value ticks nothing (never guess a protected attribute);
  * an end-to-end fill checks the selected box in a real-field-name AcroForm and the fill
    report tells the truth (reconcile confirms it landed).

DB-free / Storage-free: pure helpers + a synthetic AcroForm with the real CERFA button names.
"""
import unittest

from backend.app.services import form_prefill_service as fps

FORM = "FR_cerfa_14571_v2024"


class ChoiceResolution(unittest.TestCase):
    def _one(self, vault_path, value):
        vals, report = fps.build_choice_fill(FORM, {vault_path: value})
        return vals, report

    def test_gender_variants_map_to_one_button(self):
        for value, expected in [
            ("male", "applicantGenderM"), ("M", "applicantGenderM"), ("Homme", "applicantGenderM"),
            ("female", "applicantGenderF"), ("F", "applicantGenderF"), ("femme", "applicantGenderF"),
            ("non-binary", "applicantGenderOther"), ("x", "applicantGenderOther"),
        ]:
            vals, _ = self._one("gender", value)
            self.assertEqual(vals, {expected: fps.CHECKBOX_ON}, f"gender {value!r} → {expected}")

    def test_marital_variants_map_to_one_button(self):
        for value, expected in [
            ("single", "applicantMaritalCEL"), ("célibataire", "applicantMaritalCEL"),
            ("married", "applicantMaritalMAR"), ("marié", "applicantMaritalMAR"),
            ("separated", "applicantMaritalSEP"), ("divorced", "applicantMaritalDIV"),
            ("widowed", "applicantMaritalVEU"), ("veuve", "applicantMaritalVEU"),
            ("pacsé", "applicantMaritalAUT"),  # unknown → OTHER, never dropped
        ]:
            vals, _ = self._one("marital_status", value)
            self.assertEqual(vals, {expected: fps.CHECKBOX_ON}, f"marital {value!r} → {expected}")

    def test_missing_value_ticks_nothing(self):
        for missing in (None, "", "   "):
            vals, report = self._one("gender", missing)
            self.assertEqual(vals, {}, "a missing protected attribute must tick no button")
            self.assertTrue(report and report[0].status == fps.STATUS_BLANK)

    def test_full_profile_ticks_exactly_one_per_group(self):
        vals, report = fps.build_choice_fill(FORM, {"gender": "female", "marital_status": "married"})
        self.assertEqual(vals, {"applicantGenderF": fps.CHECKBOX_ON, "applicantMaritalMAR": fps.CHECKBOX_ON})
        self.assertTrue(all(r.status == fps.STATUS_FILLED for r in report))

    def test_unknown_form_has_no_groups(self):
        vals, report = fps.build_choice_fill("DE_blue_card_v2024", {"gender": "female"})
        self.assertEqual((vals, report), ({}, []))


class ChoiceFillEndToEnd(unittest.TestCase):
    def test_selected_checkbox_is_written_into_the_pdf(self):
        button_ids = [
            "applicantGenderM", "applicantGenderF", "applicantGenderOther",
            "applicantMaritalCEL", "applicantMaritalMAR", "applicantMaritalVEU",
        ]
        template = fps.build_synthetic_acroform([], checkbox_ids=button_ids)

        values, report = fps.build_choice_fill(FORM, {"gender": "female", "marital_status": "married"})
        pdf = fps.fill_acroform(template, values)
        report, _pdf_count, _unmapped = fps.reconcile_report_against_pdf(pdf, report)

        # The two selected buttons landed; nothing was reported not-in-pdf.
        self.assertEqual([f.form_field_id for f in report if f.status == fps.STATUS_FILLED],
                         ["applicantGenderF", "applicantMaritalMAR"])
        self.assertFalse([f for f in report if f.status == fps.STATUS_NOT_IN_PDF])

        # Verify at the PDF level: the selected checkboxes carry a value, the unselected do not.
        from pypdf import PdfReader
        import io as _io
        fields = PdfReader(_io.BytesIO(pdf)).get_fields() or {}

        def _on(name):
            v = fields.get(name, {}).get("/V")
            return v is not None and str(v) not in ("", "/Off")

        self.assertTrue(_on("applicantGenderF"))
        self.assertTrue(_on("applicantMaritalMAR"))
        self.assertFalse(_on("applicantGenderM"))
        self.assertFalse(_on("applicantMaritalCEL"))


if __name__ == "__main__":
    unittest.main()

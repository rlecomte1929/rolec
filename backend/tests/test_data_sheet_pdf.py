"""AIQ-1759 — the employee's takeaway data sheet.

What this replaced: a placeholder that drew two lines of Helvetica containing a comma-joined
dump of at most ten raw `snake_case_id: value` pairs. These tests pin the properties that make
the new sheet worth carrying to an appointment.
"""
from __future__ import annotations

import io
import unittest

from backend.app.services.data_sheet_pdf import render_data_sheet


def _text(pdf: bytes) -> str:
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join((p.extract_text() or "") for p in r.pages)


FIELDS = [
    {"id": "full_name", "label": "Full legal name", "label_nb": "Fullt juridisk navn",
     "section": "d_number", "position": 1, "required": True,
     "note": "Exactly as printed in your passport.",
     "portal_url": "https://www.skatteetaten.no/en/forms/d-number"},
    {"id": "passport_no", "label": "Passport number", "section": "d_number",
     "position": 2, "required": True},
    {"id": "tax_residency", "label": "Tax residency status", "section": "a1",
     "position": 3, "consult_professional": True},
    {"id": "no_address", "label": "Norwegian address", "section": "folkeregister",
     "position": 4, "required": True},
]
VALUES = {"full_name": "Sophie Leblanc", "passport_no": "19HK54321"}
SOURCES = {"full_name": "passport_ocr", "passport_no": "passport_ocr"}


class TestDataSheetPdf(unittest.TestCase):
    def setUp(self):
        self.pdf = render_data_sheet(
            title="Personal Relocation Data Sheet (France to Norway)",
            subtitle="Skatteetaten · Politiet",
            fields=FIELDS, values=VALUES, sources=SOURCES,
        )
        self.assertIsNotNone(self.pdf)
        self.text = _text(self.pdf)

    def test_is_a_real_pdf(self):
        self.assertTrue(self.pdf.startswith(b"%PDF"))

    def test_section_keys_are_humanised_with_the_issuing_authority(self):
        """Employees were shown raw keys like `d_number` as headings."""
        self.assertIn("D-number (Skatteetaten)", self.text)
        self.assertIn("A1 social-security certificate", self.text)
        self.assertNotIn("d_number", self.text)
        self.assertNotIn("folkeregister", self.text.lower().replace(
            "national registry / folkeregister (skatteetaten)", ""))

    def test_values_appear_with_their_provenance(self):
        self.assertIn("Sophie Leblanc", self.text)
        self.assertIn("From your passport scan", self.text)

    def test_unanswered_fields_are_shown_not_hidden(self):
        """The sheet doubles as a checklist — omitting a gap makes it look complete."""
        self.assertIn("Norwegian address", self.text)
        self.assertIn("Needs input", self.text)

    def test_consult_professional_carries_no_value(self):
        self.assertIn("Tax residency status", self.text)
        self.assertIn("Consult a regulated professional", self.text)

    def test_notes_and_portal_links_render(self):
        self.assertIn("Exactly as printed in your passport", self.text)
        self.assertIn("skatteetaten.no", self.text)

    def test_never_claims_to_be_an_official_form(self):
        self.assertIn("not an official", self.text)
        self.assertIn("confirm", self.text.lower())

    def test_unknown_section_degrades_readably(self):
        pdf = render_data_sheet(
            title="T", fields=[{"id": "x", "label": "X", "section": "some_new_step",
                                "position": 1}], values={},
        )
        self.assertIn("Some new step", _text(pdf))

    def test_no_fields_still_produces_a_document(self):
        pdf = render_data_sheet(title="Empty sheet", fields=[], values={})
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Empty sheet", _text(pdf))

    def test_markup_in_seeded_content_does_not_break_the_render(self):
        """Template content is data — an ampersand or angle bracket must not blow up the
        XML-ish paragraph markup reportlab uses."""
        pdf = render_data_sheet(
            title="A & B <test>",
            fields=[{"id": "x", "label": "Employer & co <Ltd>", "section": "s",
                     "position": 1, "note": "Bring <both> forms & the original"}],
            values={"x": "Value & <thing>"},
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Employer & co", _text(pdf))


class TestPdfRouteIsServedByTheLiveModule(unittest.TestCase):
    """`backend/app/routers/cases.py` still defines a near-identical `get_form_pdf`, but the
    app serves `cases_read`'s. Wiring the data sheet into `cases.py` produces a silent no-op —
    it did here first. This pins which module actually answers the request."""

    def test_form_pdf_route_resolves_to_cases_read(self):
        from backend.main import app

        handlers = [
            r.endpoint for r in app.routes
            if getattr(r, "path", "") == "/api/cases/{case_id}/forms/{form_id}/pdf"
        ]
        self.assertEqual(len(handlers), 1, "exactly one handler should own this path")
        self.assertEqual(
            handlers[0].__module__, "backend.app.routers.cases_read",
            "the PDF download is served by cases_read — wire changes there, not in cases.py",
        )

    def test_live_handler_reaches_the_data_sheet_renderer(self):
        """Guards the import path the placeholder branch uses."""
        import inspect

        from backend.app.routers import cases_read

        src = inspect.getsource(cases_read.get_form_pdf)
        self.assertIn("render_data_sheet", src)


if __name__ == "__main__":
    unittest.main()

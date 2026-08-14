"""AIQ-1770 — the localised field label is keyed off the template's language, not hardcoded.

Before this, three call sites read `label_nb` by name. That worked while Norway was the only
localised corridor and would have failed silently the moment a second arrived: a `label_de` on a
German sheet would have been ignored everywhere, rendering English labels with nothing to notice.

`test_a_german_sheet_would_have_been_english_before` is the one that matters — it fails against
the old hardcoded lookup and passes now. The rest pin the edges.
"""
from __future__ import annotations

import io
import unittest

from backend.app.services.data_sheet_pdf import render_data_sheet
from backend.app.services.localised_labels import (
    SUPPORTED_LABEL_LANGUAGES,
    label_key_for,
    localised_label,
)


def _text(pdf: bytes) -> str:
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join((p.extract_text() or "") for p in r.pages)


# A German sheet, shaped like the DE data-sheet will be: English label + label_de.
DE_FIELDS = [
    {"id": "full_name", "label": "Full legal name", "label_de": "Vollstaendiger Name",
     "section": "anmeldung", "position": 1, "required": True},
    {"id": "move_in_date", "label": "Date you moved in", "label_de": "Einzugsdatum",
     "section": "anmeldung", "position": 2, "required": True,
     "note": "Registration is due within two weeks of moving in."},
]

FR_FIELDS = [
    {"id": "birth_cert", "label": "Birth certificate with parents' names",
     "label_fr": "Extrait d'acte de naissance avec filiation",
     "section": "securite_sociale", "position": 1, "required": True},
]


class TestLabelKeyResolution(unittest.TestCase):
    def test_each_supported_language_maps_to_its_own_key(self):
        self.assertEqual(label_key_for("nb"), "label_nb")
        self.assertEqual(label_key_for("de"), "label_de")
        self.assertEqual(label_key_for("fr"), "label_fr")

    def test_english_has_no_second_label(self):
        """English IS the `label` column, so a `label_en` key would be a duplicate."""
        self.assertIsNone(label_key_for("en"))

    def test_unknown_language_does_not_invent_a_key(self):
        """Guessing `label_xx` would fabricate a convention instead of following one."""
        for lang in ("es", "it", "zz", "", None, "  "):
            self.assertIsNone(label_key_for(lang), f"should not invent a key for {lang!r}")

    def test_language_code_is_case_and_space_insensitive(self):
        """source_language is free text in the DB — no CHECK constraint guards its casing."""
        self.assertEqual(label_key_for(" DE "), "label_de")
        self.assertEqual(label_key_for("Nb"), "label_nb")


class TestLocalisedLabel(unittest.TestCase):
    def test_returns_the_label_in_the_templates_language(self):
        fd = {"label": "Full legal name", "label_de": "Vollstaendiger Name",
              "label_nb": "Fullt juridisk navn"}
        self.assertEqual(localised_label(fd, "de"), "Vollstaendiger Name")
        self.assertEqual(localised_label(fd, "nb"), "Fullt juridisk navn")

    def test_picks_the_language_asked_for_not_whichever_key_exists(self):
        """The bug this closes: a sheet must not fall back to another language's label."""
        fd = {"label": "Full legal name", "label_nb": "Fullt juridisk navn"}
        self.assertIsNone(localised_label(fd, "de"))

    def test_none_rather_than_the_english_label_when_absent(self):
        """None must stay distinguishable from 'seeded translation'.

        The editor renders a seeded label instantly and authoritatively, but machine-translates
        one that is missing. Returning the English label here would collapse that distinction.
        """
        self.assertIsNone(localised_label({"label": "Job title"}, "de"))

    def test_blank_and_whitespace_labels_count_as_absent(self):
        for value in ("", "   ", None):
            self.assertIsNone(localised_label({"label": "X", "label_de": value}, "de"))

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(localised_label({"label_de": "  Einzugsdatum "}, "de"), "Einzugsdatum")

    def test_english_template_has_no_localised_label(self):
        fd = {"label": "Full legal name", "label_de": "Vollstaendiger Name"}
        self.assertIsNone(localised_label(fd, "en"))


class TestDataSheetRendersTheTemplatesLanguage(unittest.TestCase):
    def test_a_german_sheet_would_have_been_english_before(self):
        """THE regression test. `label_de` reaches the PDF because the lookup follows
        source_language; the old hardcoded `fd.get("label_nb")` could never have found it."""
        pdf = render_data_sheet(
            title="Personal Relocation Data Sheet (France to Germany)",
            fields=DE_FIELDS, values={"full_name": "Camille Moreau"},
            source_language="de",
        )
        self.assertIsNotNone(pdf)
        text = _text(pdf)
        self.assertIn("Vollstaendiger Name", text)
        self.assertIn("Einzugsdatum", text)
        # The English label stays — the localised one is an aid, not a replacement.
        self.assertIn("Full legal name", text)

    def test_a_french_sheet_renders_french(self):
        pdf = render_data_sheet(
            title="Fiche de donnees", fields=FR_FIELDS, values={}, source_language="fr",
        )
        self.assertIsNotNone(pdf)
        self.assertIn("Extrait d'acte de naissance avec filiation", _text(pdf))

    def test_omitting_source_language_renders_english_only(self):
        """An older caller that does not pass the language must not crash or leak a label."""
        pdf = render_data_sheet(title="Sheet", fields=DE_FIELDS, values={})
        self.assertIsNotNone(pdf)
        text = _text(pdf)
        self.assertIn("Full legal name", text)
        self.assertNotIn("Vollstaendiger Name", text)

    def test_wrong_language_does_not_leak_another_languages_label(self):
        pdf = render_data_sheet(
            title="Sheet", fields=DE_FIELDS, values={}, source_language="nb",
        )
        self.assertIsNotNone(pdf)
        self.assertNotIn("Vollstaendiger Name", _text(pdf))


class TestFrontendAndBackendAgreeOnLanguages(unittest.TestCase):
    """The label key lives in Python and the toggle lives in TypeScript. Nothing but this test
    stops them drifting, and drift is silent: a language the backend resolves but the frontend
    does not list gets no toggle, so the seeded label is unreachable in the editor."""

    def test_fieldlang_lists_every_supported_language(self):
        import os
        import re

        here = os.path.dirname(os.path.abspath(__file__))
        field_row = os.path.join(
            here, "..", "..", "frontend", "src", "features", "platform-v2",
            "form-editor", "FieldRow.tsx",
        )
        if not os.path.exists(field_row):
            self.skipTest("frontend not present in this checkout")
        src = open(field_row, encoding="utf-8").read()
        match = re.search(r"export type FieldLang\s*=\s*([^;]+);", src)
        self.assertIsNotNone(match, "FieldLang union not found — did it get renamed?")
        declared = set(re.findall(r"'([a-z]{2})'", match.group(1)))
        missing = sorted(set(SUPPORTED_LABEL_LANGUAGES) - declared)
        self.assertEqual(
            missing, [],
            f"FieldLang is missing {missing}; a template in that language would resolve a "
            f"seeded label server-side that the editor can never show.",
        )


if __name__ == "__main__":
    unittest.main()

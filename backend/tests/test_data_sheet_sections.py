"""S1 — sections as first-class template data.

The properties that matter, in order of how much they would cost to get wrong:

  1. FR→NO renders IDENTICALLY through the new path. The migration changes where a section
     title comes from, not what the employee sees.
  2. A section with NO fields renders. France's headline fact is the ABSENCE of an arrival
     registration — no titre de séjour obligation, no mairie registration — which is a section
     that is a statement. Both renderers grouped BY FIELD, so this was impossible, and a silent
     gap reads to the employee as "ReloPass forgot this".
  3. One field, many sections, one stored value. Each authority appointment needs its own
     packet, but duplicating the field definition would write n rows for one datum.
  4. session_group is expressible — FINDINGS.md Appendix A.3, ratified 2026-07-30 and never
     built because there was nowhere to put it.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers.cases_read import _parse_sections  # noqa: E402
from backend.app.services.data_sheet_pdf import render_data_sheet  # noqa: E402

_SEED = os.path.join(_REPO_ROOT, "supabase", "migrations",
                     "20261015000000_seed_frno_data_sheet.sql")
_SECTIONS_MIGRATION = os.path.join(_REPO_ROOT, "supabase", "migrations",
                                   "20261026000000_form_templates_sections.sql")


def _text(pdf: bytes) -> str:
    import pypdf
    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)


def _seeded_fields():
    """The real shipped fields, parsed from the migration — not a copy that can drift."""
    sql = open(_SEED, encoding="utf-8").read()
    for blob in re.findall(r"'(\[\s*\{.*?\}\s*\])'::jsonb", sql, re.S):
        try:
            parsed = json.loads(blob)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, list) and parsed and "label" in parsed[0]:
            return parsed
    raise AssertionError(f"no fields array found in {_SEED}")


def _seeded_sections():
    sql = open(_SECTIONS_MIGRATION, encoding="utf-8").read()
    m = re.search(r"SET sections = '(\[[\s\S]*?\])'::jsonb", sql)
    assert m, f"no sections array found in {_SECTIONS_MIGRATION}"
    return json.loads(m.group(1))


class TestTheShippedBackfillIsConsistent(unittest.TestCase):
    """Guards over the migration itself, so a bad backfill fails here and not in prod."""

    def setUp(self):
        self.fields = _seeded_fields()
        self.sections = _seeded_sections()
        self.field_ids = {f["id"] for f in self.fields}

    def test_every_referenced_field_id_exists(self):
        referenced = {i for s in self.sections for i in s["field_ids"]}
        self.assertEqual(sorted(referenced - self.field_ids), [],
                         "a section references a field that is not in fields[]")

    def test_every_field_belongs_to_a_section(self):
        """Otherwise it silently disappears from the sheet once sections drive layout."""
        referenced = {i for s in self.sections for i in s["field_ids"]}
        self.assertEqual(sorted(self.field_ids - referenced), [],
                         "a seeded field is in no section and would not render")

    def test_section_ids_match_the_fields_section_keys(self):
        """The fallback path groups by fields[].section, so the two must agree or the
        fallback would render different sections from the primary path."""
        self.assertEqual({s["id"] for s in self.sections},
                         {f["section"] for f in self.fields})

    def test_numbers_are_a_contiguous_run_from_one(self):
        self.assertEqual([s["number"] for s in self.sections],
                         list(range(1, len(self.sections) + 1)))

    def test_titles_match_what_the_hardcoded_map_printed(self):
        """S1 changes where the title comes from, not what renders. If this fails, the
        no-regression diff in the PR is no longer meaningful."""
        from backend.app.services.data_sheet_pdf import _SECTION_LABELS
        for s in self.sections:
            self.assertEqual(s["title"], _SECTION_LABELS[s["id"]], s["id"])

    def test_appendix_a3_session_grouping_is_expressed(self):
        """FINDINGS A.3: D-number and skattekort are one Skatteetaten visit."""
        groups = {}
        for s in self.sections:
            if s.get("session_group"):
                groups.setdefault(s["session_group"], []).append(s["id"])
        self.assertEqual(groups, {"skatteetaten": ["d_number", "skattekort"]})


class TestRenderingFromSections(unittest.TestCase):
    def setUp(self):
        self.fields = _seeded_fields()
        self.sections = _seeded_sections()
        self.values = {"full_name": "Camille Moreau", "salary_amount_nok": "780000"}

    def test_the_sections_path_and_the_fallback_render_the_same_text(self):
        """THE no-regression property, asserted in the suite rather than only in a PR diff."""
        with_sections = render_data_sheet(
            title="T", fields=self.fields, values=self.values, sections=self.sections)
        fallback = render_data_sheet(
            title="T", fields=self.fields, values=self.values)
        self.assertIsNotNone(with_sections)
        self.assertEqual(_text(with_sections), _text(fallback))

    def test_a_section_with_no_fields_still_renders(self):
        """The France case. Impossible before S1 — both renderers grouped by field."""
        pdf = render_data_sheet(
            title="DE to FR", values={},
            fields=[{"id": "ssn", "label": "Social security number",
                     "section": "securite_sociale", "position": 1}],
            sections=[
                {"id": "no_registration", "number": 1,
                 "title": "Nothing to register on arrival",
                 "field_ids": []},
                {"id": "securite_sociale", "number": 2, "title": "Sécurité sociale (CPAM)",
                 "field_ids": ["ssn"]},
            ],
        )
        self.assertIsNotNone(pdf)
        text = _text(pdf)
        self.assertIn("Nothing to register on arrival", text)
        self.assertIn("Sécurité sociale (CPAM)", text)

    def test_one_field_can_appear_in_several_sections(self):
        """Each appointment needs its own packet. The field is declared ONCE."""
        fields = [{"id": "full_name", "label": "Full legal name", "position": 1}]
        pdf = render_data_sheet(
            title="T", fields=fields, values={"full_name": "Camille Moreau"},
            sections=[
                {"id": "a", "number": 1, "title": "Appointment A", "field_ids": ["full_name"]},
                {"id": "b", "number": 2, "title": "Appointment B", "field_ids": ["full_name"]},
            ],
        )
        text = _text(pdf)
        self.assertIn("Appointment A", text)
        self.assertIn("Appointment B", text)
        self.assertEqual(text.count("Camille Moreau"), 2,
                         "the value should render in both sections")

    def test_section_order_is_array_order_not_field_position(self):
        fields = [{"id": "x", "label": "X", "position": 1},
                  {"id": "y", "label": "Y", "position": 2}]
        pdf = render_data_sheet(
            title="T", fields=fields, values={},
            sections=[{"id": "second", "number": 1, "title": "ZZZ Later",
                       "field_ids": ["y"]},
                      {"id": "first", "number": 2, "title": "AAA Earlier",
                       "field_ids": ["x"]}],
        )
        text = _text(pdf)
        self.assertLess(text.index("ZZZ Later"), text.index("AAA Earlier"))

    def test_an_unknown_field_id_is_skipped_not_fatal(self):
        """A download must not 500 on a bad row; the consistency tests above catch it."""
        pdf = render_data_sheet(
            title="T", fields=[{"id": "real", "label": "Real", "position": 1}], values={},
            sections=[{"id": "s", "number": 1, "title": "Section",
                       "field_ids": ["real", "does_not_exist"]}],
        )
        self.assertIsNotNone(pdf)
        self.assertIn("Real", _text(pdf))

    def test_empty_sections_falls_back(self):
        for empty in ([], None):
            pdf = render_data_sheet(
                title="T", values={},
                fields=[{"id": "f", "label": "F", "section": "d_number", "position": 1}],
                sections=empty)
            self.assertIn("D-number (Skatteetaten)", _text(pdf), repr(empty))


class TestParseSections(unittest.TestCase):
    """Postgres hands back a decoded list; the SQLite test schema hands back TEXT."""

    def test_decodes_a_json_string(self):
        self.assertEqual(_parse_sections('[{"id": "a"}]'), [{"id": "a"}])

    def test_passes_a_list_through(self):
        self.assertEqual(_parse_sections([{"id": "a"}]), [{"id": "a"}])

    def test_degrades_to_empty_rather_than_raising(self):
        for bad in (None, "", "not json", "{}", 7, '{"not": "a list"}'):
            self.assertEqual(_parse_sections(bad), [], repr(bad))


class TestTheLoaderSelectsTheColumn(unittest.TestCase):
    def test_both_queries_select_sections(self):
        """C1 had to add source_language to _load_form_with_template for exactly this reason:
        a column the renderer needs but nobody selected resolves to None, and the feature
        silently does nothing."""
        src = open(os.path.join(_REPO_ROOT, "backend", "app", "routers", "cases_read.py"),
                   encoding="utf-8").read()
        self.assertEqual(src.count("ft.sections AS template_sections"), 2)

    def test_the_pdf_route_passes_sections_to_the_renderer(self):
        src = open(os.path.join(_REPO_ROOT, "backend", "app", "routers", "cases_read.py"),
                   encoding="utf-8").read()
        self.assertIn("sections=_parse_sections(form_row.get(\"template_sections\"))", src)


if __name__ == "__main__":
    unittest.main()

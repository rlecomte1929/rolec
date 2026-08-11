"""S1/F — the two renderers must not drift apart.

The whole reason S1 exists is that a section's presentation lived in two hardcoded maps —
`_SECTION_LABELS` in `backend/app/services/data_sheet_pdf.py` and `SECTION_LABELS` in
`frontend/src/pages/employee/FormEditorPage.tsx` — kept in step by a comment saying "keep the two
in step". A comment is not a mechanism. These tests are.

They are static (they read the TSX as text) because a Python suite cannot import TypeScript, and
because the failure being prevented is textual drift rather than a runtime behaviour. The
frontend's own behaviour is covered by its vitest suites.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.data_sheet_pdf import _SECTION_LABELS  # noqa: E402

_EDITOR = os.path.join(_REPO_ROOT, "frontend", "src", "pages", "employee", "FormEditorPage.tsx")
_DOSSIER_TS = os.path.join(_REPO_ROOT, "frontend", "src", "api", "dossier.ts")
_SECTIONS_MIGRATION = os.path.join(_REPO_ROOT, "supabase", "migrations",
                                   "20261025000000_form_templates_sections.sql")


def _tsx() -> str:
    return open(_EDITOR, encoding="utf-8").read()


def _ts_section_labels() -> dict:
    """Parse SECTION_LABELS out of the TSX."""
    src = _tsx()
    block = src.split("const SECTION_LABELS: Record<string, string> = {", 1)[1].split("};", 1)[0]
    return dict(re.findall(r"(\w+):\s*'([^']*)'", block))


class TestTheTwoFallbackMapsAgree(unittest.TestCase):
    """Only the FALLBACK path uses these maps now — a template with `sections` carries its own
    titles. They still have to agree, because 83 of 84 templates are on the fallback path."""

    def test_same_keys(self):
        self.assertEqual(sorted(_SECTION_LABELS), sorted(_ts_section_labels()))

    def test_same_values(self):
        ts = _ts_section_labels()
        differing = {k: (v, ts.get(k)) for k, v in _SECTION_LABELS.items() if ts.get(k) != v}
        self.assertEqual(differing, {}, f"PDF vs editor section labels differ: {differing}")

    def test_the_unsectioned_fallback_string_is_the_same_on_both_surfaces(self):
        """These disagreed until S1 — the PDF said "Your details", the editor said
        'Form fields'. The same sheet used two different words depending on whether you read it
        on screen or printed it."""
        from backend.app.services.data_sheet_pdf import _section_label
        pdf_fallback = _section_label("")
        m = re.search(r"const UNSECTIONED = '([^']*)'", _tsx())
        self.assertIsNotNone(m, "UNSECTIONED not found in the editor")
        self.assertEqual(m.group(1), pdf_fallback)


class TestBothSurfacesConsumeSections(unittest.TestCase):
    """A renderer that silently ignores `sections` would keep working and quietly lose the
    layout — which is exactly how `label_de` would have been dropped before C1."""

    def test_the_pdf_renderer_accepts_and_uses_sections(self):
        src = open(os.path.join(_REPO_ROOT, "backend", "app", "services",
                                "data_sheet_pdf.py"), encoding="utf-8").read()
        self.assertIn("sections: Optional[List[Dict[str, Any]]] = None", src)
        self.assertIn("if sections:", src)

    def test_the_editor_groups_by_sections_when_present(self):
        src = _tsx()
        self.assertIn("sections?: DossierFormSection[] | null", src)
        self.assertIn("if (sections && sections.length > 0)", src)
        self.assertIn("groupBySection(fields, formSummary?.template?.sections)", src)

    def test_the_api_type_declares_the_section_shape(self):
        ts = open(_DOSSIER_TS, encoding="utf-8").read()
        self.assertIn("export interface DossierFormSection", ts)
        for key in ("field_ids", "session_group", "callout_top", "callout_bottom",
                    "authority", "portal_url", "deadline_hint", "number", "title"):
            self.assertIn(key, ts, f"DossierFormSection is missing {key}")

    def test_the_editor_surfaces_the_section_metadata(self):
        """Storing authority/portal/deadline and never showing them would leave the facts
        buried in field notes, which is the problem S1 set out to fix."""
        src = _tsx()
        for expr in ("meta?.authority", "meta?.deadline_hint", "meta?.portal_url",
                     "meta?.callout_top", "meta?.callout_bottom"):
            self.assertIn(expr, src, f"the editor never renders {expr}")

    def test_the_editor_expresses_appendix_a3_session_grouping(self):
        src = _tsx()
        self.assertIn("session_group", src)
        self.assertIn("sharesSession", src)
        # A lone section sharing a key with nobody is not a group.
        self.assertIn("length > 1", src)


class TestTheBackfillIsRenderableByBoth(unittest.TestCase):
    def test_every_section_the_migration_seeds_has_what_both_renderers_read(self):
        sql = open(_SECTIONS_MIGRATION, encoding="utf-8").read()
        m = re.search(r"SET sections = '(\[[\s\S]*?\])'::jsonb", sql)
        self.assertIsNotNone(m)
        for sec in json.loads(m.group(1)):
            self.assertTrue(sec.get("id"), sec)
            self.assertTrue(sec.get("title"), sec)
            self.assertIsInstance(sec.get("number"), int, sec)
            self.assertIsInstance(sec.get("field_ids"), list, sec)
            # Optional keys must be PRESENT (possibly null) so a renderer reading them does not
            # have to distinguish "absent" from "empty".
            for key in ("authority", "portal_url", "deadline_hint", "session_group",
                        "callout_top", "callout_bottom"):
                self.assertIn(key, sec, f"{sec['id']} omits {key}")


if __name__ == "__main__":
    unittest.main()

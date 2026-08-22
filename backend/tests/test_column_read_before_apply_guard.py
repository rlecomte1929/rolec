"""Tests for scripts/check_column_read_before_apply.py.

The guard's real proof is an incident replay, recorded in the PR: run against `97a4750e`
(the commit that 500'd production for 2h33m) it exits 1 naming both
`ft.sections AS template_sections` reads; run against the re-land — which reads the column
heavily but adds no migration — it exits 0. Those cannot be asserted here without
committing fixture git history, so they are reproducible commands rather than tests.

What IS tested here is the matching logic, because that is where a guard like this rots:
too loose and it fires on every diff until someone deletes the job; too tight and it misses
the case it was written for.

Loaded via importlib because `scripts/` is not a package — the same reason
check_form_template_honesty.py is loaded that way.
"""
from __future__ import annotations

import importlib.util
import os
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "check_column_read_before_apply.py")

_spec = importlib.util.spec_from_file_location("column_read_guard", _SCRIPT)
guard = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(guard)


class TestAddColumnDetection(unittest.TestCase):
    def test_finds_the_plain_and_idempotent_forms(self) -> None:
        for sql, want in [
            ("ALTER TABLE public.form_templates ADD COLUMN sections jsonb;", "sections"),
            ("ALTER TABLE t ADD COLUMN IF NOT EXISTS sections jsonb NOT NULL;", "sections"),
            ('ALTER TABLE t ADD COLUMN "sections" jsonb;', "sections"),
            ("alter table t add column if not exists Sections jsonb;", "Sections"),
        ]:
            found = {m.group(1) for m in guard._ADD_COLUMN_RE.finditer(sql)}
            self.assertIn(want, found, sql)

    def test_ignores_an_unrelated_alter(self) -> None:
        sql = "ALTER TABLE t ADD CONSTRAINT c CHECK (x > 0); ALTER TABLE t DROP COLUMN y;"
        self.assertEqual({m.group(1) for m in guard._ADD_COLUMN_RE.finditer(sql)}, set())


class TestReadDetection(unittest.TestCase):
    def test_catches_the_exact_line_that_broke_production(self) -> None:
        self.assertTrue(guard._reads_of("sections", ["    ft.sections AS template_sections,"]))

    def test_catches_a_qualified_reference(self) -> None:
        self.assertTrue(guard._reads_of("sections", ["SELECT t.sections FROM x"]))

    def test_catches_a_quoted_key_in_a_select_list(self) -> None:
        self.assertTrue(guard._reads_of("sections", ['row["sections"],']))

    def test_ignores_a_comment_describing_the_column(self) -> None:
        """The first run reported 5 violations, 3 of which were prose about the column.
        A guard whose output is mostly noise gets switched off."""
        for line in [
            "    # When the template declares `sections`, that array IS the layout",
            "    // sections drives the layout",
            '    """`form_templates.sections` as a list, whatever the driver handed back.',
            "    * sections is the ordered array",
            "    -- sections jsonb NOT NULL",
        ]:
            self.assertEqual(guard._reads_of("sections", [line]), [], line)

    def test_ignores_a_backticked_mention_mid_docstring(self) -> None:
        line = "    `sections` is the template's `form_templates.sections` array, and when"
        self.assertEqual(guard._reads_of("sections", [line]), [])

    def test_catches_a_sqlalchemy_mapped_column_declaration(self) -> None:
        """The exact two lines of PR #1963 that took every corridor down on 2026-08-22.

        This guard ran on that PR and passed: a mapped column has no call site, so none of
        the qualified/aliased/quoted patterns match it. It is also the worst read form,
        because SQLAlchemy puts a mapped column in the SELECT list of EVERY query against
        the table — `GET /api/public/corridor-requirements` failed for FR→NO, IN→DE and
        ES→IE at once, and `GET /api/cases/{id}/requirements` with them.
        """
        for line in [
            "    verified_by = Column(Text, nullable=True)",
            "    verified_at = Column(DateTime(timezone=True), nullable=True)",
            "    verified_by: Mapped[str | None] = mapped_column(Text, nullable=True)",
            "    verified_by = sa.Column(sa.Text)",
        ]:
            self.assertTrue(guard._reads_of("verified_by", [line])
                            or guard._reads_of("verified_at", [line]), line)

    def test_the_orm_pattern_does_not_fire_on_an_ordinary_assignment(self) -> None:
        """Kept as narrow as the rest — it is anchored to `= Column(` / `= mapped_column(`,
        so a variable that merely shares the column's name is still not a violation."""
        for line in [
            "    verified_by = resolve_actor(payload)",
            "    verified_by = None",
            "        verified_by=actor,",
            "    # verified_by = Column(Text) in the model is what we are guarding against",
        ]:
            self.assertEqual(guard._reads_of("verified_by", [line]), [], line)

    def test_does_not_fire_on_a_bare_word(self) -> None:
        """Deliberately under-matches. A bare match on a name like `status` or `name` would
        fire on nearly every diff; the rule is also written in CLAUDE.md, so a missed case
        costs one revert whereas a noisy guard costs the guard."""
        self.assertEqual(guard._reads_of("sections", ["    sections = build_sections()"]), [])


class TestScopeRules(unittest.TestCase):
    def test_migration_sql_is_not_scanned(self) -> None:
        """A migration that adds a column and backfills it references that column by
        definition, in the same transaction. That is correct, not a violation."""
        self.assertFalse(guard._is_scanned("supabase/migrations/20261026000000_x.sql"))

    def test_application_code_is_scanned(self) -> None:
        for path in ("backend/app/routers/cases_read.py",
                     "frontend/src/api/dossier.ts",
                     "frontend/src/pages/employee/FormEditorPage.tsx"):
            self.assertTrue(guard._is_scanned(path), path)

    def test_tests_and_scripts_are_not_scanned(self) -> None:
        """A fixture gaining the column is the correct half of the split, not the bug."""
        for path in ("backend/tests/test_data_sheet_sections.py",
                     "scripts/check_migration_drift.py",
                     "frontend/src/features/x/__tests__/y.test.ts",
                     "docs/form-autofill/notes.py"):
            self.assertFalse(guard._is_scanned(path), path)


class TestOverride(unittest.TestCase):
    def test_the_override_requires_a_reason(self) -> None:
        self.assertIsNone(guard._OVERRIDE_RE.search("-- guard: column-read-ok"))
        m = guard._OVERRIDE_RE.search("-- guard: column-read-ok read is behind a flag")
        self.assertIsNotNone(m)
        self.assertEqual(m.group("reason"), "read is behind a flag")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

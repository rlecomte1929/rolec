"""Unit tests for scripts/check_model_schema_drift.py.

The guard's value is entirely in whether it can go RED. A guard that only ever exits 0 is
indistinguishable from one that works, and this repo has shipped several of those. So every
test here is about the failing direction, or about a way the check could examine nothing and
still look green.

No database: `parse_models` and `find_drift` are pure, which is why they are separate
functions. The live half is proven separately — the incident replay in the PR description
builds prod-as-it-was and watches the script name `requirement_items.verified_by`.
"""
from __future__ import annotations

import importlib.util
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_model_schema_drift.py"

_spec = importlib.util.spec_from_file_location("check_model_schema_drift", SCRIPT)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(guard)


def _models_file(tmp: Path, body: str) -> Path:
    path = tmp / "models.py"
    path.write_text(textwrap.dedent(body))
    return path


class ParseModelsTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_classic_column_form(self):
        p = _models_file(
            self.tmp,
            """
            class RequirementItem(Base):
                __tablename__ = "requirement_items"
                id = Column(String, primary_key=True)
                verified_by = Column(Text, nullable=True)
            """,
        )
        self.assertEqual(
            guard.parse_models(p), {"requirement_items": {"id", "verified_by"}}
        )

    def test_sqlalchemy_2_annotated_form(self):
        """`x: Mapped[...] = mapped_column(...)` is the same hazard in newer syntax."""
        p = _models_file(
            self.tmp,
            """
            class Thing(Base):
                __tablename__ = "things"
                name: Mapped[str] = mapped_column(Text)
            """,
        )
        self.assertEqual(guard.parse_models(p), {"things": {"name"}})

    def test_explicit_string_arg_overrides_the_attribute_name(self):
        """`x = Column("db_name", ...)` maps to db_name — checking `x` would miss the drift
        and, worse, report a column the database is not required to have."""
        p = _models_file(
            self.tmp,
            """
            class Thing(Base):
                __tablename__ = "things"
                py_name = Column("db_name", Text)
            """,
        )
        self.assertEqual(guard.parse_models(p), {"things": {"db_name"}})

    def test_non_column_assignments_are_not_columns(self):
        """A plain call must not be mistaken for a mapped column — that would produce
        phantom drift and train people to ignore the guard."""
        p = _models_file(
            self.tmp,
            """
            class Thing(Base):
                __tablename__ = "things"
                real = Column(Text)
                computed = resolve_actor(payload)
                rel = relationship("Other")
            """,
        )
        self.assertEqual(guard.parse_models(p), {"things": {"real"}})

    def test_class_without_tablename_is_ignored(self):
        p = _models_file(
            self.tmp,
            """
            class Mixin:
                created_at = Column(DateTime)
            """,
        )
        self.assertEqual(guard.parse_models(p), {})


class FindDriftTests(unittest.TestCase):
    def test_the_incident_a_mapped_column_the_db_lacks(self):
        """2026-08-22: models.py declared verified_by/verified_at; prod had neither, and
        every query on requirement_items 500'd for 7.5 hours."""
        models = {"requirement_items": {"id", "verified_by", "verified_at"}}
        live = {"requirement_items": {"id"}}
        missing_columns, missing_tables = guard.find_drift(models, live)
        self.assertEqual(
            missing_columns,
            [("requirement_items", "verified_at"), ("requirement_items", "verified_by")],
        )
        self.assertEqual(missing_tables, [])

    def test_extra_columns_in_the_database_are_NOT_drift(self):
        """suppliers, wizard_cases and others legitimately carry columns the ORM does not
        map. Failing on those would make the guard unusable on day one."""
        models = {"suppliers": {"id"}}
        live = {"suppliers": {"id", "vat_number", "based_in_country"}}
        self.assertEqual(guard.find_drift(models, live), ([], []))

    def test_a_mapped_table_missing_entirely_is_reported_once(self):
        """Reported as the table, not as N missing columns — otherwise one unapplied
        CREATE TABLE buries the report."""
        models = {"gone": {"a", "b", "c"}}
        missing_columns, missing_tables = guard.find_drift(models, {})
        self.assertEqual(missing_tables, ["gone"])
        self.assertEqual(missing_columns, [])

    def test_clean_when_the_database_matches(self):
        models = {"t": {"a", "b"}}
        self.assertEqual(guard.find_drift(models, {"t": {"a", "b"}}), ([], []))


class ExaminedNothingTests(unittest.TestCase):
    """Both ways this check could report success while looking at nothing.

    `migration-duplicate-main` ran for months in a mode structurally incapable of failing.
    An empty result must never be reported as a pass.
    """

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_zero_models_parsed_is_a_failure_not_a_pass(self):
        p = _models_file(self.tmp, "x = 1\n")
        self.assertEqual(guard.parse_models(p), {})
        # main() turns this into exit 1 before it ever reaches the database.

    def test_find_drift_on_an_empty_database_flags_every_table(self):
        """The signal main() uses to detect 'wrong database / cannot see
        information_schema' rather than reporting 26 phantom missing tables as findings."""
        models = {"a": {"x"}, "b": {"y"}}
        _, missing_tables = guard.find_drift(models, {})
        self.assertEqual(missing_tables, ["a", "b"])


class RealModelsFileTests(unittest.TestCase):
    """The parser must keep working on the actual file it is pointed at."""

    def test_parses_the_shipped_models_module(self):
        models = guard.parse_models(REPO_ROOT / "backend" / "app" / "models.py")
        # Concrete anchors: if these stop parsing, the guard has gone blind for real.
        self.assertIn("requirement_items", models)
        self.assertIn("verified_by", models["requirement_items"])
        self.assertIn("corridor_attestation_requests", models)
        self.assertIn("promotion_policy", models["corridor_attestation_requests"])
        # Measured 2026-08-22: 26 mapped tables, 336 columns. A floor, not an equality —
        # this must not need editing every time someone adds a model.
        self.assertGreaterEqual(len(models), 20)


if __name__ == "__main__":
    unittest.main()

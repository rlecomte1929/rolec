"""[Stage 9 · Phase 1] The catchment primitives, against a real SQLite engine.

The load-bearing tests here are the negatives. Default-on neighbours are only safe because a
neighbour with nobody who can do the job is never added, and the whole sourcing rewrite is only
honest because an unknown base country is treated as NOT eligible rather than eligible-anywhere.

Also pins the property that makes this module safe to merge before its migrations are applied:
nothing imports it.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import unittest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app.services.vendor_catchment import (  # noqa: E402
    DEFAULT_SIDE,
    VALID_SIDES,
    has_eligible_vendors,
    neighbours_of,
    sourcing_side,
)

_SCHEMA = [
    """CREATE TABLE supplier_service_categories (
         code text PRIMARY KEY,
         sourcing_side text NOT NULL DEFAULT 'destination'
       )""",
    """CREATE TABLE country_adjacency (
         country_a text NOT NULL,
         country_b text NOT NULL,
         relation_type text NOT NULL,
         default_included boolean NOT NULL DEFAULT 1,
         PRIMARY KEY (country_a, country_b)
       )""",
    """CREATE TABLE suppliers (
         id text PRIMARY KEY,
         name text,
         based_in_country text
       )""",
    """CREATE TABLE supplier_service_capabilities (
         supplier_id text NOT NULL,
         service_category text NOT NULL,
         country_code text,
         coverage_scope_type text
       )""",
    """CREATE TABLE supplier_service_area_coverage (
         supplier_id text NOT NULL,
         service_category text NOT NULL,
         area_id text
       )""",
    """CREATE TABLE supplier_accreditations (
         supplier_id text NOT NULL,
         body text NOT NULL,
         status text NOT NULL
       )""",
]

# The §A.2 mapping, exactly as the migration writes it.
_CATEGORIES = [
    ("movers", "origin"),
    ("tax_finance", "both"),
    ("rmc", "either"),
    ("healthcare_ipmi", "either"),
    ("dsp", "destination"),
    ("housing_agencies", "destination"),
    ("schools", "destination"),
    ("banks", "destination"),
    ("legal_admin", "destination"),
    ("language_cultural", "destination"),
    ("partner_family", "destination"),
]

# Pairs as the migration seeds them: listed once, both directions written.
_ADJACENCY = [
    ("FR", "DE", "land_border", True),
    ("FR", "BE", "land_border", True),
    ("FR", "ES", "land_border", True),
    ("FR", "IT", "land_border", True),
    ("FR", "CH", "land_border", True),
    ("FR", "LU", "land_border", True),
    ("NO", "SE", "land_border", True),
    ("FR", "GB", "short_sea", False),
    ("GB", "IE", "short_sea", False),
    ("DK", "SE", "short_sea", False),
    ("ES", "MA", "land_border", False),
    ("PL", "UA", "land_border", False),
    ("FI", "RU", "land_border", False),
]


def _engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        future=True,
    )
    with eng.begin() as conn:
        for ddl in _SCHEMA:
            conn.execute(text(ddl))
        for code, side in _CATEGORIES:
            conn.execute(
                text("INSERT INTO supplier_service_categories (code, sourcing_side) "
                     "VALUES (:c, :s)"),
                {"c": code, "s": side},
            )
        for a, b, rel, inc in _ADJACENCY:
            for x, y in ((a, b), (b, a)):   # symmetric, same as the seed
                conn.execute(
                    text("INSERT INTO country_adjacency "
                         "(country_a, country_b, relation_type, default_included) "
                         "VALUES (:a, :b, :r, :i)"),
                    {"a": x, "b": y, "r": rel, "i": inc},
                )
    return eng


def _add_supplier(conn, sid, based_in, category, *,
                  scope="country", area=None, accred=None, accred_status="verified"):
    conn.execute(text("INSERT INTO suppliers (id, name, based_in_country) "
                      "VALUES (:i, :n, :b)"),
                 {"i": sid, "n": sid, "b": based_in})
    conn.execute(text("INSERT INTO supplier_service_capabilities "
                      "(supplier_id, service_category, coverage_scope_type) "
                      "VALUES (:i, :c, :s)"),
                 {"i": sid, "c": category, "s": scope})
    if area:
        conn.execute(text("INSERT INTO supplier_service_area_coverage "
                          "(supplier_id, service_category, area_id) VALUES (:i, :c, :a)"),
                     {"i": sid, "c": category, "a": area})
    if accred:
        conn.execute(text("INSERT INTO supplier_accreditations (supplier_id, body, status) "
                          "VALUES (:i, :b, :s)"),
                     {"i": sid, "b": accred, "s": accred_status})


class SourcingSideTests(unittest.TestCase):
    def setUp(self):
        self.eng = _engine()

    def test_the_a2_mapping_is_what_the_migration_wrote(self):
        with self.eng.connect() as conn:
            for code, expected in _CATEGORIES:
                self.assertEqual(sourcing_side(conn, code), expected, code)

    def test_movers_is_the_only_origin_category(self):
        """The whole point of the rewrite. If a second category becomes origin-sourced that is
        a product decision, not a drive-by edit."""
        with self.eng.connect() as conn:
            origin = [c for c, _ in _CATEGORIES if sourcing_side(conn, c) == "origin"]
        self.assertEqual(origin, ["movers"])

    def test_seven_categories_keep_the_destination_default(self):
        with self.eng.connect() as conn:
            dest = [c for c, _ in _CATEGORIES if sourcing_side(conn, c) == "destination"]
        self.assertEqual(len(dest), 7)

    def test_an_unknown_category_behaves_as_the_product_does_today(self):
        with self.eng.connect() as conn:
            self.assertEqual(sourcing_side(conn, "not_a_category"), DEFAULT_SIDE)
            self.assertEqual(sourcing_side(conn, ""), DEFAULT_SIDE)

    def test_a_value_outside_the_check_degrades_rather_than_propagates(self):
        with self.eng.begin() as conn:
            conn.execute(text("INSERT INTO supplier_service_categories (code, sourcing_side) "
                              "VALUES ('weird', 'sideways')"))
        with self.eng.connect() as conn:
            self.assertEqual(sourcing_side(conn, "weird"), DEFAULT_SIDE)

    def test_every_declared_side_is_one_the_check_permits(self):
        self.assertEqual({s for _, s in _CATEGORIES}, VALID_SIDES - set())


class NeighbourTests(unittest.TestCase):
    def setUp(self):
        self.eng = _engine()

    def test_land_borders_are_default_included(self):
        with self.eng.connect() as conn:
            self.assertEqual(
                neighbours_of(conn, "FR"),
                {"DE", "BE", "ES", "IT", "CH", "LU"},
            )

    def test_short_sea_is_excluded_by_default(self):
        """A Channel crossing is not a drive-over move."""
        with self.eng.connect() as conn:
            self.assertNotIn("GB", neighbours_of(conn, "FR"))
            self.assertNotIn("IE", neighbours_of(conn, "GB"))
            self.assertNotIn("SE", neighbours_of(conn, "DK"))

    def test_cross_bloc_land_borders_are_excluded_by_default(self):
        with self.eng.connect() as conn:
            self.assertNotIn("MA", neighbours_of(conn, "ES"))
            self.assertNotIn("UA", neighbours_of(conn, "PL"))
            self.assertNotIn("RU", neighbours_of(conn, "FI"))

    def test_they_are_visible_when_hr_asks_for_the_full_list(self):
        """HR extending deliberately must be able to SEE a border before choosing it."""
        with self.eng.connect() as conn:
            self.assertIn("GB", neighbours_of(conn, "FR", default_included_only=False))
            self.assertIn("MA", neighbours_of(conn, "ES", default_included_only=False))

    def test_adjacency_is_symmetric_including_default_included(self):
        """An asymmetry is a silent one-way border: vendors visible FR->DE but not DE->FR.
        The seed writes both directions from one row so this cannot drift."""
        with self.eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT country_a, country_b, relation_type, default_included "
                "FROM country_adjacency")).fetchall()
            index = {(r[0], r[1]): (r[2], bool(r[3])) for r in rows}
        for (a, b), payload in index.items():
            self.assertIn((b, a), index, f"{a}->{b} has no reverse row")
            self.assertEqual(index[(b, a)], payload,
                             f"{a}<->{b} disagree on relation/default_included")

    def test_a_country_with_no_row_has_no_neighbours(self):
        with self.eng.connect() as conn:
            self.assertEqual(neighbours_of(conn, "AU"), set())
            self.assertEqual(neighbours_of(conn, None), set())

    def test_australia_is_never_adjacent_to_norway(self):
        """The 177 Sydney-for-Norway approvals must keep failing C1/C6. If a change here makes
        them pass, the change is wrong."""
        with self.eng.connect() as conn:
            for flag in (True, False):
                self.assertNotIn("AU", neighbours_of(conn, "NO", default_included_only=flag))
                self.assertNotIn("AU", neighbours_of(conn, "FR", default_included_only=flag))


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.eng = _engine()

    def test_a_verified_network_accreditation_evidences_reach(self):
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers",
                          accred="FIDI Global Alliance / FAIM Plus (auditor: EY)")
        with self.eng.connect() as conn:
            self.assertTrue(has_eligible_vendors(conn, "FR", "movers", "NO"))

    def test_a_merely_claimed_accreditation_does_not(self):
        """`claimed` means someone published a membership, not that we checked it."""
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers",
                          accred="FIDI Global Alliance / FAIM (auditor: EY)",
                          accred_status="claimed")
        with self.eng.connect() as conn:
            self.assertFalse(has_eligible_vendors(conn, "FR", "movers", "NO"))

    def test_global_coverage_evidences_reach(self):
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers", scope="global")
        with self.eng.connect() as conn:
            self.assertTrue(has_eligible_vendors(conn, "FR", "movers", "NO"))

    def test_an_explicit_service_area_row_evidences_reach(self):
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers", area="NO")
        with self.eng.connect() as conn:
            self.assertTrue(has_eligible_vendors(conn, "FR", "movers", "NO"))
            self.assertFalse(has_eligible_vendors(conn, "FR", "movers", "SG"))

    def test_presence_without_reach_is_not_eligible(self):
        """A Paris mover with no Nordic network cannot quote Paris->Oslo. Addendum A line 34."""
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers")
        with self.eng.connect() as conn:
            self.assertFalse(has_eligible_vendors(conn, "FR", "movers", "NO"))

    def test_an_unknown_base_country_is_not_eligible(self):
        """NULL means we never established where they are. Treating unknown as
        eligible-anywhere is how a Singapore mover reaches a Paris->Oslo slate."""
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", None, "movers", scope="global")
        with self.eng.connect() as conn:
            self.assertFalse(has_eligible_vendors(conn, "FR", "movers", "NO"))
            self.assertFalse(has_eligible_vendors(conn, None, "movers", "NO"))

    def test_the_category_must_match(self):
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers", scope="global")
        with self.eng.connect() as conn:
            self.assertFalse(has_eligible_vendors(conn, "FR", "housing_agencies", "NO"))

    def test_a_neighbour_with_zero_eligible_vendors_is_false(self):
        """This is what makes default-on neighbours safe rather than noisy — the caller drops
        such a country from the catchment and the UI never renders a chip for it."""
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers", scope="global")
        with self.eng.connect() as conn:
            self.assertTrue(has_eligible_vendors(conn, "FR", "movers", "NO"))
            self.assertFalse(has_eligible_vendors(conn, "DE", "movers", "NO"))

    def test_country_input_is_normalised(self):
        with self.eng.begin() as conn:
            _add_supplier(conn, "s1", "FR", "movers", area="NO")
        with self.eng.connect() as conn:
            self.assertTrue(has_eligible_vendors(conn, " fr ", "movers", "no"))


class InertnessTests(unittest.TestCase):
    """The property that makes this module safe to merge before its migrations are applied."""

    def test_nothing_imports_vendor_catchment(self):
        root = pathlib.Path(_REPO_ROOT)
        # IMPORTS only, not mentions. A docstring naming the module is prose — matching it
        # made this fail on `base_country.py`, whose docstring merely explains that
        # has_eligible_vendors treats NULL as not-eligible. The column-read guard learned the
        # same lesson: 3 of its first 5 hits were prose.
        pattern = re.compile(
            r"^\s*(?:from\s+\S*vendor_catchment\s+import\b"
            r"|from\s+\S+\s+import\s+[^#\n]*\bvendor_catchment\b"
            r"|import\s+\S*\bvendor_catchment\b)",
            re.MULTILINE,
        )
        offenders = []
        for path in list(root.glob("backend/**/*.py")) + list(root.glob("scripts/**/*.py")):
            parts = set(path.parts)
            if {".venv", "node_modules", "__pycache__", ".claude"} & parts:
                continue
            if path.name in ("vendor_catchment.py", "test_vendor_catchment.py"):
                continue
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if pattern.search(body):
                offenders.append(str(path.relative_to(root)))
        self.assertEqual(
            offenders, [],
            "vendor_catchment is imported by "
            f"{offenders}. Its columns are committed but applied out-of-band, so a request "
            "path that reads them 500s until an operator applies them. Wire this up in Phase 2, "
            "after the apply.",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

"""[S3] A version bump must copy the whole row, not the columns someone remembered.

`update_form_template`'s version-bump path INSERTs a new row and returns it. Its column list
used to be spelled out by hand, and nobody updated it as columns were added to the table, so
it silently dropped `sections`, `source_language`, `verification_status` and `source_url`.

Concretely: an admin opening RP-NO-DATASHEET, changing the version and saving destroyed the
sheet's five-section layout AND its Norwegian labels — no error, no warning, and the PDF
renderer would quietly fall back to grouping by `fields[].section`.

The in-place UPDATE escaped only by luck: it names the columns it SETs, so unlisted ones were
left alone rather than reset.

The structural tests below are the point. Asserting "these four columns survive" fixes today
and lets the fifth added column break again; asserting "both statements derive from one tuple"
is what actually closes it.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import admin_form_templates as aft  # noqa: E402

_SOURCE = os.path.join(_REPO_ROOT, "backend", "app", "routers", "admin_form_templates.py")


class TestOneCanonicalColumnSet(unittest.TestCase):
    """Structural: the SELECT and the version-bump INSERT must share a definition."""

    def test_the_bump_covers_every_column_the_select_reads(self) -> None:
        selected = {
            c.strip().split(" AS ")[0].strip()
            for c in aft._select_cols().split(",")
        }
        # id/created_at/updated_at are generated or immutable, never copied by a bump.
        selected -= {"id", "id::text", "created_at", "updated_at"}
        missing = selected - set(aft._BUMP_COLUMNS)
        self.assertEqual(
            missing, set(),
            f"the version bump would drop {sorted(missing)} — add them to _BUMP_COLUMNS",
        )

    def test_the_carried_columns_are_the_ones_prod_actually_has(self) -> None:
        """Pins the four that were being lost, so a refactor cannot quietly narrow the set."""
        for col in ("sections", "source_language", "verification_status", "source_url"):
            self.assertIn(col, aft._BUMP_COLUMNS, col)

    def test_the_generated_insert_names_every_bump_column(self) -> None:
        """Asserts on the SQL the code ACTUALLY builds, not on the source text.

        The first version of this test grepped the bump block for the string
        '_BUMP_COLUMNS' — and passed against a deliberately regressed build where the loop
        still mentioned the tuple while the column list came from a stale one. A guard
        keyed on an incidental token instead of on meaning proves nothing; that is the same
        error that made `superseded_codes` blind to a batched rewrite in AIQ-1795c.
        """
        sql, params, columns = aft._bump_insert(
            {"code": "X", "name": "n", "country": "no", "version": "2.0.0"}, "new-id"
        )
        self.assertEqual(tuple(columns), tuple(aft._BUMP_COLUMNS))
        for col in aft._BUMP_COLUMNS:
            self.assertIn(col, sql, f"{col} is missing from the generated INSERT")
            self.assertIn(col, params, f"{col} has no bound parameter")
        # One placeholder per column, plus :id.
        self.assertEqual(len(params), len(aft._BUMP_COLUMNS) + 1)

    def test_the_generated_insert_uppercases_country(self) -> None:
        _, params, _ = aft._bump_insert({"country": "no"}, "new-id")
        self.assertEqual(params["country"], "NO")

    def test_the_generated_insert_json_encodes_jsonb_columns_exactly_once(self) -> None:
        """A double-encoded value stores a quoted string where a jsonb array belongs, and
        the renderer then sees no sections at all."""
        sections = [{"id": "d_number", "field_ids": ["full_name"]}]
        _, params, _ = aft._bump_insert({"sections": sections}, "new-id")
        self.assertEqual(json.loads(params["sections"]), sections)

    def test_every_jsonb_column_is_json_decoded_on_read(self) -> None:
        """SQLite returns jsonb as TEXT. A column missing from the decode list round-trips
        as a STRING and the bump json-encodes it a second time, storing a quoted blob."""
        row = {
            "fields": '[{"id": "a"}]',
            "trigger_rules": '[{"conditions": {}}]',
            "sections": '[{"id": "s1", "field_ids": ["a"]}]',
        }
        out = aft._row_to_dict(row)
        for col in aft._ALL_JSONB:
            self.assertIsInstance(
                out[col], (list, dict),
                f"{col} came back as {type(out[col]).__name__}; add it to _ALL_JSONB",
            )

    def test_a_null_jsonb_column_defaults_to_empty_not_none(self) -> None:
        out = aft._row_to_dict({"fields": None, "trigger_rules": None, "sections": None})
        self.assertEqual(out["sections"], [])
        self.assertEqual(out["fields"], [])
        self.assertEqual(out["trigger_rules"], {})

    def test_carried_columns_are_not_api_editable(self) -> None:
        """Carrying a value forward does not require making it writable. Whether an admin
        may retype a template's provenance is a separate decision."""
        editable = set(aft.FormTemplateUpdate.model_fields)
        for col in aft._CARRIED_COLUMNS + aft._CARRIED_JSONB:
            self.assertNotIn(
                col, editable,
                f"{col} became API-editable; that is a deliberate decision, not a side effect",
            )


class TestTheInPlaceUpdateStillLeavesCarriedColumnsAlone(unittest.TestCase):
    def test_the_update_does_not_set_carried_columns(self) -> None:
        """It must not start writing them either — an UPDATE that SET them from `merged`
        would reset them whenever a caller omitted them from the PATCH body."""
        src = open(_SOURCE, encoding="utf-8").read()
        upd = src.split("# In-place update path", 1)[1].split("WHERE id = :id", 1)[0]
        for col in aft._CARRIED_COLUMNS + aft._CARRIED_JSONB:
            self.assertNotIn(
                f"{col} ", upd.replace("=", " = "),
                f"the in-place UPDATE now writes {col}",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

"""Unit tests for the pure decision logic of scripts/enrich_suppliers.py.

The applier writes to prod suppliers, so the fill-empty / never-overwrite / honesty / confidence
rules are pinned here. No DB is touched — decide_row is a pure function over (row, current).
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import enrich_suppliers as e  # noqa: E402

MED = e._CONF_RANK["med"]


def _outcomes(dec):
    return {fd.column: fd.outcome for fd in dec.fields}


class DecideRowTests(unittest.TestCase):
    def test_fill_empty_columns(self):
        row = {
            "key": "k", "status": "found",
            "contact_email": "a@b.de", "contact_email_source_url": "https://x", "contact_email_confidence": "high",
            "description": "A school.", "description_source_url": "https://x", "description_confidence": "high",
            "specialization_tags": ["IB", "primary"], "specialization_tags_confidence": "high",
            "city": "Berlin", "city_confidence": "high",
        }
        dec = e.decide_row(row, current={}, conf_floor=MED)
        o = _outcomes(dec)
        self.assertEqual(o["contact_email"], "fill")
        self.assertEqual(o["description"], "fill")
        self.assertEqual(o["specialization_tags"], "fill")
        self.assertEqual(o["city_name"], "fill")

    def test_never_overwrite_nonempty(self):
        row = {"key": "k", "status": "found",
               "contact_email": "new@b.de", "contact_email_source_url": "https://x", "contact_email_confidence": "high"}
        cur = {("suppliers", "contact_email"): "curated@b.de"}
        dec = e.decide_row(row, cur, conf_floor=MED)
        self.assertEqual(_outcomes(dec)["contact_email"], "skip:already")

    def test_json_array_empty_variants_are_fillable(self):
        for empty in (None, "", "[]", "null"):
            row = {"key": "k", "status": "found",
                   "specialization_tags": ["IB"], "specialization_tags_confidence": "high"}
            cur = {("supplier_service_capabilities", "specialization_tags"): empty}
            dec = e.decide_row(row, cur, conf_floor=MED)
            self.assertEqual(_outcomes(dec)["specialization_tags"], "fill", f"empty={empty!r}")

    def test_low_confidence_dropped(self):
        row = {"key": "k", "status": "found",
               "contact_phone": "+49 1", "contact_phone_source_url": "https://x", "contact_phone_confidence": "low"}
        dec = e.decide_row(row, {}, conf_floor=MED)
        self.assertEqual(_outcomes(dec)["contact_phone"], "skip:lowconf")

    def test_contact_requires_source_url(self):
        row = {"key": "k", "status": "found", "contact_email": "a@b.de", "contact_email_confidence": "high"}
        dec = e.decide_row(row, {}, conf_floor=MED)
        self.assertEqual(_outcomes(dec)["contact_email"], "skip:nosource")

    def test_descriptive_field_allowed_without_source(self):
        # city / tags / languages are low-risk — allowed with confidence only, no source_url required
        row = {"key": "k", "status": "found", "city": "Berlin", "city_confidence": "high"}
        dec = e.decide_row(row, {}, conf_floor=MED)
        self.assertEqual(_outcomes(dec)["city_name"], "fill")

    def test_honesty_email_skip(self):
        for local in ("presse", "security", "fraud", "dpo", "privacy"):
            row = {"key": "k", "status": "found",
                   "contact_email": f"{local}@b.de", "contact_email_source_url": "https://x", "contact_email_confidence": "high"}
            dec = e.decide_row(row, {}, conf_floor=MED)
            self.assertEqual(_outcomes(dec)["contact_email"], "skip:honesty", local)

    def test_not_found_row_dropped(self):
        row = {"key": "k", "status": "not_found", "contact_email": "a@b.de"}
        dec = e.decide_row(row, {}, conf_floor=MED)
        self.assertEqual(dec.row_skipped, "status=not_found")
        self.assertEqual(dec.fields, [])

    def test_partial_status_allowed(self):
        row = {"key": "k", "status": "partial", "city": "Oslo", "city_confidence": "high"}
        dec = e.decide_row(row, {}, conf_floor=MED)
        self.assertIsNone(dec.row_skipped)

    def test_json_array_serialised_as_text(self):
        row = {"key": "k", "status": "found", "specialization_tags": ["IB", "primary"], "specialization_tags_confidence": "high"}
        dec = e.decide_row(row, {}, conf_floor=MED)
        val = next(f.value for f in dec.fields if f.column == "specialization_tags")
        self.assertEqual(json.loads(val), ["IB", "primary"])

    def test_numeric_budget_coerced(self):
        row = {"key": "k", "status": "found", "min_budget": "1500", "min_budget_confidence": "high"}
        dec = e.decide_row(row, {}, conf_floor=MED)
        val = next(f.value for f in dec.fields if f.column == "min_budget")
        self.assertEqual(val, 1500.0)


if __name__ == "__main__":
    unittest.main()

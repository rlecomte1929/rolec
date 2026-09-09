"""
Phase 3 — the checked-in export data (Otto's Multi-Country Datasheet Export deliverables).

Validates the data files under data/ that drive the export, and that resolve_export_channel reads
them. This is a data-integrity gate (like the golden test parsing the shipped migration): if the
files drift or a corridor-content file is malformed, this fails.

Provenance: docs/imports/datasheet-export-otto-2026-09-09.md.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.datasheet_export import resolve_export_channel, CHANNEL_DATA_SHEET  # noqa: E402

_DATA = os.path.join(_REPO_ROOT, "data")

# Otto's manifest counts (docs/imports/datasheet-export-otto-2026-09-09.md).
EXPECTED_RECORDS = {"NO": 10, "DE": 8, "FR": 8}
REQUIRED_FIELDS = {"country_iso", "section", "step", "fact_key", "responsible_party"}


class DataSheetExportData(unittest.TestCase):

    def test_export_channels_json_is_valid_and_maps_countries(self):
        doc = json.load(open(os.path.join(_DATA, "export-channels.json")))
        channels = {c["country_iso"]: c["export_channel"] for c in doc["channels"]}
        self.assertEqual(set(channels), {"NO", "DE", "FR"})
        for iso, ch in channels.items():
            self.assertEqual(ch, CHANNEL_DATA_SHEET, f"{iso} channel drifted")

    def test_resolve_export_channel_reads_the_file(self):
        self.assertEqual(resolve_export_channel("NO"), CHANNEL_DATA_SHEET)
        self.assertEqual(resolve_export_channel("DE"), CHANNEL_DATA_SHEET)
        # Unknown country falls back to the safe default, never raises.
        self.assertEqual(resolve_export_channel("ZZ"), CHANNEL_DATA_SHEET)
        self.assertEqual(resolve_export_channel(None), CHANNEL_DATA_SHEET)

    def test_export_schema_json_is_valid(self):
        doc = json.load(open(os.path.join(_DATA, "export-schema.json")))
        self.assertIn("csv_columns", doc)
        self.assertIn("pdf_sheet_layout", doc)
        self.assertGreaterEqual(len(doc["csv_columns"]), 1)

    def test_corridor_content_ndjson_valid_with_expected_counts(self):
        for iso, expected in EXPECTED_RECORDS.items():
            path = os.path.join(_DATA, "corridor-content", f"{iso}.ndjson")
            self.assertTrue(os.path.isfile(path), f"missing {path}")
            records = []
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))  # raises if malformed
            self.assertEqual(len(records), expected, f"{iso}.ndjson record count drifted")
            for r in records:
                self.assertTrue(REQUIRED_FIELDS.issubset(r), f"{iso} record missing fields: {r}")
                self.assertEqual(r["country_iso"], iso)


if __name__ == "__main__":
    unittest.main()

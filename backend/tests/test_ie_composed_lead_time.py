"""AIQ-2192 composed Ireland permit-then-visa lead-time batch.

DB-free. Properties: THIRD_COUNTRY only, both source citations, pending, no invented
statutory 20-week figure, converter maps nationality through NATIONALITY_CLASSES.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.app.services.nationality_class import THIRD_COUNTRY
from backend.imports.otto.mappings import NATIONALITY_CLASSES, RequirementDraft, resolve
from backend.imports.otto.parsers import read_jsonl

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "convert_ie_composed_lead_time_to_otto_jsonl.py"
_GATE = _REPO_ROOT / "scripts" / "check_ie_composed_lead_time_batch.py"
_spec = importlib.util.spec_from_file_location("convert_ie_composed_lead_time", _SCRIPT)
assert _spec and _spec.loader
convert = importlib.util.module_from_spec(_spec)
sys.modules["convert_ie_composed_lead_time"] = convert
_spec.loader.exec_module(convert)

DETE = convert.DETE_URL
ISD = convert.ISD_URL


class TestComposedLeadTimeBatch(unittest.TestCase):
    def test_exactly_one_pending_third_country_row(self) -> None:
        src = convert.source_records()
        self.assertEqual(len(src), 1)
        rec = src[0]
        self.assertEqual(rec["review_status"], "pending")
        self.assertEqual(rec["applies_to_nationality_classes"], ["THIRD_COUNTRY"])

    def test_converter_nationality_maps_to_third_country_only(self) -> None:
        out = convert.build()[0]
        self.assertEqual(out["applies_to"]["nationality"], "non-EEA")
        self.assertEqual(NATIONALITY_CLASSES["non-EEA"], [THIRD_COUNTRY])

    def test_both_source_citations_survive_promotion_shape(self) -> None:
        out = convert.build()[0]
        self.assertEqual(out["source_url"], DETE)
        extras = out["applies_to"]["additional_citations"]
        self.assertEqual(extras[0]["url"], ISD)
        entity = SimpleNamespace(
            destination_country="IE",
            topic_key=out["entity_topic_key"],
            title=out["entity_title"],
            domain_area="immigration",
        )
        fact = SimpleNamespace(
            id="1",
            fact_type=out["fact_type"],
            fact_key=out["fact_key"],
            fact_text=out["fact_text"],
            applies_to=out["applies_to"],
            source_url=out["source_url"],
            evidence_quote=out["evidence_quote"],
            accuracy_tier="needs_review",
        )
        draft = resolve(entity, [fact])
        self.assertIsInstance(draft, RequirementDraft)
        citations = json.loads(draft.payload["citations_json"])
        urls = {c["url"] for c in citations}
        self.assertEqual(urls, {DETE, ISD})
        self.assertEqual(
            json.loads(draft.payload["applies_to_nationality_classes_json"]),
            [THIRD_COUNTRY],
        )

    def test_honesty_about_composed_20_weeks_and_isd_quote(self) -> None:
        text = convert.build()[0]["fact_text"]
        self.assertIn("sequential", text)
        self.assertIn("20 weeks", text)
        self.assertIn("does not invent a new statutory 20-week figure", text)
        self.assertIn("not stated in that row's ISD evidence quote", text)

    def test_read_jsonl_accepts_the_converted_row(self) -> None:
        converted = convert.build()
        tmp = Path(tempfile.mkdtemp()) / "batch.jsonl"
        tmp.write_text(json.dumps(converted[0], ensure_ascii=False) + "\n", encoding="utf-8")
        rows, rejections = read_jsonl(tmp, batch_id=convert.BATCH_ID)
        self.assertEqual(rejections, [])
        self.assertEqual(len(rows), 1)

    def test_gate_script_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(_GATE)],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

"""The VE→IE conversion, and the properties it must not lose.

Two of these guard mistakes that are easy to make and expensive to make:

**Nationality must come from the artifact, not the corridor.** The corridor is ES→IE, so
deriving the class from it — which is what the B3 converter correctly does for *its* batch —
answers EEA, because a Spanish national is a free mover into Ireland. The subject here is a
**Venezuelan** national resident in Spain, and the entire deliverable exists because her
Spanish residence does not carry into Ireland. A row staged as EEA would serve the free-mover
track to a visa-required national.

**Both halves of the divergence must survive.** The channel carries one `fact_text`; six of
the nine rows carry a statement plus a three-part note whose value is the gap between the
official page and reality. A composition that drops or merges a half destroys the only thing
the batch records that a government website does not.

DB-free. Everything here is a property of the conversion.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from backend.imports.otto.parsers import UNOFFICIAL, read_jsonl

_REPO_ROOT = Path(__file__).resolve().parents[2]
# `scripts/` is not a package, so import the converter by path — the idiom the rest of
# backend/tests already uses for script modules (see test_b3_corridor_facts_conversion.py).
_SCRIPT = _REPO_ROOT / "scripts" / "convert_ve_ie_to_otto_jsonl.py"
_spec = importlib.util.spec_from_file_location("convert_ve_ie_to_otto_jsonl", _SCRIPT)
assert _spec and _spec.loader
convert = importlib.util.module_from_spec(_spec)
sys.modules["convert_ve_ie_to_otto_jsonl"] = convert
_spec.loader.exec_module(convert)

build = convert.build
source_records = convert.source_records
BATCH_ID = convert.BATCH_ID


class TestConversion(unittest.TestCase):
    def test_every_source_record_produces_exactly_one_output(self) -> None:
        self.assertEqual(len(build()), len(source_records()))

    def test_count_reconciles_against_the_manifest(self) -> None:
        manifest = json.loads(convert.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(len(build()), int(manifest["record_count"]))

    def test_dedupe_keys_are_unique(self) -> None:
        """A collision is reported as a rejection, so it loses a fact without erroring."""
        keys = [
            (r["destination_country"], r["entity_topic_key"], r["fact_key"]) for r in build()
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_the_origin_is_in_the_fact_key(self) -> None:
        """So a later batch from another origin cannot land on an existing key."""
        for src, out in zip(source_records(), build()):
            self.assertIn(str(src["origin_country_code"]).lower(), out["fact_key"])

    def test_nationality_is_read_from_the_artifact_not_the_corridor(self) -> None:
        """The regression guard. ES→IE derives EEA; the subject is Venezuelan — non-EEA."""
        for src, out in zip(source_records(), build()):
            self.assertEqual(src["applies_to_nationality_classes"], ["THIRD_COUNTRY"])
            self.assertEqual(out["applies_to"]["nationality"], "non-EEA")

    def test_a_fact_with_no_nationality_class_is_refused_not_guessed(self) -> None:
        with self.assertRaises(ValueError):
            convert.nationality_for({"fact_uid": "x", "applies_to_nationality_classes": []})

    def test_both_halves_of_the_divergence_survive(self) -> None:
        for src, out in zip(source_records(), build()):
            note = src.get("non_obvious_note") or {}
            if not note:
                continue
            self.assertIn(note["official_guidance"].strip(), out["fact_text"])
            self.assertIn(note["actual_reality"].strip(), out["fact_text"])
            self.assertIn(note["action_required"].strip(), out["fact_text"])
            self.assertIn("Commonly believed:", out["fact_text"])
            self.assertIn("Actually:", out["fact_text"])

    def test_the_statement_itself_survives(self) -> None:
        """The note is additive — it must not replace the fact the artifact states."""
        for src, out in zip(source_records(), build()):
            self.assertIn(src["fact_text"].strip(), out["fact_text"])

    def test_no_evidence_quote_is_invented_or_dropped(self) -> None:
        for src, out in zip(source_records(), build()):
            self.assertEqual(out["evidence_quote"], src["evidence_quote"].strip())

    def test_the_counsel_flag_survives_for_every_flagged_row(self) -> None:
        """These four cannot be approved without counsel; losing the flag loses the gate."""
        manifest = json.loads(convert.MANIFEST.read_text(encoding="utf-8"))
        flagged = [r for r in build() if r["applies_to"]["needs_lawyer_review"]]
        self.assertEqual(len(flagged), int(manifest["needs_lawyer_review_count"]))
        for src, out in zip(source_records(), build()):
            self.assertEqual(
                out["applies_to"]["needs_lawyer_review"], bool(src["needs_lawyer_review"])
            )

    def test_the_unconfirmed_quote_flag_survives(self) -> None:
        """Every quote in this batch is captured but unverified; the reviewer must see that."""
        for out in build():
            self.assertFalse(out["applies_to"]["quote_verbatim_confirmed"])

    def test_the_fact_uid_is_carried_as_the_audit_anchor(self) -> None:
        for src, out in zip(source_records(), build()):
            self.assertEqual(out["applies_to"]["fact_uid"], src["fact_uid"])


class TestReaderAccepts(unittest.TestCase):
    """The gate the deliverable failed as delivered: the otto reader must parse every row."""

    def _write(self) -> Path:
        import tempfile

        tmp = Path(tempfile.mkdtemp()) / f"{BATCH_ID}.jsonl"
        tmp.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in build()) + "\n",
            encoding="utf-8",
        )
        return tmp

    def test_the_reader_parses_every_row_with_no_rejections(self) -> None:
        rows, rejections = read_jsonl(self._write(), batch_id=BATCH_ID)
        self.assertEqual(rejections, [])
        self.assertEqual(len(rows), len(source_records()))

    def test_no_row_is_scored_unofficial(self) -> None:
        rows, _ = read_jsonl(self._write(), batch_id=BATCH_ID)
        for row in rows:
            self.assertNotEqual(row.source_class, UNOFFICIAL)

    def test_nationality_survives_into_the_parsed_row(self) -> None:
        """`applies_to` must reach the row as a dict — `resolve()` refuses a NULL nationality."""
        rows, _ = read_jsonl(self._write(), batch_id=BATCH_ID)
        for row in rows:
            self.assertIsInstance(row.applies_to, dict)
            self.assertEqual(row.applies_to["nationality"], "non-EEA")


if __name__ == "__main__":
    unittest.main()

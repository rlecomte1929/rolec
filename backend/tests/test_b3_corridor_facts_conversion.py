"""The B3 corridor-facts conversion, and the two properties it must not lose.

B3's value is the *divergence* between official guidance and operational reality. Otto's fact
channel carries one `fact_text`, so the conversion composes the pair — and a composition that
drops or merges a half silently destroys the only thing the batch records that a government
website does not.

The second property is collision safety. `dedupe_key` is `destination|topic|fact_key`, and the
batch carries several ORIGINS into the same destination and category: DK->DE and DE->DK both
touch `tax_payroll`. Two rows landing on one key would collide on the table's UNIQUE index,
and the reader reports that as a rejection rather than an error — so a collision costs a fact
quietly.

DB-free. Everything here is a property of the conversion.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from backend.imports.otto.parsers import read_jsonl

# `scripts/` is not a package, so import the converter by path — the idiom the rest of
# backend/tests already uses for script modules (see test_synth_passport.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "convert_b3_to_otto_jsonl.py"
_spec = importlib.util.spec_from_file_location("convert_b3_to_otto_jsonl", _SCRIPT)
assert _spec and _spec.loader
convert = importlib.util.module_from_spec(_spec)
sys.modules["convert_b3_to_otto_jsonl"] = convert
_spec.loader.exec_module(convert)

_CLI = _REPO_ROOT / "scripts" / "import_otto_facts.py"
_cli_spec = importlib.util.spec_from_file_location("import_otto_facts", _CLI)
assert _cli_spec and _cli_spec.loader
cli = importlib.util.module_from_spec(_cli_spec)
sys.modules["import_otto_facts"] = cli
_cli_spec.loader.exec_module(cli)

REPO = _REPO_ROOT
BATCH_ID = convert.BATCH_ID
OUT = convert.OUT
SOURCE = convert.SOURCE
build = convert.build
split_corridor = convert.split_corridor


def source_records() -> list[dict]:
    return [json.loads(l) for l in SOURCE.read_text().splitlines() if l.strip()]


class TestConversion(unittest.TestCase):
    def test_every_source_record_produces_exactly_one_output(self) -> None:
        self.assertEqual(len(build()), len(source_records()))

    def test_dedupe_keys_are_unique(self) -> None:
        """A collision is reported as a rejection, so it loses a fact without erroring."""
        keys = [
            (r["destination_country"], r["entity_topic_key"], r["fact_key"]) for r in build()
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_the_origin_is_in_the_fact_key(self) -> None:
        """Without it, DK->DE and a later FR->DE collide on `DE|tax_payroll|…`."""
        for src, out in zip(source_records(), build()):
            origin, _ = split_corridor(src["corridor"])
            self.assertIn(origin.lower(), out["fact_key"])

    def test_both_halves_of_the_divergence_survive(self) -> None:
        """The composition must keep the misconception identifiable, not merge it in."""
        for src, out in zip(source_records(), build()):
            self.assertIn(src["official_guidance"].strip(), out["fact_text"])
            self.assertIn(src["actual_reality"].strip(), out["fact_text"])
            self.assertIn(src["action_required"].strip(), out["fact_text"])
            self.assertIn("Commonly believed:", out["fact_text"])
            self.assertIn("Actually:", out["fact_text"])

    def test_the_destination_is_the_right_side_of_the_corridor(self) -> None:
        self.assertEqual(split_corridor("NO->GB"), ("NO", "GB"))
        for src, out in zip(source_records(), build()):
            self.assertEqual(out["destination_country"], src["corridor"].split("->")[1].strip())

    def test_the_wildcard_employee_type_is_resolved_not_dropped(self) -> None:
        """This test used to assert the opposite, and the assertion was the mistake.

        It read mappings.py's "NULL means applies to everyone" as licence to omit the key,
        and passed — which is exactly why the error survived review. `resolve()` refuses a
        NULL nationality, so every fact staged that way was unpromotable. The source's
        "all" is a wildcard that must be RESOLVED against the corridor, not carried through.
        """
        for src, out in zip(source_records(), build()):
            self.assertEqual(src["employee_type"], "all")
            self.assertIn("nationality", out["applies_to"])
            self.assertIn(out["applies_to"]["nationality"], ("EEA", "non-EEA"))

    def test_no_evidence_quote_is_invented(self) -> None:
        """B3 carries no verbatim quotes. A fabricated one would let a row auto-accept."""
        for out in build():
            self.assertIsNone(out["evidence_quote"])

    def test_no_source_is_invented(self) -> None:
        for src, out in zip(source_records(), build()):
            self.assertEqual(out["source_url"], src["source_url"].strip())

    def test_the_committed_jsonl_matches_the_generator(self) -> None:
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "convert_b3_to_otto_jsonl.py"), "--check"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestNationalityIsDerivedFromTheCorridor(unittest.TestCase):
    """B3's `employee_type` is the literal "all", so the class has to come from the corridor.

    An earlier version omitted `applies_to.nationality` entirely, reading mappings.py's note
    that NULL means "applies to everyone" as permission. The same module REFUSES a NULL
    nationality at promote time, precisely because "applies to everyone" would serve a
    visa-track requirement to a free mover — so all 20 facts came back Unmapped.
    """

    def test_every_fact_carries_a_nationality_class(self) -> None:
        for r in build():
            self.assertIn(r["applies_to"]["nationality"], ("EEA", "non-EEA"), r["fact_key"])

    def test_brexit_is_not_hand_rolled(self) -> None:
        """NO→GB and GB→NO are third-country BOTH ways; the four Nordic pairs are not.

        The values come from `nationality_class.classify`, which owns the EU-27/EEA sets and
        the rule that free movement is worth nothing unless the DESTINATION is inside the
        area. A second EEA set written here is how NO→GB would quietly stay free-movement.
        """
        by_corridor = {
            r["applies_to"]["corridor"]: r["applies_to"]["nationality"] for r in build()
        }
        self.assertEqual(by_corridor["NO->GB"], "non-EEA")
        self.assertEqual(by_corridor["GB->NO"], "non-EEA")
        for free in ("DK->NO", "NO->DK", "DK->DE", "DE->DK"):
            self.assertEqual(by_corridor[free], "EEA", free)

    def test_the_batch_spans_several_destinations(self) -> None:
        """The precondition that exposed the promote-scoping bug — see `destinations_for`."""
        self.assertEqual(
            sorted({r["destination_country"] for r in build()}), ["DE", "DK", "GB", "NO"]
        )


class TestPromotionCoversEveryDestination(unittest.TestCase):
    """`import_otto_facts` scoped promotion to `rows[0].destination_country`.

    Every batch before B3 was single-destination, so one country was the whole batch and the
    bug could not show itself. B3 spans four. Its first record is NO→GB, so promotion ran for
    GB alone, wrote 4 rows, never looked at the other 16 facts, and printed "promote: 4" as
    though that were the batch.
    """

    def _rows(self, *dests):
        from types import SimpleNamespace
        return [SimpleNamespace(destination_country=d) for d in dests]

    def test_every_destination_is_returned(self) -> None:
        self.assertEqual(
            cli.destinations_for(self._rows("NO", "GB", "DK", "DE", "GB")),
            ["DE", "DK", "GB", "NO"],
        )

    def test_a_single_destination_batch_is_unchanged(self) -> None:
        self.assertEqual(cli.destinations_for(self._rows("FR", "FR")), ["FR"])

    def test_it_does_not_return_only_the_first(self) -> None:
        """The regression. `[rows[0].destination_country]` would pass every other test here."""
        got = cli.destinations_for(self._rows("NO", "GB", "DK", "DE"))
        self.assertNotEqual(got, ["NO"])
        self.assertEqual(len(got), 4)


class TestReaderAcceptsTheWholeBatch(unittest.TestCase):
    """End to end through the real reader — the gate must admit the ROWS, not just parse them.

    Before the DK/DE hosts were added to the source allowlist this failed with 9 rejections,
    and they clustered by country: NO->DK, DK->DE and DE->DK each lost every fact.
    """

    def test_all_twenty_are_accepted_and_none_auto_accepted(self) -> None:
        rows, rejections = read_jsonl(OUT, batch_id=BATCH_ID)
        self.assertEqual(rejections, [], "a rejected fact is a lost fact")
        self.assertEqual(len(rows), 20)
        for row in rows:
            self.assertEqual(
                row.accuracy_tier, "needs_review",
                "unreviewed research must never land auto_accepted",
            )


if __name__ == "__main__":
    unittest.main()

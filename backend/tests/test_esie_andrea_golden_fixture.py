"""The ES→IE golden fixture, executed.

`docs/esie-andrea-golden-fixture.md` is the frozen statement of what the serving layer must do
on this corridor. This module loads it and asserts it against the real batch artifact, so the
document cannot drift away from the code that is supposed to honour it.

Two personas, two opposite failure modes (see the fixture for why):
  * Andrea (Venezuela, third country) must be served all 38 records.
  * The EEA control (Spain) must be served the 17 `audience_scope` records and NONE of the 21
    `nationality_determined` ones — even though every record is labelled `nationality: non-EEA`.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from backend.app.services.applies_to_matcher import apply_applies_to

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "docs" / "esie-andrea-golden-fixture.md"


def _load_fixture() -> dict:
    match = re.search(r"```json\n(.*?)\n```", FIXTURE.read_text(), re.S)
    assert match, f"no json block in {FIXTURE}"
    return json.loads(match.group(1))


def _load_batch(fixture: dict) -> list[dict]:
    path = REPO_ROOT / fixture["source_artifact"]
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _snapshot(persona: dict) -> dict:
    """The subset of `build_profile_snapshot`'s output that the matcher actually reads."""
    return {
        "nationality": persona["nationality"],
        "origin_country": persona["origin_country"],
        "destination_country": persona["destination_country"],
    }


def _served(batch: list[dict], persona: dict) -> set[str]:
    snap = _snapshot(persona)
    return {r["fact_key"] for r in batch if apply_applies_to(r.get("applies_to") or {}, snap)}


class GoldenFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _load_fixture()
        cls.batch = _load_batch(cls.fixture)

    def test_batch_matches_the_fixture_it_was_frozen_against(self) -> None:
        """If the artifact is re-issued, the fixture must be re-frozen deliberately."""
        self.assertEqual(len(self.batch), 38)
        keys = {r["fact_key"] for r in self.batch}
        andrea = self.fixture["personas"]["andrea"]
        self.assertEqual(keys, set(andrea["expected_served_rules"]))

    def test_andrea_third_country_is_served_every_rule(self) -> None:
        andrea = self.fixture["personas"]["andrea"]
        served = _served(self.batch, andrea)
        self.assertEqual(served, set(andrea["expected_served_rules"]))
        self.assertEqual(len(served), andrea["expected_served_count"])

    def test_eea_control_still_sees_the_audience_scope_rules(self) -> None:
        """The mis-serve this fixture exists to prevent: PPSN and emergency tax are not
        nationality-gated, and hiding them costs a Spanish mover 40% of her first pay."""
        eea = self.fixture["personas"]["eea_control"]
        served = _served(self.batch, eea)
        missing = set(eea["expected_served_rules"]) - served
        self.assertEqual(missing, set(), f"audience_scope rules hidden from an EEA mover: {sorted(missing)}")

    def test_eea_control_is_not_served_third_country_rules(self) -> None:
        eea = self.fixture["personas"]["eea_control"]
        served = _served(self.batch, eea)
        leaked = served & set(eea["must_not_be_served"])
        self.assertEqual(leaked, set(), f"nationality_determined rules leaked to an EEA mover: {sorted(leaked)}")

    def test_eea_control_is_served_exactly_the_audience_scope_set(self) -> None:
        eea = self.fixture["personas"]["eea_control"]
        self.assertEqual(_served(self.batch, eea), set(eea["expected_served_rules"]))

    def test_no_conditional_rule_reaches_the_eea_control(self) -> None:
        """Both conditional records assert a visa SEQUENCE, not a determination. Neither may be
        used to tell an EEA mover that she is — or is not — visa-required."""
        eea = self.fixture["personas"]["eea_control"]
        served = _served(self.batch, eea)
        self.assertEqual(served & set(self.fixture["conditional_rules"]), set())

    def test_conditional_records_carry_what_the_renderer_needs(self) -> None:
        by_key = {r["fact_key"]: r for r in self.batch}
        for key in self.fixture["conditional_rules"]:
            applies_to = by_key[key]["applies_to"]
            self.assertEqual(applies_to.get("assertion_mode"), "conditional", key)
            self.assertTrue(str(applies_to.get("conditional_on") or "").strip(),
                            f"{key} is conditional but names no condition")

    def test_non_obvious_traps_are_flagged_on_the_batch(self) -> None:
        by_key = {r["fact_key"]: r for r in self.batch}
        for key in self.fixture["non_obvious_rules"]:
            self.assertTrue(by_key[key]["applies_to"].get("non_obvious"), key)


if __name__ == "__main__":
    unittest.main()

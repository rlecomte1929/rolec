"""[AIQ-1953] A circular prerequisite chain must fail the BUILD, not the serve.

`scheduler._topological_order` already ran Kahn's algorithm and raised on a cycle — but it
runs while SCHEDULING a timeline, which is to say while serving a real person's case. A
corridor authored with `A -> B -> A` loaded cleanly, passed review, and blew up later at
the moment someone needed their plan.

The card's constraint states it directly: *"Cycle detection must fail the build, not serve."*

These tests pin both halves: the cycle is refused at load, and a legitimate diamond
dependency still loads.
"""
from __future__ import annotations

import unittest

from backend.relopass.corridors.loader import (
    CorridorLoadError,
    load_corridor,
    load_corridor_text,
)

BASE = """
corridor_agent:
  corridor_id: TEST_XX
  version: v1
  petitioning_party: EMPLOYEE
  origin_country_iso3: ESP
  destination_country_iso3: IRL
  applicable_rules:
    - rule_id: R1
      legal_reference: "Test Act 2026 s.1"
  required_documents: []
  required_data_points: []
  eligibility_branches: []
  no_branch_verdict: NOT_ELIGIBLE
  exception_cases: []
  step_graph:
{steps}
"""


def corridor_with(steps_yaml: str) -> str:
    return BASE.format(steps=steps_yaml)


LINEAR = """    - step_id: A
      name: "First"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: []
    - step_id: B
      name: "Second"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [A]
"""

TWO_STEP_CYCLE = """    - step_id: A
      name: "First"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [B]
    - step_id: B
      name: "Second"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [A]
"""

THREE_STEP_CYCLE = """    - step_id: A
      name: "First"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [C]
    - step_id: B
      name: "Second"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [A]
    - step_id: C
      name: "Third"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [B]
"""

SELF_CYCLE = """    - step_id: A
      name: "First"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [A]
"""

DIAMOND = """    - step_id: A
      name: "Root"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: []
    - step_id: B
      name: "Left"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [A]
    - step_id: C
      name: "Right"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [A]
    - step_id: D
      name: "Join"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids: [B, C]
"""


class TestCyclesAreRefusedAtLoad(unittest.TestCase):
    def test_a_two_step_cycle_fails_to_load(self) -> None:
        with self.assertRaises(CorridorLoadError) as ctx:
            load_corridor_text(corridor_with(TWO_STEP_CYCLE))
        self.assertIn("circular", str(ctx.exception).lower())

    def test_a_three_step_cycle_fails_to_load(self) -> None:
        with self.assertRaises(CorridorLoadError):
            load_corridor_text(corridor_with(THREE_STEP_CYCLE))

    def test_a_step_that_depends_on_itself_fails_to_load(self) -> None:
        with self.assertRaises(CorridorLoadError):
            load_corridor_text(corridor_with(SELF_CYCLE))

    def test_the_error_names_the_blocked_steps(self) -> None:
        """"There is a cycle somewhere in 23 steps" is not actionable for an author."""
        with self.assertRaises(CorridorLoadError) as ctx:
            load_corridor_text(corridor_with(THREE_STEP_CYCLE))
        msg = str(ctx.exception)
        for step_id in ("A", "B", "C"):
            self.assertIn(step_id, msg)


class TestLegitimateGraphsStillLoad(unittest.TestCase):
    """The guard must not reject graphs that are merely non-linear."""

    def test_a_linear_chain_loads(self) -> None:
        agent = load_corridor_text(corridor_with(LINEAR))
        self.assertEqual(agent.step_ids(), ("A", "B"))

    def test_a_diamond_loads(self) -> None:
        """Two independent branches rejoining is a DAG, not a cycle."""
        agent = load_corridor_text(corridor_with(DIAMOND))
        self.assertEqual(len(agent.step_graph), 4)


class TestRealCorridorsAreAcyclic(unittest.TestCase):
    """The shipped corridors must satisfy the new guard — otherwise this breaks prod."""

    def test_every_registered_pathway_loads(self) -> None:
        from pathlib import Path

        repo = Path(__file__).resolve().parents[2]
        pathways = sorted(repo.glob("corridors/*/pathways/*/*.yaml"))
        self.assertGreater(len(pathways), 0, "no corridor pathways found to check")
        for p in pathways:
            with self.subTest(pathway=str(p.relative_to(repo))):
                load_corridor(str(p))


if __name__ == "__main__":
    unittest.main()

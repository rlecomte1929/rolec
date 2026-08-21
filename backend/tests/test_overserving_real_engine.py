"""Both halves of the non-obvious metric, measured against the engine that actually ships.

Two things this file exists to prove, in order of importance.

**1. Recall cannot fail here, and that is not a compliment.** Driven through the real
`derive_roadmap`, every one of the six HLP slices scores 1.0. Recall counts requirements that
are *present*; every defect the 2026-08-21 ES→IE audit found was an over-serving defect, and
serving a requirement to someone who must not receive it costs exactly zero recall. A
framework with only that half reads green through the failures it exists to prevent.

**2. The precision half found a real defect on its first run.** `FR_NO` declares only an
`EEA_FREEDOM_2026` pathway, and `roadmap_corridor_overlay._resolve_pathway` serves
`pathways[0]` to every nationality with no class check. So a third-country national moving
France→Norway is shown the step *"Travel to Norway (no visa required for EEA nationals)"*
alongside the generic scaffold's *"Work / residence permit application"* — two contradictory
instructions in one plan.

That violation is left **failing on purpose**, so the number stays true. Fixing it needs a
product decision (serve no overlay to an uncovered class, or author a third-country FR_NO
pathway), and an amnesty file would have buried it.

`test_the_known_violation_set_is_exactly_what_we_expect` pins the set **by name**. A new
violation fails it; so does fixing this one without removing the entry. Same discipline as
`check_corridor_facts.py`'s allowlist, where an entry that no longer reproduces is itself a
failure — that is what makes the file drain instead of becoming a blindfold.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./ci_test.db")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.eval.nonobvious_harness import build_produced, load_profiles  # noqa: E402
from backend.eval.nonobvious_recall import load_baseline, score_slices  # noqa: E402
from backend.eval.overserving import score_overserving  # noqa: E402

#: The one over-serving violation known and accepted on 2026-08-21, by name.
KNOWN_VIOLATIONS = {"FR_NO:non_eea_national:no_visa_required_claim"}


def _run():
    profiles = load_profiles()
    steps, advisories = build_produced(profiles)
    baseline = load_baseline()
    return (
        baseline,
        steps,
        advisories,
        score_slices(baseline, steps),
        score_overserving(baseline, steps, advisories),
    )


class TheHarnessMeasuresTheRealEngine(unittest.TestCase):

    def test_every_slice_is_measured(self):
        # `score_slices` reports unscored as a COUNT; `score_overserving` reports unmeasured
        # as a LIST of slice ids (so the failure names them). Both must be empty.
        _, steps, _, recall, over = _run()
        self.assertEqual(0, recall["unscored_slices"])
        self.assertEqual([], over["unmeasured_slices"])
        self.assertEqual(6, recall["scored_slices"])

    def test_several_profiles_per_slice_so_the_every_roadmap_rule_is_live(self):
        """`score_slice` counts a requirement served only when EVERY roadmap has it.

        With one profile per slice that clause is dead code and the metric is a single
        point. This asserts the committed set actually exercises it.
        """
        _, steps, _, _, _ = _run()
        for sid, roadmaps in steps.items():
            self.assertGreaterEqual(len(roadmaps), 2, f"{sid} has only {len(roadmaps)} roadmap(s)")

    def test_the_harness_is_offline_and_clock_free(self):
        """Two runs in the same process must be identical, and neither may touch a clock.

        The committed profiles omit `dateOfBirth` precisely because
        `roadmap_builder._age_from_dob` calls `date.today()`.
        """
        profiles = load_profiles()
        a, _ = build_produced(profiles)
        b, _ = build_produced(profiles)
        self.assertEqual(
            {k: [[s.get("title") for s in rm] for rm in v] for k, v in a.items()},
            {k: [[s.get("title") for s in rm] for rm in v] for k, v in b.items()},
        )


class RecallIsGreenAndThatIsTheProblem(unittest.TestCase):

    def test_recall_is_1_0_on_every_slice_against_the_real_engine(self):
        """Documents the vacuity rather than hiding it. If this ever drops, read the diff."""
        _, _, _, recall, _ = _run()
        self.assertEqual(1.0, recall["worst_recall"])

    def test_removing_the_corridor_overlay_provably_drops_recall(self):
        """Poison the ENGINE, not a fixture — strictly stronger than mutating JSON.

        Removes exactly the AIQ-1867 feature and proves the eval would have caught its
        absence.
        """
        from unittest import mock

        profiles = load_profiles()
        baseline = load_baseline()
        with mock.patch(
            "backend.app.services.roadmap_builder.corridor_overlay", lambda case: None
        ):
            steps, _ = build_produced(profiles)
        recall = score_slices(baseline, steps)
        self.assertLess(recall["worst_recall"], 1.0)
        missing = {m for s in recall["slices"] for m in s["missing"]}
        self.assertIn("d_visa_before_travel", missing)


class PrecisionCatchesWhatRecallCannot(unittest.TestCase):

    def test_the_known_violation_set_is_exactly_what_we_expect(self):
        """Pinned by name, so it drains rather than becoming a blindfold.

        A NEW over-serving violation fails this. So does fixing the known one without
        removing its `must_not_serve` entry.
        """
        _, _, _, _, over = _run()
        actual = {
            f"{s['corridor']}:{s['employee_type']}:{v['key']}"
            for s in over["slices"]
            for v in s["violated"]
        }
        self.assertEqual(KNOWN_VIOLATIONS, actual)

    def test_the_es_ie_free_mover_is_clean(self):
        """The #1951 invariant, held at the slice level rather than only the unit level."""
        _, _, _, _, over = _run()
        s = next(
            x for x in over["slices"]
            if x["corridor"] == "ES_IE" and x["employee_type"] == "eu_national"
        )
        self.assertEqual(0, s["violations"], s["violated"])
        self.assertGreater(s["n_forbidden"], 0, "the slice must actually be constrained")

    def test_precision_would_have_caught_the_defect_recall_missed(self):
        """Re-introduce the #1951 bug and prove the two axes disagree.

        With the nationality gate removed, an ES_IE free mover is served the third-country
        track again. Recall stays 1.0 — it is blind to over-serving — while over-serving
        rises. That divergence is the entire argument for the second axis.
        """
        from unittest import mock

        import backend.app.services.roadmap_corridor_overlay as ov

        profiles = load_profiles()
        baseline = load_baseline()
        with mock.patch.object(ov, "_THIRD_COUNTRY_ONLY_ADVISORIES", frozenset()), \
             mock.patch.object(ov, "_IMMIGRATION_GATED", frozenset()):
            steps, advisories = build_produced(profiles)

        recall = score_slices(baseline, steps)
        over = score_overserving(baseline, steps, advisories)

        self.assertEqual(1.0, recall["worst_recall"],
                         "recall must stay blind — that is the point being demonstrated")
        self.assertGreater(over["violations"], len(KNOWN_VIOLATIONS))
        es_ie = next(
            x for x in over["slices"]
            if x["corridor"] == "ES_IE" and x["employee_type"] == "eu_national"
        )
        self.assertGreater(es_ie["violations"], 0)

    def test_an_unconstrained_slice_reports_itself_rather_than_counting_as_clean(self):
        _, _, _, _, over = _run()
        unconstrained = [s for s in over["slices"] if s["n_forbidden"] == 0]
        self.assertTrue(unconstrained, "expected some slices to carry no must_not_serve yet")
        for s in unconstrained:
            self.assertEqual(0, s["violations"])
            self.assertTrue(s["measured"])


if __name__ == "__main__":
    unittest.main()

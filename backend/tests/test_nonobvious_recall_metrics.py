"""
Sliced non-obvious recall vs the lawyer-verified HLP baseline.

Pins the properties that make this metric the replacement for the retired
aggregate 'corridor completeness %':

  1. recall is computed per (corridor x employee_type) slice \u2014 never averaged;
  2. a single missed non-obvious requirement in one slice lowers ONLY that
     slice, and makes it the worst slice;
  3. all three active corridors (FR\u2192NO, ES\u2192IE, NO\u2192FR) x their employee
     types are in the baseline;
  4. the worst slice is surfaced first, identified by corridor and
     employee type.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.nonobvious_recall import (
    DEFAULT_BASELINE_PATH,
    load_baseline,
    score_slice,
    score_slices,
    slice_id,
)

_SAMPLE = Path(__file__).parent / "fixtures" / "eval" / "nonobvious" / "produced_slices_sample.json"

ACTIVE_SLICES = {
    ("FR_NO", "eu_national"),
    ("FR_NO", "non_eu_eea_national"),
    ("FR_NO", "non_eea_national"),
    ("ES_IE", "eu_national"),
    ("ES_IE", "non_eu_passport_holder"),
    ("NO_FR", "norwegian_national"),
}


def _load_sample():
    data = json.loads(_SAMPLE.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def test_baseline_covers_all_active_corridor_employee_type_slices():
    baseline = load_baseline()
    assert DEFAULT_BASELINE_PATH.exists()
    slices = {(s["corridor"], s["employee_type"]) for s in baseline["slices"]}
    assert slices == ACTIVE_SLICES
    for s in baseline["slices"]:
        assert s["requirements"], "every slice needs a lawyer-verifiable HLP requirement set"
        # The denominator is the lawyer-verified ground-truth count.
        assert all(r.get("key") and r.get("match") for r in s["requirements"])
        # Verification state is explicit, never implied.
        assert s["verification"]["status"] in {"lawyer_verified", "pending_lawyer_signoff"}


def test_perfect_sample_scores_recall_one_on_every_slice():
    baseline = load_baseline()
    result = score_slices(baseline, _load_sample())
    assert result["scored_slices"] == 6
    assert result["unscored_slices"] == 0
    assert all(s["recall"] == 1.0 for s in result["slices"])
    assert result["worst_recall"] == 1.0
    # No cross-slice mean exists anywhere in the result.
    assert "mean" not in result and "average" not in result


def test_single_missed_requirement_lowers_only_its_own_slice():
    baseline = load_baseline()
    produced = copy.deepcopy(_load_sample())
    key = slice_id("ES_IE", "non_eu_passport_holder")
    # Drop the 'D' Employment visa step from the priority Madrid->Dublin slice:
    # the single rare miss this metric exists to catch.
    produced[key][0] = [s for s in produced[key][0] if "employment visa" not in s["title"].lower()]

    result = score_slices(baseline, produced)

    hit = next(s for s in result["slices"]
               if (s["corridor"], s["employee_type"]) == ("ES_IE", "non_eu_passport_holder"))
    assert hit["recall"] == round(6 / 7, 4)
    assert hit["missing"] == ["d_visa_before_travel"]
    # Every OTHER slice is untouched.
    for s in result["slices"]:
        if (s["corridor"], s["employee_type"]) != ("ES_IE", "non_eu_passport_holder"):
            assert s["recall"] == 1.0
    # The worst slice is surfaced FIRST and identified.
    assert result["slices"][0] is hit
    assert result["worst_slice"] == {
        "corridor": "ES_IE",
        "employee_type": "non_eu_passport_holder",
        "recall": round(6 / 7, 4),
        "missing": ["d_visa_before_travel"],
    }
    assert result["worst_recall"] == round(6 / 7, 4)


def test_a_miss_in_one_case_of_many_still_lowers_the_slice():
    # Two employees in the slice; one roadmap misses the IRP step. Recall must
    # drop \u2014 'most cases were fine' is exactly the averaging trap.
    baseline = load_baseline()
    slice_def = next(s for s in baseline["slices"]
                     if (s["corridor"], s["employee_type"]) == ("ES_IE", "non_eu_passport_holder"))
    good = _load_sample()[slice_id("ES_IE", "non_eu_passport_holder")][0]
    bad = [s for s in good if "irp" not in s["title"].lower()]

    report = score_slice(slice_def, [good, bad])
    assert report["n_roadmaps"] == 2
    assert "irp_registration_90_days" in report["missing"]
    assert report["recall"] < 1.0


def test_slice_with_no_data_is_reported_not_hidden():
    baseline = load_baseline()
    produced = _load_sample()
    produced.pop(slice_id("NO_FR", "norwegian_national"))
    result = score_slices(baseline, produced)
    assert result["scored_slices"] == 5
    assert result["unscored_slices"] == 1
    no_data = [s for s in result["slices"] if s["recall"] is None]
    assert [(s["corridor"], s["employee_type"]) for s in no_data] == [("NO_FR", "norwegian_national")]
    # Unscored slices trail the scored ones but stay visible in the report.
    assert result["slices"][-1]["recall"] is None

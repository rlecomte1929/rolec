"""
Phase 3a — feedback → gold candidate conversion.

Turns a `rejected` / `edited` ai_human_feedback verdict (joined to its replay
record) into a CANDIDATE regression gold case. Governance: candidates are staged
for human promotion — the converter must never mutate the authoritative gold.

These tests pin the pure core: an `edited` roadmap correction → a positive
candidate whose expected_steps are derived from the corrected steps; a `rejected`
verdict → a negative (must-not-recur) candidate; approved/unknown-trace → skipped.
"""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.feedback_to_gold import build_gold_candidates


def _replay(trace_id, corridor="IN_DE", feature_key="rag_roadmap", steps=None, result="OK"):
    return {
        "id": f"rec-{trace_id}",
        "trace_id": trace_id,
        "corridor": corridor,
        "feature_key": feature_key,
        "result": result,
        "output_masked": json.dumps({"result": result, "steps": steps or []}),
    }


def _fb(fid, trace, verdict, edited=None, comment=None):
    return {"id": fid, "trace_session_id": trace, "verdict": verdict,
            "edited_output_json": edited, "comment": comment}


def test_edited_roadmap_becomes_positive_candidate_with_derived_steps():
    edited = {"steps": [
        {"order": 1, "title": "Apply for the EU Blue Card visa"},
        {"order": 2, "title": "Register your address (Anmeldung)"},
        {"order": 3, "title": "Collect the residence permit card"},
    ]}
    feedback = [_fb("fb1", "t1", "edited", edited=edited, comment="added the permit step")]
    replays = [_replay("t1", steps=[{"order": 1, "title": "Apply for the EU Blue Card visa"}])]

    cands = build_gold_candidates(feedback, replays)

    assert len(cands) == 1
    c = cands[0]
    assert c["kind"] == "positive"
    assert c["corridor"] == "IN_DE"
    assert c["feature_key"] == "rag_roadmap"
    assert c["source_feedback_id"] == "fb1"
    # expected_steps derived: one per corrected step, each with a key + a match substring.
    steps = c["case"]["expected_steps"]
    assert len(steps) == 3
    assert all(s.get("key") and s.get("match") for s in steps)
    # the match must actually be findable in the source title (so it can match future output)
    assert steps[2]["match"] in "collect the residence permit card"
    # sequential ordering constraints derived from the corrected sequence
    assert c["case"]["order"] == [[steps[0]["key"], steps[1]["key"]],
                                  [steps[1]["key"], steps[2]["key"]]]


def test_rejected_becomes_negative_must_not_recur_candidate():
    feedback = [_fb("fb2", "t2", "rejected", comment="hallucinated a non-existent permit office")]
    replays = [_replay("t2", steps=[{"order": 1, "title": "Visit the imaginary permit office"}])]

    cands = build_gold_candidates(feedback, replays)

    assert len(cands) == 1
    c = cands[0]
    assert c["kind"] == "negative"
    assert c["verdict"] == "rejected"
    assert c["case"]["reason"] == "hallucinated a non-existent permit office"
    assert "Visit the imaginary permit office" in c["case"]["original_step_titles"]


def test_approved_and_unknown_trace_are_skipped():
    feedback = [
        _fb("fb3", "t3", "approved"),                 # approved → no candidate
        _fb("fb4", "t-missing", "rejected"),          # no replay record → skipped
    ]
    replays = [_replay("t3")]

    cands = build_gold_candidates(feedback, replays)

    assert cands == []


def test_loop_proof_promoted_candidate_catches_the_old_bad_output():
    """The whole point of the flywheel: a promoted candidate (used as gold) PASSES
    the corrected roadmap and FAILS the original deficient one → a real permanent
    regression case."""
    from backend.eval.roadmap_metrics import score_roadmap

    corrected_steps = [
        {"order": 1, "title": "Apply for the EU Blue Card visa"},
        {"order": 2, "title": "Register your address (Anmeldung)"},
        {"order": 3, "title": "Collect the residence permit card"},
    ]
    original_steps = [{"order": 1, "title": "Apply for the EU Blue Card visa"}]  # missing 2 steps

    feedback = [_fb("fb1", "t1", "edited", edited={"steps": corrected_steps})]
    replays = [_replay("t1", steps=original_steps)]
    gold_case = build_gold_candidates(feedback, replays)[0]["case"]  # promote this candidate

    # Corrected output satisfies the new gold ...
    good = score_roadmap(corrected_steps, gold_case)
    assert good["completeness"] == 1.0 and good["ordering"] == 1.0
    # ... and the original bad output is now caught by it.
    bad = score_roadmap(original_steps, gold_case)
    assert bad["completeness"] < 1.0


def test_governance_writer_only_touches_candidates_file(tmp_path):
    """The converter must never write the authoritative gold — only candidates.jsonl."""
    from backend.app.services.feedback_to_gold import write_candidates

    cand = {"kind": "negative", "corridor": "IN_DE", "feature_key": "rag_roadmap",
            "verdict": "rejected", "case": {"reason": "x"}}
    dest = write_candidates([cand], tmp_path, "IN_DE")

    assert dest.name == "candidates.jsonl"
    assert dest.parent.name == "IN_DE"
    # No authoritative gold file (in_de.json / in_de.jsonl) was created anywhere under the out dir.
    assert not list(tmp_path.rglob("in_de.json"))
    assert not list(tmp_path.rglob("in_de.jsonl"))

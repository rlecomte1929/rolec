"""Beam pass runner + tolerant JSON parsing.

Covers the two failures that cost real runs, and the ordering fix that cost a golden test:

  * run `beam:FR-NO:eea:msxf6rwlbjt3` died on JSON parse failures — the model fenced its
    output. Five paid calls lost to formatting. `parsing.py` recovers that case.
  * an exporter dropped within-pass ordering, and clustering is greedy in arrival order,
    so the golden fixture had to be reverse-engineered — of 200 within-pass shuffles, 100
    reproduce the reference and 100 do not. `arrival_ordinal` removes the guesswork.

No network and no key: the model call is injected. That is deliberate — a test that needs
a paid call does not get run, and this is the layer where a silent regression is expensive.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.imports.candidate_beam import parsing, pipeline, ranking  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


# ─── parsing: the run-2 killer ──────────────────────────────────────────────


def test_plain_json_array_parses():
    assert parsing.parse_model_json('[{"title": "A"}]') == [{"title": "A"}]


def test_json_fenced_output_parses():
    """```json fences — the exact shape that killed run 2."""
    text = '```json\n[{"title": "Tax Exit from France"}]\n```'
    assert parsing.parse_model_json(text) == [{"title": "Tax Exit from France"}]


def test_bare_fenced_output_parses():
    assert parsing.parse_model_json('```\n[{"title": "A"}]\n```') == [{"title": "A"}]


def test_prose_before_the_array_is_tolerated():
    text = 'Certainly! Here is the list:\n[{"title": "A"}]\nLet me know if you need more.'
    assert parsing.parse_model_json(text) == [{"title": "A"}]


def test_largest_fenced_block_wins_over_a_narrated_example():
    text = (
        "For example:\n```json\n[{\"title\": \"x\"}]\n```\n"
        "And the full set:\n```json\n[{\"title\": \"a\"}, {\"title\": \"b\"}, {\"title\": \"c\"}]\n```"
    )
    assert len(parsing.parse_model_json(text)) == 3


def test_braces_inside_strings_do_not_break_extraction():
    text = 'Note: use {curly} carefully.\n[{"title": "a ] b", "action_required": "x"}]'
    assert parsing.parse_model_json(text) == [{"title": "a ] b", "action_required": "x"}]


def test_malformed_json_raises_rather_than_being_repaired():
    """A parser that guesses at broken syntax would invent obligations. Fail loudly."""
    with pytest.raises(parsing.ModelJsonError):
        parsing.parse_model_json('[{"title": "A", ')


def test_empty_output_raises():
    with pytest.raises(parsing.ModelJsonError):
        parsing.parse_model_json("   ")


def test_object_wrapper_is_unwrapped_in_order():
    payload = {"items": [{"title": "a"}, {"title": "b"}]}
    assert [i["title"] for i in parsing.extract_items(payload)] == ["a", "b"]


def test_a_single_unwrapped_item_is_accepted():
    payload = {"title": "Only one", "action_required": "do it"}
    assert parsing.extract_items(payload) == [payload]


def test_unrecognised_object_shape_raises():
    with pytest.raises(parsing.ModelJsonError):
        parsing.extract_items({"summary": "no list here"})


def test_extract_items_preserves_order_and_drops_non_dicts():
    payload = [{"title": "a"}, "junk", {"title": "b"}]
    assert [i["title"] for i in parsing.extract_items(payload)] == ["a", "b"]


# ─── arrival_ordinal: the E3 fix ────────────────────────────────────────────


def test_parse_pass_numbers_variants_from_one():
    items = [{"title": f"T{i}", "action_required": "do"} for i in range(1, 4)]
    variants = ranking.parse_pass(items, pass_number=1)
    assert [v.arrival_ordinal for v in variants] == [1, 2, 3]


def test_ordinal_indexes_the_raw_array_so_drops_leave_a_gap():
    """Indexed against the raw array, not the survivors: a gap is evidence that an item
    was dropped, rather than being silently closed up."""
    items = [
        {"title": "kept", "action_required": "do"},
        {"title": "", "action_required": "no title -> dropped"},
        {"title": "also kept", "action_required": "do"},
    ]
    variants = ranking.parse_pass(items, pass_number=1)
    assert [v.arrival_ordinal for v in variants] == [1, 3]


def test_ordinal_survives_into_the_persisted_variant_dict():
    variants = ranking.parse_pass([{"title": "T", "action_required": "do"}], pass_number=2)
    assert variants[0].as_dict()["arrival_ordinal"] == 1


def test_order_variants_reconstructs_the_clustering_input():
    """The whole point of E3: stored variants in any order sort back to arrival order."""
    p1 = ranking.parse_pass([{"title": f"A{i}", "action_required": "do"} for i in range(3)], 1)
    p2 = ranking.parse_pass([{"title": f"B{i}", "action_required": "do"} for i in range(2)], 2)
    shuffled = [p2[1], p1[2], p1[0], p2[0], p1[1]]
    recovered = ranking.order_variants(shuffled)
    assert [(v.pass_number, v.arrival_ordinal) for v in recovered] == [
        (1, 1), (1, 2), (1, 3), (2, 1), (2, 2),
    ]


def test_the_golden_fixture_can_be_replayed_from_ordinals_alone():
    """Against the REAL validated run: stamping ordinals then sorting by them reproduces
    the stored order exactly. If this holds, no future fixture needs reverse-engineering."""
    payload = json.loads((FIXTURES / "candidate_beam_fr_no_eea_pass_outputs.json").read_text())
    for pass_output in payload["passOutputs"]:
        stored = [i["title"] for i in pass_output["items"]]
        variants = ranking.parse_pass(pass_output["items"], pass_output["pass"])
        replayed = [v.title for v in ranking.order_variants(reversed(variants))]
        assert replayed == [t for t in stored if t in set(replayed)]


# ─── the pass runner ────────────────────────────────────────────────────────


def _stub(payload: str):
    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        return payload

    complete.calls = calls  # type: ignore[attr-defined]
    return complete


ONE_ITEM = '```json\n[{"title": "Tax Exit", "action_required": "File the form", "source": null}]\n```'


def test_run_pass_parses_fenced_output_and_reports_ok():
    record = pipeline.run_pass(
        corridor="FR-NO", employee_type="eea",
        framing="zero_shot_official_audit", complete=_stub(ONE_ITEM),
    )
    assert record["ok"] is True
    assert [i["title"] for i in record["items"]] == ["Tax Exit"]


def test_a_failed_pass_is_recorded_not_raised():
    def boom(**kwargs):
        raise RuntimeError("provider 503")

    record = pipeline.run_pass(
        corridor="FR-NO", employee_type="eea",
        framing="lived_experience", complete=boom,
    )
    assert record["ok"] is False and record["items"] == []
    assert "provider 503" in record["error"]


def test_unparseable_output_is_named_as_such():
    record = pipeline.run_pass(
        corridor="FR-NO", employee_type="eea",
        framing="lived_experience", complete=_stub("I'm sorry, I can't help with that."),
    )
    assert record["ok"] is False
    assert "unparseable model output" in record["error"]


def test_context_is_pii_masked_before_it_reaches_the_prompt():
    """Corridor context is operator-written free text and can name a real person. The
    provider is a sub-processor of anything we send (GDPR Art. 28/44)."""
    prompt = pipeline.build_pass_prompt(
        corridor="FR-NO", employee_type="eea", framing="lived_experience",
        context="Employee reachable on +33 6 12 34 56 78 for follow-up.",
    )
    assert "+33 6 12 34 56 78" not in prompt["user"]
    assert "REDACTED" in prompt["user"]


def test_prompt_forbids_inventing_a_source():
    prompt = pipeline.build_pass_prompt(
        corridor="FR-NO", employee_type="eea", framing="professional_advisor",
    )
    assert "NEVER invent a URL" in prompt["system"]


def test_unknown_framing_is_rejected():
    with pytest.raises(ValueError):
        pipeline.build_pass_prompt(corridor="FR-NO", employee_type="eea", framing="freestyle")


def test_model_default_comes_from_llm_client_not_a_literal():
    from backend.app.services import llm_client

    assert pipeline.default_model() == llm_client._OPENAI_DEFAULT_MODEL


# ─── the beam ───────────────────────────────────────────────────────────────


def test_run_beam_stamps_arrival_ordinal_on_every_stored_item():
    out = pipeline.run_beam(
        corridor="FR-NO", employee_type="eea", passes=3, complete=_stub(ONE_ITEM),
    )
    for pass_output in out["pass_outputs"]:
        assert [i["arrival_ordinal"] for i in pass_output["items"]] == [1]


def test_run_beam_keeps_the_slot_of_a_failed_pass():
    """Dropping it would inflate cross-pass agreement — an item in 2 of 2 survivors would
    read 2/2 when a third pass never ran, and pass_frequency is the reviewer's main signal."""
    state = {"n": 0}

    def flaky(**kwargs):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("provider 503")
        return ONE_ITEM

    out = pipeline.run_beam(
        corridor="FR-NO", employee_type="eea", passes=3, complete=flaky,
    )
    assert len(out["pass_meta"]) == 3
    assert [m["ok"] for m in out["pass_meta"]] == [True, False, True]
    assert out["passes_completed"] == 2
    assert out["passes_requested"] == 3
    assert out["candidates"][0]["passes_total"] == 2


def test_a_beam_with_fewer_than_two_usable_passes_is_failed_not_empty_success():
    def boom(**kwargs):
        raise RuntimeError("no key")

    out = pipeline.run_beam(corridor="FR-NO", employee_type="eea", passes=2, complete=boom)
    assert out["status"] == "failed"
    assert out["candidate_count"] == 0


def test_run_beam_status_matches_the_schema_check_constraint():
    out = pipeline.run_beam(
        corridor="FR-NO", employee_type="eea", passes=2, complete=_stub(ONE_ITEM),
    )
    assert out["status"] in {"generating", "pending_review", "failed"}
    assert out["passes_requested"] >= 2


def test_passes_outside_the_cost_clamp_are_rejected():
    with pytest.raises(ValueError):
        pipeline.run_beam(corridor="FR-NO", employee_type="eea", passes=1, complete=_stub(ONE_ITEM))


def test_framings_are_applied_in_the_reference_order():
    out = pipeline.run_beam(
        corridor="FR-NO", employee_type="eea", passes=5, complete=_stub(ONE_ITEM),
    )
    assert [p["framing"] for p in out["pass_outputs"]] == list(pipeline.PASS_FRAMINGS)
    assert [p["pass"] for p in out["pass_outputs"]] == [1, 2, 3, 4, 5]


# ─── framing cycling (2..7) ─────────────────────────────────────────────────


def test_framings_cycle_past_the_fifth_pass():
    """`PASS_FRAMINGS[:passes]` truncated, which quietly made 5 the ceiling. The schema
    CHECK has always allowed `passes_requested BETWEEN 2 AND 7`, so a run asking for six
    failed with an unexplained ValueError against a column that had agreed to store it."""
    assert pipeline.framing_for(1) == pipeline.PASS_FRAMINGS[0]
    assert pipeline.framing_for(5) == pipeline.PASS_FRAMINGS[4]
    assert pipeline.framing_for(6) == pipeline.PASS_FRAMINGS[0]
    assert pipeline.framing_for(7) == pipeline.PASS_FRAMINGS[1]


def test_framing_for_is_one_based():
    with pytest.raises(ValueError):
        pipeline.framing_for(0)


def test_a_seven_pass_run_actually_runs_seven_passes():
    out = pipeline.run_beam(
        corridor="FR-NO", employee_type="eea", passes=7, complete=_stub(ONE_ITEM)
    )
    assert len(out["pass_outputs"]) == 7
    assert [p["pass"] for p in out["pass_outputs"]] == [1, 2, 3, 4, 5, 6, 7]
    assert out["passes_requested"] == 7


def test_the_repeated_framings_are_the_first_two():
    out = pipeline.run_beam(
        corridor="FR-NO", employee_type="eea", passes=7, complete=_stub(ONE_ITEM)
    )
    framings = [p["framing"] for p in out["pass_outputs"]]
    assert framings[5] == pipeline.PASS_FRAMINGS[0]
    assert framings[6] == pipeline.PASS_FRAMINGS[1]


@pytest.mark.parametrize("passes", [1, 8])
def test_the_clamp_still_rejects_outside_two_to_seven(passes):
    with pytest.raises(ValueError, match="between 2 and 7"):
        pipeline.run_beam(
            corridor="FR-NO", employee_type="eea", passes=passes, complete=_stub(ONE_ITEM)
        )

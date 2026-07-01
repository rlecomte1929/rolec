"""
Mission Control P3 — the triage eval as a CI regression guard: the real classifier
must keep meeting the gate on the gold set, and the gold must be a real guard (a
mislabel drops the score).
"""
from pathlib import Path

from backend.eval.run_triage_eval import load_gold
from backend.eval.triage_metrics import score_triage

_GOLD = Path(__file__).resolve().parent / "fixtures/eval/triage/triage_gold.jsonl"


def test_real_classifier_meets_gate_on_gold():
    report = score_triage(load_gold(_GOLD))
    assert report["kind_accuracy"] >= 0.85, report["confusion"]


def test_gold_is_a_real_guard():
    gold = load_gold(_GOLD)
    poisoned = [dict(c) for c in gold]
    first = poisoned[0]
    first["expected_kind"] = "idea" if first["expected_kind"] != "idea" else "task"
    assert score_triage(poisoned)["kind_accuracy"] < 1.0

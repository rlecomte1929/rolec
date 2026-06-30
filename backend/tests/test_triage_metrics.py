"""
Mission Control P3 — triage eval metrics: kind/priority accuracy over a gold set
of demands. Classifier injectable so the math is unit-tested against a known set.
"""
from backend.eval.triage_metrics import score_triage


def _clf(mapping):
    return lambda title, body="": mapping[title]


def test_perfect_kind_accuracy():
    cases = [
        {"title": "a", "expected_kind": "bug", "expected_priority": "P1"},
        {"title": "b", "expected_kind": "idea", "expected_priority": "P3"},
    ]
    clf = _clf({"a": {"kind": "bug", "priority": "P1"}, "b": {"kind": "idea", "priority": "P3"}})
    r = score_triage(cases, classifier=clf)
    assert r["kind_accuracy"] == 1.0
    assert r["priority_accuracy"] == 1.0
    assert r["overall_accuracy"] == 1.0


def test_one_kind_wrong():
    cases = [
        {"title": "a", "expected_kind": "bug"},
        {"title": "b", "expected_kind": "idea"},
    ]
    clf = _clf({"a": {"kind": "bug", "priority": "P1"}, "b": {"kind": "bug", "priority": "P2"}})
    r = score_triage(cases, classifier=clf)
    assert r["kind_accuracy"] == 0.5
    assert r["confusion"]["idea->bug"] == 1


def test_priority_optional():
    cases = [{"title": "a", "expected_kind": "bug"}]  # no expected_priority
    clf = _clf({"a": {"kind": "bug", "priority": "P2"}})
    r = score_triage(cases, classifier=clf)
    assert r["priority_accuracy"] is None
    assert r["kind_accuracy"] == 1.0


def test_empty_is_zero():
    assert score_triage([], classifier=_clf({}))["total"] == 0

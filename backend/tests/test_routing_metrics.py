"""
Routing eval metrics — accuracy + per-domain precision/recall/F1 + ambiguous-rate
over a (question → expected_domain) gold set. Classifier injectable so the math is
unit-tested against a known confusion matrix.
"""
from backend.eval.routing_metrics import score_routing


def _clf(mapping):
    return lambda q: {"domain": mapping[q], "immigration_score": 0, "policy_score": 0}


def test_perfect_accuracy():
    cases = [
        {"question": "a", "expected_domain": "immigration"},
        {"question": "b", "expected_domain": "policy"},
    ]
    r = score_routing(cases, classifier=_clf({"a": "immigration", "b": "policy"}))
    assert r["accuracy"] == 1.0
    assert r["ambiguous_rate"] == 0.0


def test_counts_precision_recall_on_a_misroute():
    cases = [
        {"question": "a", "expected_domain": "immigration"},
        {"question": "b", "expected_domain": "immigration"},
        {"question": "c", "expected_domain": "policy"},
    ]
    # b (immigration) is misrouted to policy.
    r = score_routing(cases, classifier=_clf({"a": "immigration", "b": "policy", "c": "policy"}))
    assert r["accuracy"] == 2 / 3
    assert r["per_domain"]["immigration"]["precision"] == 1.0  # a only, no FP
    assert r["per_domain"]["immigration"]["recall"] == 0.5     # missed b
    assert r["per_domain"]["policy"]["precision"] == 0.5       # c right, b wrong
    assert r["per_domain"]["policy"]["recall"] == 1.0
    assert r["confusion"]["immigration->policy"] == 1


def test_ambiguous_rate_and_accuracy():
    cases = [
        {"question": "a", "expected_domain": "immigration"},
        {"question": "b", "expected_domain": "ambiguous"},
    ]
    r = score_routing(cases, classifier=_clf({"a": "ambiguous", "b": "ambiguous"}))
    assert r["ambiguous_rate"] == 1.0
    assert r["accuracy"] == 0.5


def test_empty_is_zero_not_crash():
    r = score_routing([], classifier=_clf({}))
    assert r["accuracy"] == 0.0
    assert r["total"] == 0

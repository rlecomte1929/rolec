"""
WS-B — tests for the pass@k / pass^k stability harness.
"""
from __future__ import annotations

from backend.scripts.eval_pass_at_k import run_pass_at_k, _demo_callable


def test_deterministic_callable_is_fully_stable():
    report = run_pass_at_k(_demo_callable, n=5, expected="us_l1b")
    assert report["n"] == 5
    assert report["unique_outputs"] == 1
    assert report["stability"] == 1.0
    assert report["pass_at_k"] == 1.0
    assert report["pass_pow_k"] == 1.0
    assert report["modal_output"] == "us_l1b"


def test_wrong_expected_value_fails_all_passes_but_stays_stable():
    report = run_pass_at_k(_demo_callable, n=4, expected="japan_coe")
    assert report["stability"] == 1.0          # still deterministic
    assert report["pass_rate"] == 0.0
    assert report["pass_at_k"] == 0.0
    assert report["pass_pow_k"] == 0.0


def test_stochastic_callable_partial_agreement():
    seq = iter(["a", "a", "b", "a", "b"])
    report = run_pass_at_k(lambda: next(seq), n=5, expected="a")
    assert report["unique_outputs"] == 2
    assert report["stability"] == 0.6          # modal "a" in 3/5 runs
    assert report["pass_rate"] == 0.6
    assert report["pass_at_k"] == 1.0          # at least one "a"
    assert report["pass_pow_k"] == 0.0         # not all "a"


def test_predicate_based_pass():
    seq = iter([1, 2, 3, 4])
    report = run_pass_at_k(lambda: next(seq), n=4, predicate=lambda x: x % 2 == 0)
    assert report["pass_rate"] == 0.5
    assert report["pass_at_k"] == 1.0


def test_n_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        run_pass_at_k(_demo_callable, n=0)

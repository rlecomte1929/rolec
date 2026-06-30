"""[P2] Tests for the supplier-weight learner scaffold (pure functions)."""
from backend.app.recommendations import weight_learner as L


def _slate(case_id, category, items, segment=None):
    return {"category": category, "segment": segment, "case_id": case_id, "items_json": items}


def test_build_training_examples_joins_chosen_vs_shown():
    slates = [
        _slate("c1", "banks", [
            {"item_id": "b-1", "breakdown": {"language": 1.0, "fees": 0.2}},
            {"item_id": "b-2", "breakdown": {"language": 0.1, "fees": 0.9}},
        ]),
    ]
    selections = [{"case_id": "c1", "item_id": "b-1"}]
    examples = L.build_training_examples(slates, selections)
    assert len(examples) == 2
    chosen = {e.features["language"]: e.chosen for e in examples}
    assert chosen[1.0] is True   # b-1 was chosen
    assert chosen[0.1] is False  # b-2 was not

    # Items without a breakdown are skipped.
    s2 = [_slate("c2", "banks", [{"item_id": "b-9"}])]
    assert L.build_training_examples(s2, []) == []


def test_fit_weights_from_examples_favors_discriminating_factor():
    # 60 examples: chosen items have high 'language', low 'fees'; vice-versa.
    examples = []
    for i in range(30):
        examples.append(L.TrainingExample("banks", None, {"language": 1.0, "fees": 0.0}, True))
        examples.append(L.TrainingExample("banks", None, {"language": 0.0, "fees": 1.0}, False))
    w = L.fit_weights_from_examples(examples, ["language", "fees"])
    assert w is not None
    assert abs(sum(w.values()) - 1.0) < 1e-6        # normalised
    assert all(v >= 0 for v in w.values())          # non-negative
    assert w["language"] > w["fees"]                # learned the signal


def test_fit_weights_single_class_returns_none():
    examples = [L.TrainingExample("banks", None, {"language": 1.0, "fees": 0.0}, True) for _ in range(60)]
    assert L.fit_weights_from_examples(examples, ["language", "fees"]) is None


def test_fit_cell_noops_below_threshold():
    examples = [
        L.TrainingExample("banks", None, {"language": 1.0, "fees": 0.0}, i % 2 == 0)
        for i in range(10)
    ]
    weights, reason = L.fit_cell(examples, ["language", "fees"], min_pairs=50)
    assert weights is None
    assert "insufficient data" in reason


def test_fit_cell_fits_above_threshold():
    examples = []
    for i in range(40):
        examples.append(L.TrainingExample("banks", None, {"language": 1.0, "fees": 0.0}, True))
        examples.append(L.TrainingExample("banks", None, {"language": 0.0, "fees": 1.0}, False))
    weights, reason = L.fit_cell(examples, ["language", "fees"], min_pairs=50)
    assert weights is not None
    assert "fit on 80 examples" == reason


def test_group_by_cell():
    examples = [
        L.TrainingExample("banks", "paris", {"language": 1.0}, True),
        L.TrainingExample("banks", "paris", {"language": 0.0}, False),
        L.TrainingExample("banks", None, {"language": 1.0}, True),
    ]
    cells = L.group_by_cell(examples)
    assert set(cells.keys()) == {("banks", "paris"), ("banks", None)}
    assert len(cells[("banks", "paris")]) == 2

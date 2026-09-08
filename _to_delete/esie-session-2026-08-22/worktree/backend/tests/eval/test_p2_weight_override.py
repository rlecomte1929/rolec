"""[P2] Tests for the per-segment weight-override accessor (byte-identical OFF)."""
import importlib

from backend.app.recommendations import weights as W


def test_get_weights_byte_identical_when_flag_off(monkeypatch):
    monkeypatch.delenv("SUPPLIER_LEARNED_WEIGHTS", raising=False)
    for category, expected in W.WEIGHTS.items():
        got = W.get_weights(category)
        # Same object identity → genuinely byte-identical to legacy WEIGHTS[cat].
        assert got is expected, category
        # ...and a segment hint is ignored entirely when the flag is off.
        assert W.get_weights(category, segment="paris") is expected, category


def test_get_weights_blends_when_flag_on(monkeypatch):
    monkeypatch.setenv("SUPPLIER_LEARNED_WEIGHTS", "1")
    # Stub the store so no DB is needed: override one existing factor.
    monkeypatch.setattr(
        W, "_read_segment_override",
        lambda category, segment: {"language": 0.99, "not_a_factor": 0.5} if category == "banks" else None,
    )
    got = W.get_weights("banks", segment="paris")
    assert got is not W.WEIGHTS["banks"]              # a merged copy, not the global
    assert got["language"] == 0.99                    # existing factor overridden
    assert "not_a_factor" not in got                  # unknown factor never introduced
    assert set(got) == set(W.WEIGHTS["banks"])        # factor set preserved
    # A category with no override falls back to the global object.
    assert W.get_weights("insurance") is W.WEIGHTS["insurance"]


def test_get_weights_flag_on_but_no_override_is_identity(monkeypatch):
    monkeypatch.setenv("SUPPLIER_LEARNED_WEIGHTS", "true")
    monkeypatch.setattr(W, "_read_segment_override", lambda category, segment: None)
    assert W.get_weights("banks") is W.WEIGHTS["banks"]


def test_derive_segment_from_dict_and_object():
    assert W.derive_segment({"destination_city": "Paris, France"}) == "paris"
    assert W.derive_segment({"destination_city": "  Berlin  "}) == "berlin"
    assert W.derive_segment({}) is None
    assert W.derive_segment(None) is None

    class Crit:
        destination_city = "Lisbon"

    assert W.derive_segment(Crit()) == "lisbon"

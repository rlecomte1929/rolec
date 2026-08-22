"""The batch gate must grade a batch by the contract it declares, not by another batch's.

Sections 1-3 of `check_otto_batches.py` encode the otto-loader v6 delivery contract. Applied
to every batch with an NDJSON, they fail any batch of a different shape for the sole reason
that it is a different shape.

`ve-ie-entry-family-2026-08-20` is that case: it predates the gate, uses `fact_uid` /
`applies_to_nationality_classes`, has no `fact_type` or `confidence_score`, targets
`public.requirement_items`, and has its own passing validator
(`scripts/verify_aiq_2027_ve_ie_load.py`). Graded against v6 it scored 18 PASS / 15 FAIL —
measured identically on unmodified `origin/main`, so the gate shipped failing a batch that
was already committed.

It stayed invisible because CI gates only CHANGED batches and #1971 did not touch that one.
The first edit to it would have failed CI for a defect that was never in the edit.
"""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _gate():
    spec = importlib.util.spec_from_file_location(
        "check_otto_batches", os.path.join(ROOT, "scripts", "check_otto_batches.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_batch_without_a_loader_block_is_not_graded_against_v6():
    """ve-ie declares no `loader`, so the v6 record contract does not apply to it."""
    gate = _gate()
    os.chdir(ROOT)
    r = gate.check_batch("ve-ie-entry-family-2026-08-20")
    assert not r.failed, "a batch that never claimed the otto-loader contract was graded by it"
    labels = [label for kind, label, _ in r.lines if kind == "SKIP"]
    assert any("otto-loader contract" in l for l in labels), (
        "the skip must be STATED — an unexplained skip and a false failure are both worse "
        "than a named one"
    )


def test_the_batch_that_DOES_declare_the_contract_is_still_fully_graded():
    """The fix must not become a way to opt out of the gate. es-ie declares `loader`, so it
    keeps every section: record contract, count histograms, promotion simulation."""
    gate = _gate()
    os.chdir(ROOT)
    r = gate.check_batch("es-ie-thirdcountry-requirements-2026-08-22")
    assert not r.failed
    passes = [label for kind, label, _ in r.lines if kind == "PASS"]
    assert len(passes) > 40, f"expected the full v6 grading, got only {len(passes)} checks"
    joined = " ".join(passes)
    assert "promotes" in joined, "promotion simulation did not run"
    assert "confidence_score" in joined, "record contract did not run"


def test_a_reference_batch_with_no_stream_is_still_skipped_by_the_earlier_rule():
    gate = _gate()
    os.chdir(ROOT)
    r = gate.check_batch("ie-isd-visa-required-2026-08-22")
    assert not r.failed
    labels = [label for kind, label, _ in r.lines if kind == "SKIP"]
    assert any("NDJSON" in l for l in labels)

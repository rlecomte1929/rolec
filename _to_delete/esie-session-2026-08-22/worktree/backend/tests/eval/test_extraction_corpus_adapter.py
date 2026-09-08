"""AIQ-515 — offline tests for the extraction harness glue (no API, no DB).

Validates: (1) the per-document adapter groups dossier fields by doc_type with the
right name/is_money; (2) the full chain corpus → build → predictions → run_extraction_eval
scores 1.0 with the reference predictor (plumbing); (3) the real `pipeline` predictor
is guarded (no keys → PredictorUnavailable → CLI skip exit 0). No network, no spend.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.eval.extraction_corpus_adapter import dossier_to_document_records
from backend.eval.run_extraction_eval import run_eval
from backend.scripts.build_extraction_corpus import build_corpus
from backend.scripts import run_extraction_predictions as rep


def test_adapter_groups_by_doc_type_with_money_flag():
    dossier = {
        "dossier_id": "IN_DE_001",
        "extracted_fields": [
            {"field_key": "surname", "value": "Patel", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}},
            {"field_key": "given_name", "value": "Priya", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}},
            {"field_key": "employer_name", "value": "ACME", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}},
            {"field_key": "monthly_salary_eur", "value": "5000", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}},
            {"field_key": "diploma_field", "value": "CS", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}},
        ],
    }
    recs = {r["doc_type"]: r for r in dossier_to_document_records(dossier)}
    assert set(recs) == {"identity_document", "employment_contract", "diploma"}
    assert recs["identity_document"]["document_id"] == "IN_DE_001:identity_document"
    id_names = {f["name"] for f in recs["identity_document"]["fields"]}
    assert id_names == {"surname", "given_name"}
    sal = next(f for f in recs["employment_contract"]["fields"] if f["name"] == "monthly_salary_eur")
    assert sal["is_money"] is True
    assert next(f for f in recs["employment_contract"]["fields"] if f["name"] == "employer_name")["is_money"] is False


def test_unknown_field_keys_are_skipped():
    recs = dossier_to_document_records({"dossier_id": "X", "extracted_fields": [
        {"field_key": "mystery", "value": "z", "bbox": None},
    ]})
    assert recs == []


def test_full_chain_corpus_to_eval_scores_one(tmp_path):
    """build corpus → reference predictions → run_extraction_eval = perfect (plumbing)."""
    corpus = tmp_path / "corpus"
    written = build_corpus(corpus)
    assert written, "no per-document records built"
    # 20 dossiers → identity + employment_contract each; diploma only for IN_DE.
    doc_types = sorted({p.parent.name.split("__", 1)[1] for p in written})
    assert doc_types == ["diploma", "employment_contract", "identity_document"]

    preds = tmp_path / "preds.jsonl"
    n = rep.produce_predictions(corpus, preds, rep.reference_predictor)
    assert n == len(written)

    score = run_eval(corpus, predictions_path=preds)
    assert score.n_fields > 0
    assert score.value_accuracy == 1.0  # reference predictor == ground truth


def test_pipeline_predictor_guarded_without_keys(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(rep.PredictorUnavailable):
        rep.pipeline_predictor({"doc_type": "identity_document", "fields": []})


def test_cli_pipeline_without_keys_skips_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    corpus = tmp_path / "c"; build_corpus(corpus)
    rc = rep.main(["--corpus", str(corpus), "--out", str(tmp_path / "p.jsonl"), "--predictor", "pipeline"])
    assert rc == 0
    assert "skipping (pipeline)" in capsys.readouterr().out

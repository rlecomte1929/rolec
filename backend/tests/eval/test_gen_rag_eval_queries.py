"""
P3 — tests for the ARES-style synthetic query generator (--mock mode, no LLM).

Verifies the generator produces N schema-valid, answerable queries from a real
chunk fixture, and that the answerability gate actually rejects off-topic text.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.scripts.gen_rag_eval_queries import (
    generate,
    is_answerable,
    main,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HR_CHUNKS = _REPO_ROOT / "backend" / "tests" / "fixtures" / "rag_eval" / "hr_policy" / "chunks.jsonl"
_IMM_CHUNKS = _REPO_ROOT / "backend" / "tests" / "fixtures" / "rag_eval" / "chunks.jsonl"

_REQUIRED = {
    "query_id", "corridor", "intent_category", "query_text",
    "expected_chunk_ids", "difficulty", "persona", "notes",
}


def _load_chunk_ids(path: Path) -> set:
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "chunk_id" in row:
            ids.add(row["chunk_id"])
    return ids


def test_mock_generates_n_schema_valid_rows():
    rows = generate(_HR_CHUNKS, n=10, mock=True)
    assert len(rows) == 10
    chunk_ids = _load_chunk_ids(_HR_CHUNKS)
    for r in rows:
        assert _REQUIRED <= set(r)
        assert r["query_id"].startswith("Q-GEN-")
        assert r["query_text"].strip()
        # Each query points at a real chunk in the corpus.
        assert r["expected_chunk_ids"]
        assert set(r["expected_chunk_ids"]) <= chunk_ids
        assert r["difficulty"] in ("easy", "medium", "hard")


def test_mock_query_ids_are_unique_and_sequential():
    rows = generate(_HR_CHUNKS, n=5, mock=True)
    ids = [r["query_id"] for r in rows]
    assert ids == [f"Q-GEN-{i:03d}" for i in range(1, 6)]


def test_every_generated_query_is_answerable_by_its_chunk():
    rows = generate(_HR_CHUNKS, n=10, mock=True)
    chunks = {
        json.loads(line)["chunk_id"]: json.loads(line)
        for line in _HR_CHUNKS.read_text(encoding="utf-8").splitlines()
        if line.strip() and "chunk_id" in json.loads(line)
    }
    for r in rows:
        body = chunks[r["expected_chunk_ids"][0]]["body"]
        assert is_answerable(r["query_text"], body)


def test_answerability_gate_rejects_offtopic():
    body = "The monthly housing allowance cap is EUR 2,500 per month."
    assert is_answerable("What is the monthly housing allowance cap?", body)
    assert not is_answerable("Penguins migrate across the antarctic ice shelf.", body)


def test_mock_is_deterministic():
    a = generate(_IMM_CHUNKS, n=8, mock=True)
    b = generate(_IMM_CHUNKS, n=8, mock=True)
    assert a == b


def test_main_writes_jsonl_with_representative_meta(tmp_path):
    out = tmp_path / "queries_generated.jsonl"
    rc = main(["--corpus", str(_HR_CHUNKS), "--out", str(out), "--mock", "--n", "6"])
    assert rc == 0
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    meta = json.loads(lines[0])
    assert meta["verification_status"] == "representative"
    assert meta["_meta_total_queries"] == 6
    assert len(lines) == 7  # meta + 6 rows
    for ln in lines[1:]:
        assert _REQUIRED <= set(json.loads(ln))

"""
P3 — ARES-style synthetic QUERY generator for the RAG eval golden sets.

Grows the retrieval-eval query sets *without hand-labeling*: for each chunk in a
corpus we ask an LLM to write candidate questions that the chunk answers, then run
an answerability/critique filter that drops any question the chunk can't actually
support. Surviving questions are emitted in the same ``queries.jsonl`` schema the
existing golden sets use (``{query_id, corridor, intent_category, query_text,
expected_chunk_ids[], difficulty, persona, notes}``), with
``_meta.verification_status = "representative"`` — they are synthetic-but-realistic
and still NEED HUMAN CURATION before being treated as hard ground truth.

This mirrors the style of the synthetic chunk generator
(``backend/scripts/gen_rag_eval_chunks.py``): a deterministic offline fixture
producer plus, here, a real-LLM path.

Two modes
─────────
* ``--mock`` (default off, but the ONLY mode the tests use) — deterministic, no
  network. Templates a question from the chunk's topic + distinctive body
  keywords so the produced question provably overlaps the chunk body and passes
  the same answerability filter the LLM path uses.
* live (no ``--mock``) — calls ``llm_client.claude_complete`` to (1) propose
  questions and (2) critique each for answerability. The chunk body is masked
  with ``pii_masker.mask_pii`` BEFORE any LLM egress (GDPR data-minimisation).

Usage
─────
    # Offline deterministic (CI / tests):
    python backend/scripts/gen_rag_eval_queries.py \
        --corpus backend/tests/fixtures/rag_eval/hr_policy/chunks.jsonl \
        --mock --n 10 --json

    # Real LLM (needs ANTHROPIC_API_KEY), write a fixture:
    python backend/scripts/gen_rag_eval_queries.py \
        --corpus backend/tests/fixtures/rag_eval/hr_policy/chunks.jsonl \
        --out backend/tests/fixtures/rag_eval/hr_policy/queries_generated.jsonl --n 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIFFICULTIES = ("easy", "medium", "hard")

# Lexical helpers — shared shape with run_rag_triad's scorer so "answerable"
# means the same thing (content-token overlap) in mock and live filters.
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "for", "of", "to", "and", "or", "in", "on",
    "what", "how", "does", "do", "this", "that", "per", "by", "with", "at",
    "be", "as", "it", "from", "into", "you", "your", "which", "when", "where",
    "policy", "rule", "requirement", "requirements", "about", "say", "says",
}
# Minimum fraction of a question's content tokens that must appear in the chunk
# body for the question to be considered answerable by that chunk.
_ANSWERABLE_MIN_OVERLAP = 0.4


def _content_tokens(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP]


def _iter_chunks(path: Path) -> List[Dict[str, Any]]:
    """Read a chunks.jsonl corpus, skipping the leading ``_meta`` header line(s)."""
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "chunk_id" not in row:  # _meta header
            continue
        out.append(row)
    return out


def _chunk_corridor(chunk: Dict[str, Any]) -> str:
    """The query's ``corridor`` field — immigration corpora key on ``corridor``,
    the HR-policy corpus keys on ``company`` (mirrors the shipped golden sets)."""
    return str(chunk.get("corridor") or chunk.get("company") or "unknown")


def _chunk_topic(chunk: Dict[str, Any]) -> str:
    """The query's ``intent_category`` — ``policy_topic`` (HR) / ``pathway_type``
    (immigration), else the most distinctive token of the chunk id."""
    topic = chunk.get("policy_topic") or chunk.get("pathway_type")
    if topic:
        return str(topic)
    tail = str(chunk.get("chunk_id", "")).split(".")[-1].split("_")
    return next((p for p in tail if p), "general")


def _persona(chunk: Dict[str, Any]) -> str:
    company = chunk.get("company")
    return f"{company}_employee" if company else "relocating_employee"


def _body_keywords(body: str, topic: str, n: int = 3) -> List[str]:
    """First ``n`` distinctive body tokens, excluding the topic words. Deterministic
    (first-occurrence order) so the same chunk always yields the same question."""
    topic_tokens = set(_content_tokens(topic.replace("_", " ")))
    seen: List[str] = []
    for tok in _content_tokens(body):
        if tok in topic_tokens or tok in seen:
            continue
        seen.append(tok)
        if len(seen) >= n:
            break
    return seen


def is_answerable(query_text: str, body: str) -> bool:
    """Heuristic answerability gate: does the chunk body cover the question?

    True when at least ``_ANSWERABLE_MIN_OVERLAP`` of the question's content
    tokens appear in the body. Used directly in mock mode and as a cheap
    pre-filter before the LLM critique in live mode.
    """
    q = _content_tokens(query_text)
    if not q:
        return False
    body_tokens = set(_content_tokens(body))
    covered = sum(1 for t in q if t in body_tokens)
    return (covered / len(q)) >= _ANSWERABLE_MIN_OVERLAP


# ---------------------------------------------------------------------------
# Mock (offline, deterministic) generator
# ---------------------------------------------------------------------------


def mock_questions(chunk: Dict[str, Any]) -> List[Dict[str, str]]:
    """Template one deterministic, answerable question per chunk.

    Built from the chunk's topic + its distinctive body keywords so the question
    provably overlaps the body and survives ``is_answerable``. No network.
    """
    topic = _chunk_topic(chunk)
    topic_phrase = topic.replace("_", " ")
    keywords = _body_keywords(chunk.get("body", ""), topic)
    kw_phrase = " ".join(keywords) if keywords else topic_phrase
    query_text = (
        f"What does the {topic_phrase} policy specify regarding {kw_phrase}?"
    )
    return [{"query_text": query_text, "intent_category": topic, "difficulty": "easy"}]


# ---------------------------------------------------------------------------
# Live (LLM) generator — masks the chunk body before egress
# ---------------------------------------------------------------------------

_GEN_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query_text": {"type": "string"},
                    "intent_category": {"type": "string"},
                    "difficulty": {"type": "string", "enum": list(_DIFFICULTIES)},
                },
                "required": ["query_text", "intent_category", "difficulty"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

_GEN_SYSTEM = (
    "You generate retrieval-eval questions. Given a single policy/immigration "
    "CHUNK, write natural questions a relocating employee would ask that THIS "
    "chunk fully answers. Do not invent facts not present in the chunk. Return "
    "JSON only."
)

_CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["answerable"],
    "additionalProperties": False,
}

_CRITIQUE_SYSTEM = (
    "You are a strict answerability judge. Given a CHUNK and a QUESTION, answer "
    "whether the chunk alone fully answers the question. Return JSON only."
)


def llm_questions(chunk: Dict[str, Any], per_chunk: int) -> List[Dict[str, str]]:
    """Real LLM proposal + critique. Masks the chunk body before egress."""
    import asyncio

    from backend.app.services.llm_client import claude_complete
    from backend.app.services.pii_masker import mask_pii

    masked_body = mask_pii(chunk.get("body", ""))

    proposal = asyncio.run(
        claude_complete(
            system=_GEN_SYSTEM,
            user=(
                f"CHUNK (topic={_chunk_topic(chunk)}):\n{masked_body}\n\n"
                f"Write up to {per_chunk} distinct questions this chunk answers."
            ),
            schema=_GEN_SCHEMA,
        )
    )
    candidates = (proposal.get("questions") or [])[:per_chunk]

    kept: List[Dict[str, str]] = []
    for cand in candidates:
        query_text = str(cand.get("query_text") or "").strip()
        if not query_text:
            continue
        # Cheap lexical pre-filter, then the LLM critique (defence in depth).
        if not is_answerable(query_text, masked_body):
            continue
        critique = asyncio.run(
            claude_complete(
                system=_CRITIQUE_SYSTEM,
                user=f"CHUNK:\n{masked_body}\n\nQUESTION:\n{query_text}",
                schema=_CRITIQUE_SCHEMA,
            )
        )
        if not critique.get("answerable"):
            continue
        kept.append(
            {
                "query_text": query_text,
                "intent_category": str(cand.get("intent_category") or _chunk_topic(chunk)),
                "difficulty": str(cand.get("difficulty") or "medium"),
            }
        )
    return kept


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _build_row(chunk: Dict[str, Any], idx: int, cand: Dict[str, str]) -> Dict[str, Any]:
    return {
        "query_id": f"Q-GEN-{idx:03d}",
        "corridor": _chunk_corridor(chunk),
        "intent_category": cand["intent_category"],
        "query_text": cand["query_text"],
        "expected_chunk_ids": [chunk["chunk_id"]],
        "difficulty": cand["difficulty"],
        "persona": _persona(chunk),
        "notes": (
            f"Synthetic question auto-generated from chunk {chunk['chunk_id']}; "
            "the source chunk is the expected answering chunk. NEEDS HUMAN CURATION."
        ),
    }


def generate(
    corpus: Path,
    n: int,
    mock: bool,
    per_chunk: int = 3,
) -> List[Dict[str, Any]]:
    """Generate up to ``n`` schema-valid, answerable query rows from ``corpus``."""
    chunks = _iter_chunks(corpus)
    rows: List[Dict[str, Any]] = []
    for chunk in chunks:
        if len(rows) >= n:
            break
        if mock:
            candidates = mock_questions(chunk)
        else:
            candidates = llm_questions(chunk, per_chunk)
        for cand in candidates:
            if len(rows) >= n:
                break
            # Final answerability gate (mock templates pass by construction;
            # this also guards live candidates that slipped the critique).
            if not is_answerable(cand["query_text"], chunk.get("body", "")):
                continue
            rows.append(_build_row(chunk, len(rows) + 1, cand))
    return rows


def _write_jsonl(rows: List[Dict[str, Any]], out: Path, corpus: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "_meta": (
            "Synthetic RAG eval queries auto-generated by "
            "backend/scripts/gen_rag_eval_queries.py from "
            f"{corpus.name}. Questions are synthetic-but-realistic and NEED "
            "HUMAN CURATION before being treated as ground truth."
        ),
        "_meta_schema": "1.0.0",
        "_meta_total_queries": len(rows),
        "verification_status": "representative",
    }
    with out.open("w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Synthesize RAG-eval queries from a chunk corpus.")
    parser.add_argument("--corpus", type=Path, required=True, help="chunks.jsonl corpus to question.")
    parser.add_argument("--out", type=Path, default=None, help="Write queries.jsonl here (optional).")
    parser.add_argument("--n", type=int, default=20, help="Max number of queries to generate.")
    parser.add_argument("--mock", action="store_true", help="Deterministic offline mode (no LLM).")
    parser.add_argument("--per-chunk", type=int, default=3, help="Max LLM candidates per chunk (live mode).")
    parser.add_argument("--json", action="store_true", help="Print the generated rows as JSON to stdout.")
    args = parser.parse_args(argv)

    rows = generate(args.corpus, n=args.n, mock=args.mock, per_chunk=args.per_chunk)

    if args.out:
        _write_jsonl(rows, args.out, args.corpus)
        print(f"wrote {len(rows)} queries -> {args.out}", file=sys.stderr)
    if args.json:
        print(json.dumps(rows, indent=2))
    elif not args.out:
        print(f"generated {len(rows)} queries from {args.corpus} "
              f"(mock={args.mock}); pass --out or --json to capture them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

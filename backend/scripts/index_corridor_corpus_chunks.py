"""
P2-06e · Corridor-corpus → policy_assistant_chunks RAG indexer
─────────────────────────────────────────────────────────────────────────────
Turns a corridor corpus file (schema_version 1.0.0 — the format produced by
P2-06a / P2-06b / the P3-03 corridor research tasks) into RAG chunks and emits
an idempotent, replay-safe SQL block that loads them into
`public.policy_assistant_chunks`.

This is the *RAG-grounding* half of corridor ingestion. Its sibling
`ingest_corridor_corpus.py` (P2-06d) loads the STRUCTURED requirements into
`immigration_requirements`; this script loads the same corpus as embedded text
chunks so the roadmap retriever (`immigration_retriever.retrieve_for_profile`)
can surface grounded rules instead of returning RULE_NOT_FOUND.

WHY a new script: `policy_chunk_indexer.py` builds chunks from a company's HR
policy rows in the DB — it has no notion of corridor corpus JSON. This script
reads the corpus files instead, so a new corridor is RAG-grounded by dropping a
JSON file in `corpus/` and re-running, rather than editing Python.

Chunk model (one concept per chunk, so retrieval picks exactly what applies):
  • 1 corridor overview chunk            (pathway_type = NULL → matches all pathways)
  • 1 chunk per pathway                  (pathway_type = visa_type)
  • 1 chunk per required_document        (pathway_type = visa_type; "any" → NULL)
  • 1 chunk per post_arrival_step        (pathway_type = NULL → corridor-wide)

Metadata contract (consumed by immigration_retriever._applies):
  chunk_metadata.corridor      = corridor_key(from, to)  e.g. "US→FR"
  chunk_metadata.pathway_type  = visa_type | null

Embeddings come from `get_default_embedder()` — HashEmbedder (deterministic, no
API key) unless OPENAI_API_KEY is set, in which case OpenAIEmbedder is used.
Both emit 1536-dim vectors, so the same `embedding vector(1536)` column works.
Re-running with a real key is an idempotent upgrade (the emitted SQL deletes the
corridor's prior chunks first), so a hash-embedded load can be replaced with a
semantic one with no schema change.

Idempotency: for each corridor the SQL first DELETEs that corridor's existing
immigration_rule chunks (scoped by company_id + source_type + corridor), then
INSERTs the freshly-built set. Re-running converges; it never duplicates.

Usage (run from the repo root):
  # Emit the SQL for review (does NOT touch any DB):
  python backend/scripts/index_corridor_corpus_chunks.py \\
      corpus/us_fr_corridor.json corpus/in_de_corridor.json --emit-sql

Apply the emitted SQL via the Supabase migration tooling / MCP apply_migration.
This script is pure-Python apart from the embedder; it never opens a DB
connection.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.immigration_retriever import (  # noqa: E402
    IMMIGRATION_CORPUS_COMPANY_ID,
    IMMIGRATION_SOURCE_TYPE,
    corridor_key,
)
from backend.app.services.policy_assistant_embedder import (  # noqa: E402
    Embedder,
    get_default_embedder,
)


# --- Chunk text renderers ---------------------------------------------------
# Each renderer produces a self-contained paragraph. Include the corridor,
# scheme names, and key numbers as natural text so both the keyword-ish hash
# embedder and a real LLM have enough to work with.

def _join(parts: List[Optional[str]]) -> str:
    return " ".join(p for p in parts if p)


def render_overview(corpus: Dict[str, Any], corridor: str) -> str:
    c = corpus.get("corridor", {})
    pathways = corpus.get("pathways", [])
    pathway_bits = [
        f"{p.get('scheme_name_en') or p.get('visa_type')} ({p.get('visa_type')})"
        for p in pathways
    ]
    return _join([
        f"Immigration corridor {c.get('from_country_name') or c.get('from')} "
        f"({c.get('from')}) to {c.get('to_country_name') or c.get('to')} "
        f"({c.get('to')}), corridor {corridor}.",
        f"Classification: {c.get('classification')}." if c.get("classification") else None,
        c.get("description"),
        ("Available pathways: " + "; ".join(pathway_bits) + ".") if pathway_bits else None,
    ])


def render_pathway(p: Dict[str, Any], corridor: str) -> str:
    el = p.get("eligibility") or {}
    salary = el.get("salary_min_eur_annual")
    contract = el.get("contract_type")
    proc_low = p.get("typical_processing_days_low")
    proc_high = p.get("typical_processing_days_high")
    return _join([
        f"{p.get('scheme_name_en') or p.get('visa_type')} "
        f"({p.get('scheme_name_native') or ''}), visa type {p.get('visa_type')}, "
        f"for the {corridor} corridor.",
        ("For employee types: " + ", ".join(p.get("employee_types") or []) + ".")
        if p.get("employee_types") else None,
        f"Duration {p['duration_months']} months." if p.get("duration_months") else None,
        f"Renewable via {p.get('renewal_path')}." if p.get("renewable") and p.get("renewal_path") else None,
        f"Minimum salary EUR {salary:g} per year ({el.get('salary_basis') or 'statutory'})."
        if isinstance(salary, (int, float)) else None,
        ("Contract types: " + ", ".join(contract) + ".") if isinstance(contract, list) and contract else None,
        ("Recognised qualification required." if el.get("qualification_required")
         else "No formal qualification required.") if "qualification_required" in el else None,
        f"Typical processing {proc_low}-{proc_high} days."
        if proc_low is not None and proc_high is not None else None,
        f"Fast-track available ({p.get('fast_track_label_native') or 'accelerated procedure'}), "
        f"{p.get('fast_track_low_days')}-{p.get('fast_track_high_days')} days."
        if p.get("fast_track_available") else None,
        f"Post-arrival validation required within {p.get('post_arrival_validation_window_days')} days."
        if p.get("post_arrival_validation_required") else None,
        f"Source: {p.get('source_url')} (tier {p.get('source_tier')})." if p.get("source_url") else None,
    ])


def render_document(d: Dict[str, Any], corridor: str) -> str:
    requiredness = (
        "Conditional" if d.get("is_conditional")
        else ("Required" if d.get("is_required", True) else "Optional")
    )
    flags = []
    if d.get("requires_apostille"):
        flags.append("apostille required")
    if d.get("requires_translation"):
        flags.append("certified translation required")
    return _join([
        f"{requiredness} document for the {corridor} corridor, "
        f"visa type {d.get('visa_type')}: {d.get('document_name')} "
        f"(document type {d.get('document_type')}).",
        ("Notes: " + ", ".join(flags) + ".") if flags else None,
        f"Freshness: must be issued within {d['freshness_days']} days."
        if d.get("freshness_days") else None,
        f"Source: {d.get('source_url')} (tier {d.get('source_tier')})." if d.get("source_url") else None,
    ])


def render_post_arrival(s: Dict[str, Any], corridor: str) -> str:
    fee = s.get("fee_eur")
    return _join([
        f"Post-arrival step {s.get('order')} for the {corridor} corridor: {s.get('name')}.",
        f"Deadline: {s['deadline_days_after_arrival']} days after arrival."
        if s.get("deadline_days_after_arrival") is not None else None,
        s.get("deadline_basis"),
        (f"Fee: EUR {fee:g}" + (f" ({s.get('fee_label')})" if s.get("fee_label") else "") + ".")
        if isinstance(fee, (int, float)) and fee else None,
        f"Where: {s.get('where')}." if s.get("where") else None,
        f"Source: {s.get('source_url')} (tier {s.get('source_tier')})." if s.get("source_url") else None,
    ])


# --- Chunk building ---------------------------------------------------------

def build_chunks(corpus: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the ordered list of chunk dicts for one corridor corpus.

    Each chunk: {chunk_id, source_ref, chunk_text, corridor, pathway_type, metadata}.
    `pathway_type` is None for corridor-wide chunks (overview, post-arrival, and
    documents whose visa_type is "any") so they match every pathway query.
    """
    c = corpus.get("corridor", {})
    cf, ct = c.get("from"), c.get("to")
    if not cf or not ct:
        raise ValueError("corpus.corridor.from / .to are required")
    corridor = corridor_key(cf, ct)
    slug = f"{cf}_{ct}".lower()

    chunks: List[Dict[str, Any]] = []

    def add(chunk_id: str, text_body: str, pathway_type: Optional[str], kind: str, extra: Dict[str, Any]):
        meta = {"corridor": corridor, "pathway_type": pathway_type, "kind": kind}
        meta.update({k: v for k, v in extra.items() if v is not None})
        chunks.append({
            "chunk_id": chunk_id,
            "source_ref": f"{IMMIGRATION_SOURCE_TYPE}.{chunk_id}",
            "chunk_text": text_body,
            "corridor": corridor,
            "pathway_type": pathway_type,
            "metadata": meta,
        })

    # 1) corridor overview (corridor-wide)
    add(f"{slug}_overview", render_overview(corpus, corridor), None, "overview",
        {"classification": c.get("classification")})

    # 2) pathways
    for p in corpus.get("pathways", []):
        vt = p.get("visa_type")
        if not vt:
            continue
        add(f"{slug}_pathway_{vt}", render_pathway(p, corridor), vt, "pathway",
            {"visa_type": vt, "source_url": p.get("source_url"), "source_tier": p.get("source_tier")})

    # 3) required documents
    for d in corpus.get("required_documents", []):
        vt = d.get("visa_type")
        did = d.get("id") or f"{slug}_doc_{d.get('document_type')}"
        pathway_type = None if (vt is None or vt == "any") else vt
        add(did, render_document(d, corridor), pathway_type, "document",
            {"visa_type": vt, "document_type": d.get("document_type"),
             "source_url": d.get("source_url"), "source_tier": d.get("source_tier")})

    # 4) post-arrival steps (corridor-wide)
    for s in corpus.get("post_arrival_steps", []):
        sid = s.get("id") or f"{slug}_postarrival_{s.get('order')}"
        add(sid, render_post_arrival(s, corridor), None, "post_arrival",
            {"source_url": s.get("source_url"), "source_tier": s.get("source_tier")})

    return chunks


# --- SQL emission -----------------------------------------------------------

def _quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _vector_literal(vec: List[float]) -> str:
    return "'[" + ",".join(f"{x:g}" for x in vec) + "]'"


def _chunk_row_id(source_ref: str) -> str:
    """Deterministic primary-key UUID per (corpus, source_ref) so re-runs and
    replays produce stable ids."""
    return str(uuid.uuid5(uuid.UUID(IMMIGRATION_CORPUS_COMPANY_ID), source_ref))


def build_sql(corpus_files: List[str], *, embedder: Optional[Embedder] = None,
              wrap_transaction: bool = False) -> str:
    embedder = embedder or get_default_embedder()
    parsed = [(f, json.load(open(f, encoding="utf-8"))) for f in corpus_files]

    lines: List[str] = []
    lines.append("-- P2-06e · Index corridor corpus → public.policy_assistant_chunks")
    lines.append("-- Generated by backend/scripts/index_corridor_corpus_chunks.py — do not hand-edit.")
    lines.append(f"-- embedder: {embedder.name}")
    if wrap_transaction:
        lines.append("BEGIN;")
    lines.append("")

    cid = IMMIGRATION_CORPUS_COMPANY_ID
    cols = ("id, company_id, policy_version_id, source_type, source_ref, "
            "chunk_text, chunk_metadata, embedding, created_at, updated_at")

    for path, corpus in parsed:
        chunks = build_chunks(corpus)
        corridor = chunks[0]["corridor"] if chunks else "?"
        texts = [c["chunk_text"] for c in chunks]
        embeddings = embedder.embed_batch(texts)

        lines.append(f"-- {corridor} : {len(chunks)} chunks from {path.split('/')[-1]}")
        lines.append(
            "DELETE FROM public.policy_assistant_chunks "
            f"WHERE company_id = {_quote(cid)}::uuid "
            f"AND source_type = {_quote(IMMIGRATION_SOURCE_TYPE)} "
            f"AND chunk_metadata->>'corridor' = {_quote(corridor)};"
        )
        lines.append(f"INSERT INTO public.policy_assistant_chunks ({cols}) VALUES")
        rows = []
        for ch, emb in zip(chunks, embeddings):
            rows.append(
                "  ("
                f"{_quote(_chunk_row_id(ch['source_ref']))}::uuid, "
                f"{_quote(cid)}::uuid, "
                "NULL, "
                f"{_quote(IMMIGRATION_SOURCE_TYPE)}, "
                f"{_quote(ch['source_ref'])}, "
                f"{_quote(ch['chunk_text'])}, "
                f"{_quote(json.dumps(ch['metadata'], ensure_ascii=False))}::jsonb, "
                f"{_vector_literal(emb)}::vector, "
                "now(), now()"
                ")"
            )
        lines.append(",\n".join(rows))
        lines.append(
            "ON CONFLICT (company_id, source_type, source_ref) DO UPDATE SET "
            "chunk_text = EXCLUDED.chunk_text, "
            "chunk_metadata = EXCLUDED.chunk_metadata, "
            "embedding = EXCLUDED.embedding, "
            "updated_at = now();"
        )
        lines.append("")

    if wrap_transaction:
        lines.append("COMMIT;")
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Index corridor corpus files into policy_assistant_chunks.")
    ap.add_argument("corpus_files", nargs="+", help="Paths to corridor corpus JSON files.")
    ap.add_argument("--emit-sql", action="store_true", help="Print the idempotent SQL to stdout.")
    ap.add_argument("--wrap-transaction", action="store_true",
                    help="Wrap output in BEGIN/COMMIT (for standalone psql -f runs).")
    args = ap.parse_args(argv)

    sql = build_sql(args.corpus_files, wrap_transaction=args.wrap_transaction)
    if args.emit_sql:
        print(sql)
    else:
        # Default: summarise without dumping the (large) SQL.
        for f in args.corpus_files:
            chunks = build_chunks(json.load(open(f, encoding="utf-8")))
            print(f"{f}: {len(chunks)} chunks ({chunks[0]['corridor']})", file=sys.stderr)
        print("Pass --emit-sql to print the SQL.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""[P3-02] Dossier suggestion service — RAG (retrieve → LLM suggest → structured).

Replaces the SERPAPI web-search path for dossier question suggestions with a
retrieval-augmented pipeline grounded in the synthetic immigration corpus:

  corridor + profile
    → retrieve top-k `policy_assistant_chunks` (source_type='immigration_rule')
      by corridor + pgvector cosine similarity
    → LLM (policy_assistant_llm_client, PII-masked) produces structured
      [{question_text, source_ids[], rationale}]
    → mapped to the dossier suggestion DTO shape.

Corpus covers 5 corridors (US→FR, IN→DE, FR→NO, UK→DE, BR→PT). For any other
corridor the retriever returns [] and this service returns [] gracefully (no
SERPAPI fallback — pure RAG per P3-02). No new tables; read-only access to
`policy_assistant_chunks` via the existing engine.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class DossierSuggestionUnavailable(RuntimeError):
    """[OBS-01] Raised when the dossier-suggestion LLM call fails (transport /
    provider outage, e.g. Anthropic credit exhaustion) — as opposed to a corridor
    with no corpus coverage, which is a legitimate empty result. The handler turns
    this into a `degraded` signal so a platform-wide LLM outage is observable
    instead of looking identical to 'this corridor has no coverage'."""

# policy_assistant_chunks stores corpus source_refs like
# `immigration_rule.us_fr_lsv_passport`; the corridor metadata uses a Unicode
# arrow + ISO2 (e.g. "US→FR").
_SOURCE_TYPE = "immigration_rule"
_SOURCE_REF_PREFIX = "immigration_rule."

# Light, self-contained country → ISO2 (covers the corpus corridors + ISO2
# pass-through) so this module stays dependency-light.
_COUNTRY_ISO2 = {
    "united states": "US", "usa": "US", "us": "US", "u.s.": "US", "u.s.a.": "US",
    "france": "FR", "fr": "FR",
    "india": "IN", "in": "IN",
    "germany": "DE", "de": "DE",
    "norway": "NO", "no": "NO",
    "united kingdom": "UK", "uk": "UK", "gb": "UK", "great britain": "UK",
    "brazil": "BR", "br": "BR",
    "portugal": "PT", "pt": "PT",
}


def _iso2(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    s = str(value).strip()
    hit = _COUNTRY_ISO2.get(s.lower())
    if hit:
        return hit
    return s.upper() if len(s) == 2 and s.isalpha() else None


def corridor_for_case(draft: Dict[str, Any]) -> Optional[str]:
    """Build the 'ORIGIN→DEST' corridor key (ISO2, Unicode arrow) from a case
    draft, or None when origin/destination can't be resolved."""
    basics = (draft or {}).get("relocationBasics") or {}
    origin = _iso2(basics.get("originCountry"))
    dest = _iso2(basics.get("destCountry"))
    if origin and dest:
        return f"{origin}→{dest}"
    return None


def retrieve_chunks(corridor: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Top-k `policy_assistant_chunks` for `corridor` by pgvector cosine.
    Best-effort: returns [] on no corpus / embedder unavailable / any failure."""
    try:
        from backend.app.services.policy_assistant_embedder import get_default_embedder
        from backend.database import db
        from sqlalchemy import text as sa_text

        q_emb = get_default_embedder().embed(query)
        q_vec = "[" + ",".join(f"{x:.6f}" for x in q_emb) + "]"
        sql = sa_text(
            "SELECT source_ref, chunk_text, chunk_metadata, "
            "  (embedding <=> CAST(:q AS vector)) AS distance "
            "FROM policy_assistant_chunks "
            "WHERE source_type = :src "
            "  AND chunk_metadata->>'corridor' = :corr "
            "  AND chunk_metadata->>'kind' NOT IN ('overview', 'pathway') "
            "ORDER BY embedding <=> CAST(:q AS vector) ASC "
            "LIMIT :k"
        )
        with db.engine.begin() as conn:
            rows = conn.execute(
                sql, {"q": q_vec, "src": _SOURCE_TYPE, "corr": corridor, "k": k}
            ).mappings().all()
    except Exception:
        log.warning("dossier RAG retrieval failed for corridor %s", corridor, exc_info=True)
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        ref = r["source_ref"] or ""
        meta = r["chunk_metadata"] or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        out.append({
            "chunk_id": ref.removeprefix(_SOURCE_REF_PREFIX),
            "text": r["chunk_text"],
            "source_url": meta.get("source_url"),
        })
    return out


_SUGGEST_TOOL = {
    "name": "suggest_dossier_questions",
    "description": (
        "Return dossier questions the employee should be ready to answer, grounded "
        "ONLY in the provided immigration facts. Cite the chunk_id(s) each question "
        "is based on."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_text": {"type": "string"},
                        "source_ids": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                    },
                    "required": ["question_text", "source_ids"],
                },
            }
        },
        "required": ["questions"],
    },
}

_SYSTEM = (
    "You help build a relocation dossier. Given immigration facts for a corridor, "
    "generate specific questions the employee should be ready to answer for their "
    "dossier. Ground every question ONLY in the provided facts and cite the "
    "chunk_id(s) it is based on. Do not invent requirements absent from the facts."
)


def _retrieval_query(profile: Dict[str, Any]) -> str:
    # Generic, non-PII topic string for retrieval (no user free-text in it).
    basics = (profile or {}).get("relocationBasics") or {}
    purpose = (basics.get("purpose") or "relocation").strip() or "relocation"
    return f"immigration documents and requirements for {purpose}"


def suggest_questions(
    corridor: Optional[str],
    profile: Dict[str, Any],
    *,
    max_questions: int = 5,
    client: Any = None,
) -> List[Dict[str, Any]]:
    """RAG dossier suggestions for a corridor. Returns a list of dicts shaped for
    DossierSuggestionDTO ({question_text, answer_type, sources}). [] when the
    corridor has no corpus coverage (graceful empty fallback).

    Raises DossierSuggestionUnavailable when the LLM call itself fails (provider /
    transport outage) — distinct from the empty-corpus case — so callers can
    surface a degraded state instead of a silent empty result ([OBS-01])."""
    if not corridor:
        return []
    chunks = retrieve_chunks(corridor, _retrieval_query(profile))
    if not chunks:
        return []

    facts = "\n\n".join(f"[{c['chunk_id']}] {c['text']}" for c in chunks)
    user_message = (
        f"Corridor: {corridor}\n\n"
        f"Immigration facts:\n{facts}\n\n"
        f"Generate up to {max_questions} specific dossier questions, each citing the "
        f"chunk_id(s) it is based on."
    )

    # The policy-assistant client masks PII in user_message before egress and
    # returns the forced tool's structured input under `tool_use`.
    from backend.app.services.policy_assistant_llm_client import LlmRequest, get_default_client

    cli = client or get_default_client()
    req = LlmRequest(
        system=_SYSTEM,
        user_message=user_message,
        tools=[_SUGGEST_TOOL],
        tool_choice={"type": "tool", "name": "suggest_dossier_questions"},
        max_tokens=900,
    )
    try:
        result = cli.complete(req)
    except Exception as exc:
        # [OBS-01] A failure here is an LLM/transport outage, NOT a covered-but-empty
        # corridor (the corpus was retrieved fine above). Log at ERROR so it alerts,
        # and raise so the handler can surface a `degraded` signal instead of an
        # indistinguishable empty 200.
        log.error(
            "dossier suggest LLM failed for corridor %s (degraded)", corridor, exc_info=True
        )
        raise DossierSuggestionUnavailable(corridor) from exc

    tool = result.get("tool_use") if isinstance(result, dict) else None
    questions = tool.get("questions") if isinstance(tool, dict) else None
    if not isinstance(questions, list):
        return []

    by_id = {c["chunk_id"]: c for c in chunks}
    out: List[Dict[str, Any]] = []
    for q in questions[:max_questions]:
        if not isinstance(q, dict):
            continue
        qt = (q.get("question_text") or "").strip()
        if not qt:
            continue
        source_ids = [s for s in (q.get("source_ids") or []) if isinstance(s, str)]
        sources = [
            {"chunk_id": sid, "url": by_id[sid].get("source_url")}
            for sid in source_ids
            if sid in by_id
        ]
        out.append({"question_text": qt, "answer_type": "text", "sources": sources})
    return out

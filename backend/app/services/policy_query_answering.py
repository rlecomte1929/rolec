"""
Company-scoped canonical policy retrieval and query answering with citations.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text

from ...database import Database
from .llm_client import complete_text_sync

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "have",
    "i",
    "if",
    "in",
    "is",
    "me",
    "my",
    "of",
    "or",
    "the",
    "to",
    "what",
    "with",
}


def redact_pii_from_query(query: str) -> str:
    # GDPR Art. 28/44 (SEC-03): delegate to the canonical mask_pii so the query
    # is scrubbed of IBAN/passport/SSN/national-ID/name too — the previous
    # bespoke regex only caught email/phone/loose-ID and let those through to
    # the OpenAI retrieval + answer call. mask_pii is the mandated masker.
    from .pii_masker import mask_pii

    return mask_pii(query)


def _tokens(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9_]+", text.lower())
        if token not in STOPWORDS and len(token) > 1
    ]


def _score_text(query_tokens: Sequence[str], text: str) -> int:
    haystack = set(_tokens(text))
    return sum(3 if token in haystack else 0 for token in query_tokens)


def retrieve_company_scoped_policy_chunks(
    db: Database,
    *,
    company_id: str,
    query: str,
    canonical_policy_document_id: Optional[str] = None,
    top_k: int = 5,
    tier: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retrieve top-K policy chunks + related facts for a company.

    [P5-9 C1] The ``tier`` kwarg enforces tier isolation on facts:
      - ``tier=None``  → no tier filter (admin/HR path)
      - ``tier="X"``   → only facts where ``tier IS NULL OR tier = 'X'``
                         are returned, so a Manager-tier user cannot
                         retrieve Executive-tier benefit values via the
                         assistant.

    Chunks themselves are NOT tier-filtered yet — the canonical chunks
    table has no ``tier`` column. That's an acceptable scope: chunks
    carry section text (no specific benefit values); the sensitive
    per-tier numbers live in ``canonical_policy_facts`` which IS now
    filtered. The chunk-side filter is a follow-up that requires a
    second schema change.
    """
    document = (
        db.get_canonical_policy_document(canonical_policy_document_id)
        if canonical_policy_document_id
        else db.get_active_canonical_policy_document_for_company(company_id)
    )
    if not document or str(document.get("company_id") or "") != str(company_id):
        raise RuntimeError("no_company_scoped_policy_document")

    chunks = db.list_canonical_policy_document_chunks(str(document["id"]), company_id=company_id)
    facts = db.list_canonical_policy_facts(
        str(document["id"]),
        company_id=company_id,
        tier=tier,
    )
    query_tokens = _tokens(query)
    scored_chunks: List[Tuple[int, Dict[str, Any]]] = []
    for chunk in chunks:
        text = str(chunk.get("text_content") or "")
        score = _score_text(query_tokens, text)
        if score > 0:
            scored_chunks.append((score, chunk))
    scored_chunks.sort(key=lambda item: (-item[0], item[1].get("chunk_index", 0)))
    top_chunks = [chunk for _score, chunk in scored_chunks[:top_k]]
    if not top_chunks and chunks:
        top_chunks = chunks[: min(top_k, len(chunks))]

    top_chunk_ids = {str(chunk["id"]) for chunk in top_chunks}
    related_facts = [
        fact for fact in facts if str(fact.get("canonical_policy_document_chunk_id") or "") in top_chunk_ids
    ]
    if not related_facts and facts:
        related_facts = facts[: min(top_k, len(facts))]
    return document, top_chunks, related_facts


def _citation_for_chunk(chunk: Dict[str, Any], idx: int) -> str:
    section = str(chunk.get("section_path") or chunk.get("structure_type") or "section")
    return f"[{idx}] chunk `{chunk['id']}` ({section})"


def _fallback_answer(
    query: str,
    document: Dict[str, Any],
    chunks: List[Dict[str, Any]],
    facts: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    citations = [_citation_for_chunk(chunk, idx + 1) for idx, chunk in enumerate(chunks)]
    if facts:
        lines = [
            f"According to your company policy **{document.get('title') or document.get('filename') or document.get('id')}**, here is the relevant guidance:"
        ]
        for idx, fact in enumerate(facts[:3], start=1):
            desc = str(fact.get("title") or fact.get("description") or fact.get("benefit_category") or "Policy fact")
            if fact.get("amount") is not None:
                value = f"{fact.get('currency') or ''} {fact.get('amount')}".strip()
            elif fact.get("percentage") is not None:
                value = f"{fact.get('percentage')}%"
            elif fact.get("value_text"):
                value = str(fact.get("value_text"))
            else:
                value = "See cited policy text"
            lines.append(f"{idx}. {desc}: {value} {citations[idx - 1] if idx - 1 < len(citations) else ''}".strip())
        return "\n".join(lines), citations
    if chunks:
        return (
            "I could only find the following directly relevant policy text, so I’m answering conservatively from that context:\n"
            + "\n".join(f"- {_citation_for_chunk(chunk, idx + 1)}: {str(chunk.get('text_content') or '')[:220]}" for idx, chunk in enumerate(chunks[:3])),
            citations,
        )
    # [P5-9 C2] Do NOT echo the user's query back here. The previous
    # version included `Query reviewed: {query[:120]}` which leaked the
    # first 120 chars of the user's question into backend logs and any
    # APM tracing that captured response bodies (passport numbers,
    # IBANs, etc.). Generic message keeps the surface clean.
    return (
        "I could not find support for this question in your company’s current policy document. "
        "Please contact your HR team for clarification.",
        [],
    )


class CanonicalPolicyQueryLLM:
    def __init__(self, *, client: Any = None, model: Optional[str] = None) -> None:
        self._client = client
        self._model = model or os.getenv("OPENAI_POLICY_QUERY_MODEL", "gpt-4.1-mini")

    def answer(self, *, query: str, context_blocks: List[str]) -> str:
        # AIQ-401: prod routes through llm_client.complete_text_sync (timeout +
        # 429/5xx retry + structured logging). A test-injected `client` takes
        # precedence (testing seam). The egress kill-switch applies on the prod
        # path only; an injected client has opted into that client. Free-text
        # (no json_object) — the answer is prose with [n] citations.
        from ...core.llm_flags import policy_llm_disabled, policy_llm_temperature

        if self._client is None and policy_llm_disabled():
            # Deterministic short-circuit. Caller treats "" as "no LLM answer"
            # and routes to a template-based deterministic response.
            return ""

        system = (
            "Answer strictly from the provided policy context. "
            "Do not use outside knowledge. "
            "If the answer is not fully supported, say so clearly. "
            "Cite every material statement using the provided numbered citations like [1], [2]."
        )
        user = json.dumps({"query": query, "context": context_blocks})
        temperature = policy_llm_temperature()

        if self._client is not None:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content if response.choices else ""

        return complete_text_sync(
            system=system,
            user=user,
            model=self._model,
            temperature=temperature,
            timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
        )


def _resolve_caller_tier(db: Database, *, user_id: str, user_role: str) -> Optional[str]:
    """[P5-9 C1] Look up the caller's current active tier from
    ``employee_tiers`` so the retrieval path can enforce tier isolation.

    Returns:
      - tier name (e.g. "Manager") for an employee with an active row
      - None for HR/admin (they see all tiers) OR for an employee with
        no active assignment (treat as universal — they only see facts
        with tier IS NULL, never tier-specific ones)

    Notes:
      - HR and admin intentionally bypass the filter because they
        configure policies for every tier; their use case requires
        the full set.
      - Employees with no active tier get the safest possible default:
        only universal facts. They can't escalate, but they also can't
        see manager-only or executive-only content until HR assigns them.
    """
    role = (user_role or "").lower()
    if role in ("hr", "admin"):
        return None
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT tier_name FROM employee_tiers "
                    "WHERE employee_id = :uid AND end_date IS NULL "
                    "LIMIT 1"
                ),
                {"uid": user_id},
            ).mappings().first()
    except Exception:
        # Defensive: if employee_tiers lookup fails we MUST fall back
        # to the strictest default (universal-only). Any other branch
        # would risk leaking tier content on a transient DB error.
        return "__NO_TIER__"
    if row and row.get("tier_name"):
        return str(row["tier_name"])
    # Employee exists but no active tier → strict default.
    return "__NO_TIER__"


def _hash_question(query: str) -> str:
    """SHA-256 of the lowercased + whitespace-stripped question.

    Same canonicalisation as the policy_feedback client (commit 92fb641)
    so the hash is comparable across retrieval audit + HR review queue.
    """
    canonical = " ".join((query or "").lower().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _audit_log_table_name(db: Database) -> str:
    """`public.audit_log` on Postgres, bare `audit_log` on sqlite (tests)."""
    try:
        return "public.audit_log" if db.engine.dialect.name == "postgresql" else "audit_log"
    except Exception:
        return "public.audit_log"


def _write_policy_query_audit_log(
    db: Database,
    *,
    actor_user_id: str,
    session_id: str,
    company_id: str,
    question_hash: str,
    chunk_ids: List[str],
) -> None:
    """[P5-9 H2] Append a row to public.audit_log for each retrieval.

    Hard contract: NO raw question text in the audit row — only the
    SHA-256 question_hash. Failures are swallowed (logged) so a
    retrieval never fails because audit_log is unavailable.
    """
    try:
        table = _audit_log_table_name(db)
        metadata = {
            "company_id": company_id,
            "question_hash": question_hash,
            "chunk_ids": list(chunk_ids),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {table} "
                    f"  (id, actor_user_id, action_type, target_type, target_id, "
                    f"   metadata_json, created_at) "
                    f"VALUES (:id, :actor, 'policy.queried', 'policy_assistant', "
                    f"        :target, :meta, :now)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "actor": actor_user_id,
                    "target": session_id,
                    "meta": json.dumps(metadata),
                    "now": datetime.now(timezone.utc).isoformat(),
                },
            )
    except Exception:
        logger.warning(
            "policy_query: audit_log write failed actor=%s session=%s",
            actor_user_id,
            session_id,
            exc_info=True,
        )


def answer_company_scoped_policy_query(
    db: Database,
    *,
    company_id: str,
    user_id: str,
    user_role: str,
    query: str,
    canonical_policy_document_id: Optional[str] = None,
    llm: Optional[CanonicalPolicyQueryLLM] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    redacted_query = redact_pii_from_query(query)
    # [P5-9 C1] Resolve caller's tier before retrieval. HR/admin → None
    # (no filter). Employees without an active tier → "__NO_TIER__"
    # which matches no real tier name, so only universal (NULL) facts
    # come back.
    caller_tier = _resolve_caller_tier(db, user_id=user_id, user_role=user_role)
    document, chunks, facts = retrieve_company_scoped_policy_chunks(
        db,
        company_id=company_id,
        query=redacted_query,
        canonical_policy_document_id=canonical_policy_document_id,
        tier=caller_tier,
    )
    context_blocks = [
        f"[{idx + 1}] chunk_id={chunk['id']} section={chunk.get('section_path') or chunk.get('structure_type')}: {chunk.get('text_content')}"
        for idx, chunk in enumerate(chunks)
    ]
    citation_labels = [_citation_for_chunk(chunk, idx + 1) for idx, chunk in enumerate(chunks)]
    citations = [str(chunk["id"]) for chunk in chunks]
    use_llm = bool(llm) or bool(os.getenv("OPENAI_API_KEY"))
    if use_llm:
        llm_client = llm or CanonicalPolicyQueryLLM()
        answer = llm_client.answer(query=redacted_query, context_blocks=context_blocks).strip()
        if not answer:
            answer, _ = _fallback_answer(redacted_query, document, chunks, facts)
    else:
        answer, _ = _fallback_answer(redacted_query, document, chunks, facts)

    db.insert_canonical_policy_query_audit_log(
        company_id=company_id,
        user_id=user_id,
        user_role=user_role,
        canonical_policy_document_id=str(document["id"]),
        query_text=query,
        redacted_query_text=redacted_query,
        retrieved_chunk_ids=citations,
        answer_preview=answer[:280],
    )

    # [P5-9 H2] Compliance audit row in the cross-cutting audit_log table.
    # Hash the original (un-redacted) question — the hash is one-way and
    # carries no PII; the redacted_query_text only matters for the
    # domain-specific audit table above.
    resolved_session_id = session_id or str(uuid.uuid4())
    question_hash = _hash_question(query)
    _write_policy_query_audit_log(
        db,
        actor_user_id=user_id,
        session_id=resolved_session_id,
        company_id=company_id,
        question_hash=question_hash,
        chunk_ids=citations,
    )

    return {
        "company_id": company_id,
        "canonical_policy_document_id": str(document["id"]),
        "answer": answer,
        "citations": citation_labels,
        "retrieved_chunk_ids": citations,
        "session_id": resolved_session_id,
    }

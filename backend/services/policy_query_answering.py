"""
Company-scoped canonical policy retrieval and query answering with citations.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..database import Database

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
    out = re.sub(r"\b[\w.+-]+@[\w.-]+\.\w+\b", "[REDACTED_EMAIL]", query)
    out = re.sub(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b", "[REDACTED_PHONE]", out)
    out = re.sub(r"\b[A-Z]{1,2}\d{5,}\b", "[REDACTED_ID]", out)
    return out


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
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    document = (
        db.get_canonical_policy_document(canonical_policy_document_id)
        if canonical_policy_document_id
        else db.get_active_canonical_policy_document_for_company(company_id)
    )
    if not document or str(document.get("company_id") or "") != str(company_id):
        raise RuntimeError("no_company_scoped_policy_document")

    chunks = db.list_canonical_policy_document_chunks(str(document["id"]), company_id=company_id)
    facts = db.list_canonical_policy_facts(str(document["id"]), company_id=company_id)
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
    return (
        f"I could not find support for this question in your company’s current policy document. Query reviewed: {query[:120]}",
        [],
    )


class CanonicalPolicyQueryLLM:
    def __init__(self, *, client: Any = None, model: Optional[str] = None) -> None:
        self._client = client
        self._model = model or os.getenv("OPENAI_POLICY_QUERY_MODEL", "gpt-4.1-mini")

    def _client_or_raise(self) -> Any:
        if self._client is not None:
            return self._client
        from ..core.llm_flags import LLMDisabled, policy_llm_disabled
        if policy_llm_disabled():
            # RELOPASS_POLICY_LLM_DISABLED=1 — never build a client, never egress.
            return LLMDisabled
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for policy query answering") from exc
        # Explicit timeout + retries — avoids hung requests blocking policy Q&A.
        timeout_s = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
        max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=timeout_s,
            max_retries=max_retries,
        )

    def answer(self, *, query: str, context_blocks: List[str]) -> str:
        from ..core.llm_flags import LLMDisabled, policy_llm_temperature
        client = self._client_or_raise()
        if client is LLMDisabled:
            # Deterministic short-circuit. Caller is expected to treat an
            # empty string as "no LLM answer" and route to a template-based
            # deterministic response (or set review_required=True).
            return ""
        system = (
            "Answer strictly from the provided policy context. "
            "Do not use outside knowledge. "
            "If the answer is not fully supported, say so clearly. "
            "Cite every material statement using the provided numbered citations like [1], [2]."
        )
        response = client.chat.completions.create(
            model=self._model,
            temperature=policy_llm_temperature(),
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps({"query": query, "context": context_blocks}),
                },
            ],
        )
        return response.choices[0].message.content if response.choices else ""


def answer_company_scoped_policy_query(
    db: Database,
    *,
    company_id: str,
    user_id: str,
    user_role: str,
    query: str,
    canonical_policy_document_id: Optional[str] = None,
    llm: Optional[CanonicalPolicyQueryLLM] = None,
) -> Dict[str, Any]:
    redacted_query = redact_pii_from_query(query)
    document, chunks, facts = retrieve_company_scoped_policy_chunks(
        db,
        company_id=company_id,
        query=redacted_query,
        canonical_policy_document_id=canonical_policy_document_id,
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
    return {
        "company_id": company_id,
        "canonical_policy_document_id": str(document["id"]),
        "answer": answer,
        "citations": citation_labels,
        "retrieved_chunk_ids": citations,
    }

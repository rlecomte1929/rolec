"""E-PIPE-5b · Fuzzy-match helpers for the C1-07 entity resolver (Stages 3–4).

Two AI-backed pieces the deterministic v1 (SupabaseCanonicalStore, #620) left as
stubs:

  - ``embed_person_768`` — an OpenAI ``text-embedding-3-small`` (768-dim) embedding
    of a person's identity, stored on the canonical entity so pgvector ANN
    (Stage 3, ``SupabaseCanonicalStore.ann_search``) can find near-duplicates
    (name typos / ICAO transliteration variants) across documents.
  - ``OpenAILLMResolver`` — the C1-07P prompt wrapper (Stage 4), consulted only for
    the 0.80–0.92 cosine band to decide whether a candidate is the same person as
    one of the ANN hits.

Both **degrade to a no-op when ``OPENAI_API_KEY`` is unset** (embedding → ``None``
so the resolver skips ANN+LLM and stays deterministic; resolver → no-match verdict),
so the pipeline keeps working until the key is provisioned.

GDPR: identity text is passed through ``mask_pii`` before the vendor call (strips any
incidental IDs); names/dob are inherently sent for matching — that is the resolver's
purpose, mirroring the GPT-4o passport path. The sync OpenAI client is used directly
(``llm_client.complete`` is async and the resolver Protocol is sync) — the same
documented exception OpenAIEmbedder relies on. Never log the identity text.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Sequence

from backend.relopass.agents.entity_resolution import (
    AnnHit,
    ExtractedPerson,
    LLMResolverVerdict,
)

log = logging.getLogger(__name__)

_EMBED_MODEL = "text-embedding-3-small"
_EMBED_DIM = 768  # matches rce.canonical_entities.embedding vector(768)
_LLM_MODEL = "gpt-4o-mini"


def _identity_text(p: "ExtractedPerson | object") -> str:
    parts = [
        getattr(p, "surname_main", None),
        getattr(p, "given_names_main", None),
        getattr(p, "dob_iso", None),
        getattr(p, "nationality_iso3", None),
    ]
    return " ".join(str(x) for x in parts if x)


def _openai_client():
    """Return a sync OpenAI client, or None if key/package is unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
    except ImportError:
        log.warning("openai package not installed — rce entity AI disabled")
        return None
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def embed_person_768(person: ExtractedPerson) -> Optional[List[float]]:
    """768-dim identity embedding for ANN matching, or None when AI is disabled.

    Returns None (not an exception) when OPENAI_API_KEY is unset or the call fails,
    so resolve_and_link can attach ``embedding=None`` and the resolver stays on its
    deterministic stages — no regression vs. v1.
    """
    client = _openai_client()
    if client is None:
        log.info("OPENAI_API_KEY unset — entity embeddings disabled (resolver stays deterministic)")
        return None
    from .pii_masker import mask_pii

    text_in = mask_pii(_identity_text(person)) or " "
    try:
        resp = client.embeddings.create(model=_EMBED_MODEL, input=[text_in], dimensions=_EMBED_DIM)
        return list(resp.data[0].embedding)
    except Exception as exc:  # fail-soft — degrade to deterministic resolution
        log.warning("rce entity embedding failed (%s) — proceeding without embedding", type(exc).__name__)
        return None


_SYSTEM_PROMPT = (
    "You are an entity-resolution adjudicator for immigration case documents. "
    "You are given one candidate person extracted from a document and a short list "
    "of existing canonical persons that an approximate-nearest-neighbour search "
    "flagged as possibly the same individual. Decide whether the candidate is the "
    "SAME real person as one of the canonicals (e.g. a transliteration or spelling "
    "variant of the same name with a compatible date of birth and nationality), or "
    "a different person. Return the canonical_entity_id of the match, or null if "
    "none is clearly the same person. Be conservative: only match when confident."
)

_VERDICT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "match": {"type": ["string", "null"], "description": "canonical_entity_id of the match, or null"},
        "confidence": {"type": "number", "description": "0.0–1.0 confidence in the match decision"},
        "reasoning": {"type": "string", "description": "one short sentence of justification"},
    },
    "required": ["match", "confidence", "reasoning"],
}


def _candidate_payload(person: ExtractedPerson) -> dict:
    from .pii_masker import mask_pii

    return {
        "surname": mask_pii(person.surname_main or ""),
        "given_names": mask_pii(person.given_names_main or ""),
        "date_of_birth": person.dob_iso,
        "nationality": person.nationality_iso3,
    }


def _hit_payload(hit: AnnHit) -> dict:
    from .pii_masker import mask_pii

    c = hit.canonical
    return {
        "canonical_entity_id": hit.canonical_entity_id,
        "cosine_sim": round(hit.cosine_sim, 4),
        "surname": mask_pii(c.surname_main or ""),
        "given_names": mask_pii(c.given_names_main or ""),
        "date_of_birth": c.dob_iso,
        "nationality": c.nationality_iso3,
    }


class OpenAILLMResolver:
    """C1-07P prompt wrapper (Stage 4). Sync, fail-soft: a no-match verdict when AI
    is disabled or the call fails, so the resolver creates a new canonical instead."""

    def resolve(self, candidate: ExtractedPerson, top_hits: Sequence[AnnHit]) -> LLMResolverVerdict:
        client = _openai_client()
        if client is None or not top_hits:
            return LLMResolverVerdict(match=None, confidence=0.0, reasoning="LLM resolver disabled")
        user = json.dumps(
            {"candidate": _candidate_payload(candidate), "canonicals": [_hit_payload(h) for h in top_hits]}
        )
        try:
            resp = client.chat.completions.create(
                model=_LLM_MODEL,
                messages=[{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "entity_resolution_verdict", "strict": True, "schema": _VERDICT_SCHEMA},
                },
            )
            data = json.loads(resp.choices[0].message.content)
            match = data.get("match")
            # Defense-in-depth: the returned id becomes rce.entity_links.canonical_entity_id,
            # and the candidate/hit fields are derived from uploaded-document content (attacker-
            # influenceable). Trust `match` only if it is one of the canonicals we actually
            # offered this call — never an arbitrary/hallucinated/cross-case id. Otherwise treat
            # as no-match so the resolver creates a fresh canonical instead.
            offered = {h.canonical_entity_id for h in top_hits}
            if match is not None and match not in offered:
                log.warning("rce LLM resolver returned an unoffered match id — treating as no-match")
                return LLMResolverVerdict(match=None, confidence=0.0, reasoning="match not in offered slate")
            return LLMResolverVerdict(
                match=match,
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning"),
            )
        except Exception as exc:  # fail-soft
            log.warning("rce LLM entity resolver failed (%s) — treating as no-match", type(exc).__name__)
            return LLMResolverVerdict(match=None, confidence=0.0, reasoning="resolver error")

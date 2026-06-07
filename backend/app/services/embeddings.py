"""
Embeddings abstraction layer (AI-I.4a / AIQ-621).

This is the canonical entry point for obtaining an embeddings client. It
decouples caller code from the concrete embedding model so the BGE-M3 vs
Cohere v3 decision (AI-W1.2 / AIQ-572) becomes a config swap rather than a
refactor of every call site.

Usage:

    from backend.app.services.embeddings import get_embeddings_client

    client = get_embeddings_client()          # model from env / legacy default
    vecs = client.embed_batch(["chunk a", "chunk b"])

The protocol (`EmbeddingsClient`) and the existing concrete implementations
(`HashEmbedder`, `OpenAIEmbedder`) currently live in
`policy_assistant_embedder.py`. This module re-exports them unchanged so the
~11 existing importers keep working, and layers a model-selection registry on
top. When AI-W1.2 lands, the chosen model's adapter is added to `_REGISTRY`
below and selected via the `EMBEDDINGS_MODEL` env var — no caller changes.

Model selection (highest precedence first):
  1. explicit `model=` argument to get_embeddings_client()
  2. EMBEDDINGS_MODEL env var
  3. legacy behaviour: OPENAI_API_KEY present -> OpenAI, else Hash
     (delegated to policy_assistant_embedder.get_default_embedder)
"""
from __future__ import annotations

import os
from typing import Callable, Dict, Optional

# Re-export the protocol + implementations from the existing module so this
# file is a true drop-in superset: callers can switch their import to
# `embeddings` with no other change.
from .policy_assistant_embedder import (  # noqa: F401  (re-exported)
    EMBEDDING_DIM,
    Embedder,
    HashEmbedder,
    OpenAIEmbedder,
    cosine_similarity,
    get_default_embedder,
)

# Canonical name for the embeddings interface going forward. Identical shape to
# `Embedder` (name / embed / embed_batch); aliased so new code can depend on the
# stable `EmbeddingsClient` name while legacy importers keep using `Embedder`.
EmbeddingsClient = Embedder

# Concrete adapters keyed by model identifier. New models (BGE-M3, Cohere v3)
# register here once AI-W1.2 decides — that is the "config swap" the abstraction
# exists to enable.
_REGISTRY: Dict[str, Callable[[], EmbeddingsClient]] = {
    "hash": HashEmbedder,
    "openai": OpenAIEmbedder,
    "text-embedding-3-small": OpenAIEmbedder,
}

# Models that are planned but whose adapter has not landed yet. Selecting one of
# these fails loudly with a pointer to the deciding task, rather than silently
# falling back to the wrong model and poisoning the corpus.
_PENDING_MODELS = {
    "bge-m3": "AI-W1.2 (AIQ-572) — BGE-M3 self-host adapter not yet built",
    "cohere-v3": "AI-W1.2 (AIQ-572) — Cohere v3 (Bedrock) adapter not yet built",
    "cohere": "AI-W1.2 (AIQ-572) — Cohere v3 (Bedrock) adapter not yet built",
}


def get_embeddings_client(model: Optional[str] = None) -> EmbeddingsClient:
    """
    Return an EmbeddingsClient for the requested (or configured) model.

    Args:
        model: explicit model id. If None, falls back to the EMBEDDINGS_MODEL
            env var, then to the legacy OPENAI_API_KEY-based default.

    Raises:
        NotImplementedError: a planned model (e.g. bge-m3, cohere-v3) was
            requested but its adapter is still pending AI-W1.2.
        ValueError: an unknown model id was requested.
    """
    requested = (model or os.environ.get("EMBEDDINGS_MODEL") or "").strip().lower()

    # No explicit selection -> preserve the existing env-driven default so
    # nothing changes for current call sites.
    if not requested:
        return get_default_embedder()

    if requested in _PENDING_MODELS:
        raise NotImplementedError(
            f"Embedding model '{requested}' is not available yet: "
            f"{_PENDING_MODELS[requested]}. Set EMBEDDINGS_MODEL to a supported "
            f"model {sorted(_REGISTRY)} or leave it unset for the default."
        )

    factory = _REGISTRY.get(requested)
    if factory is None:
        raise ValueError(
            f"Unknown embedding model '{requested}'. Supported: {sorted(_REGISTRY)}; "
            f"pending (AI-W1.2): {sorted(_PENDING_MODELS)}."
        )
    return factory()


__all__ = [
    "EMBEDDING_DIM",
    "Embedder",
    "EmbeddingsClient",
    "HashEmbedder",
    "OpenAIEmbedder",
    "cosine_similarity",
    "get_default_embedder",
    "get_embeddings_client",
]

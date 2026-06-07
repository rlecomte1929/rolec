"""
Policy Assistant RAG (Sprint A): embedding abstraction.

Two implementations:

  - HashEmbedder: deterministic, no API key, useful for tests and dev.
    Hashes tokens into a fixed-size vector. Same input -> same vector;
    overlapping inputs -> more similar vectors. Not semantic, but fine
    for "retrieval picks the right chunk" unit tests.

  - OpenAIEmbedder: real semantic embeddings via OpenAI text-embedding-
    3-small. Used in production. Requires OPENAI_API_KEY env var.

Selection via OPENAI_API_KEY presence + POLICY_ASSISTANT_EMBEDDER env
var. Default behavior:

  - OPENAI_API_KEY set AND POLICY_ASSISTANT_EMBEDDER=openai (or unset)
    -> OpenAIEmbedder
  - Otherwise -> HashEmbedder

Both produce 1536-dim vectors so the same DB column works for either.
The hash embedder pads its 128-dim hash output to 1536 with zeros.

Cost: HashEmbedder is free. OpenAIEmbedder runs at $0.02 per 1M tokens
(text-embedding-3-small price as of 2026-04). A typical company policy
indexes to ~50 chunks of ~150 tokens each = 7,500 tokens = $0.00015
per full reindex. Negligible at expected pilot volume.

llm_client wrapper exception (AUDIT-B5-followup / AIQ-401)
---------------------------------------------------------
``OpenAIEmbedder`` constructs the OpenAI SDK client directly instead of
going through ``services/llm_client.py``. This is a *documented, allowed*
exception: ``llm_client`` only wraps chat/messages completions (``complete`` /
``claude_complete``) and has no embeddings entry point. The embeddings API
(``client.embeddings.create``) returns vectors, not chat text, so the
wrapper's JSON-schema / retry-on-completion machinery does not apply. If a
shared embeddings wrapper is ever added, migrate this call site to it.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import List, Protocol

log = logging.getLogger(__name__)

EMBEDDING_DIM = 1536


class Embedder(Protocol):
    """Embedder interface. Implementations must produce EMBEDDING_DIM
    floats per text. Implementations should be deterministic for the
    same input within a single deploy (caching benefits)."""

    name: str

    def embed(self, text: str) -> List[float]: ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]: ...


# --- HashEmbedder -----------------------------------------------------------

class HashEmbedder:
    """
    Deterministic, no-API-key embedder. Hashes lower-cased word tokens
    into a 128-dim hash space, then zero-pads to EMBEDDING_DIM. Vectors
    are L2-normalized so cosine similarity behaves sensibly.

    Use for tests and local dev. Production uses OpenAI.
    """

    name = "hash"
    HASH_DIMS = 128

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.HASH_DIMS
        for token in self._tokenize(text):
            h = hashlib.md5(token.encode("utf-8")).digest()
            # Use bytes 0..3 for index, byte 4 for sign.
            idx = int.from_bytes(h[0:4], "big") % self.HASH_DIMS
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            vec[idx] += sign
        # L2 normalize so cosine similarity is comparable across texts
        # of different lengths.
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        # Pad to EMBEDDING_DIM with zeros so the same DB column shape
        # works for both embedders.
        return vec + [0.0] * (EMBEDDING_DIM - self.HASH_DIMS)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # Simple lower-case word split. Drop tokens shorter than 2 chars.
        words = []
        cur = []
        for ch in (text or "").lower():
            if ch.isalnum():
                cur.append(ch)
            else:
                if len(cur) >= 2:
                    words.append("".join(cur))
                cur = []
        if len(cur) >= 2:
            words.append("".join(cur))
        return words


# --- OpenAIEmbedder ---------------------------------------------------------

class OpenAIEmbedder:
    """
    Real semantic embeddings via OpenAI text-embedding-3-small.
    Returns 1536-dim float vectors. Lazy-imports openai so the test
    environment doesn't need the package installed.
    """

    name = "openai-text-embedding-3-small"
    MODEL = "text-embedding-3-small"

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set; cannot use OpenAIEmbedder")
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai package not installed; pip install openai or fall back to HashEmbedder"
            )
        self._client = OpenAI(api_key=api_key)

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # Strip empties to avoid an OpenAI 400; refill with zero vectors
        # so caller's index alignment stays correct.
        cleaned = [t if (t and t.strip()) else " " for t in texts]
        resp = self._client.embeddings.create(model=self.MODEL, input=cleaned)
        return [d.embedding for d in resp.data]


# --- Factory ---------------------------------------------------------------

def get_default_embedder() -> Embedder:
    """
    Pick an embedder based on environment.

    POLICY_ASSISTANT_EMBEDDER overrides everything:
      - 'hash'   -> HashEmbedder (forces hash even if OPENAI_API_KEY is set)
      - 'openai' -> OpenAIEmbedder (errors at construct time if no key)

    Without the override:
      - OPENAI_API_KEY present -> OpenAIEmbedder
      - Otherwise               -> HashEmbedder
    """
    forced = (os.environ.get("POLICY_ASSISTANT_EMBEDDER") or "").strip().lower()
    if forced == "hash":
        return HashEmbedder()
    if forced == "openai":
        return OpenAIEmbedder()
    if os.environ.get("OPENAI_API_KEY"):
        try:
            return OpenAIEmbedder()
        except Exception as e:
            log.warning(
                "OpenAIEmbedder unavailable (%s); falling back to HashEmbedder.", e
            )
            return HashEmbedder()
    return HashEmbedder()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Pure-Python cosine similarity. Used by SQLite retrieval path
    where pgvector isn't available."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

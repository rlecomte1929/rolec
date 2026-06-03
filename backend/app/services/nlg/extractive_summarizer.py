"""Extractive summarisation — TextRank over TF-IDF sentence similarity.

Parker NLG approach #7 (extractive). Picks the most central sentences from a
long document (e.g. a 40-page policy) to form a TL;DR. No LLM call: pure Python
plus numpy for the PageRank power-iteration. Deterministic — identical input
yields identical bytes — and runs on CPU with no PII leaving the process.

Implementation note: the original audit sketch named networkx for the graph.
networkx is not an installed dependency and TextRank needs only a single
PageRank pass over one similarity matrix, so this uses a ~15-line numpy
power-iteration instead — no new dependency. See PLAN.md deviation #1.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List

import numpy as np

# Lightweight English stopword set — enough to keep TF-IDF from being dominated
# by function words without pulling in an NLP package.
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or
    that the their there to was were will with this these those they your you
    we our us i he she his her them then than but not no if so such can may
    must shall should would could been being do does did done about above
    below over under between each any all more most other some only own same
    very which who whom whose when where why how""".split()
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")


def _split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT.split(cleaned)
    return [p.strip() for p in parts if p.strip()]


def _tokenise(sentence: str) -> List[str]:
    return [
        w
        for w in (m.group(0).lower() for m in _WORD.finditer(sentence))
        if w not in _STOPWORDS and len(w) > 1
    ]


def _tfidf_vectors(sentences: List[str]) -> List[Dict[str, float]]:
    tokenised = [_tokenise(s) for s in sentences]
    n = len(tokenised)
    df: Counter = Counter()
    for toks in tokenised:
        for term in set(toks):
            df[term] += 1
    vectors: List[Dict[str, float]] = []
    for toks in tokenised:
        tf = Counter(toks)
        length = len(toks) or 1
        vec: Dict[str, float] = {}
        for term, count in tf.items():
            idf = math.log((1 + n) / (1 + df[term])) + 1.0
            vec[term] = (count / length) * idf
        vectors.append(vec)
    return vectors


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    if dot == 0.0:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb)


def _pagerank(sim: np.ndarray, *, damping: float = 0.85, iterations: int = 60) -> np.ndarray:
    n = sim.shape[0]
    row_sums = sim.sum(axis=1, keepdims=True)
    # Rows that sum to 0 (a sentence similar to nothing) become uniform so the
    # walk never divides by zero and mass is conserved.
    row_sums[row_sums == 0] = 1.0
    transition = sim / row_sums
    scores = np.full(n, 1.0 / n)
    teleport = (1.0 - damping) / n
    for _ in range(iterations):
        scores = teleport + damping * (transition.T @ scores)
    return scores


def summarise(text: str, *, max_sentences: int = 5) -> str:
    """Return an extractive TL;DR of ``text`` (at most ``max_sentences``).

    Sentences are scored by TextRank and the top ``max_sentences`` are returned
    in their original document order. Deterministic and LLM-free.
    """
    sentences = _split_sentences(text)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    vectors = _tfidf_vectors(sentences)
    n = len(sentences)
    sim = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            score = _cosine(vectors[i], vectors[j])
            sim[i, j] = score
            sim[j, i] = score

    scores = _pagerank(sim)
    # Top-k by score; ties broken by earliest source index (stable, deterministic).
    ranked = sorted(range(n), key=lambda i: (-scores[i], i))
    chosen = sorted(ranked[:max_sentences])
    return " ".join(sentences[i] for i in chosen)

"""
C1-07 · Entity resolution algorithm — deterministic-first, LLM-fallback.

Architecture Report §3.5. Links every extracted person to a canonical_entity
via a 5-stage cascade. The design choice — never LLM-only — is what makes
the product defensible to immigration lawyers: every deterministic match
is auditable, and the LLM only enters the picture when deterministic
methods have already done their work.

5 stages, ordered cheapest+most-trustworthy → most-expensive:

  Stage 1: exact match on passport_mrz_doc_number (confidence 0.99)
  Stage 2: Splink-style block on (surname_main, dob_iso, nationality_iso3)
           — returns deterministic if exactly one block hit (confidence 0.95)
  Stage 3: pgvector ANN top-5 with cosine >= 0.92 gate (confidence = cosine)
  Stage 4: LLM fallback in cosine band 0.80-0.92 — returns LLM if
           verdict.confidence >= 0.85
  Stage 5: nothing matched → create_new_canonical()

Human override: if rce.corrections contains a row with
target_table='canonical_entities' for the same (case_id, surname_main,
dob_iso) signature, the linker honours the override before Stage 1.

Stores + side-effects are exposed via Protocols so the orchestrator is
pure and testable. The 30-pair fixture in tests uses in-memory doubles;
the production wiring (PostgreSQL + pgvector + Anthropic/OpenAI) lands
when C1-13 router + C1-07P prompt + pgvector migration converge.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class LinkMethod(str, Enum):
    """Mirrors rce.entity_links.link_method CHECK constraint."""

    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    HUMAN = "HUMAN"


class LinkStage(str, Enum):
    """Which of the 5 stages produced the link. Logged on agent_runs."""

    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
    MRZ_DOC_NUMBER = "MRZ_DOC_NUMBER"
    BLOCK = "BLOCK"
    ANN_HIGH = "ANN_HIGH"
    LLM_FALLBACK = "LLM_FALLBACK"
    NEW_CANONICAL = "NEW_CANONICAL"


class ExtractedPerson(BaseModel):
    """Input to the resolver — typically produced by C1-05 extraction agents."""

    model_config = ConfigDict(frozen=True)

    extracted_field_id: Optional[str] = None
    case_id: str
    surname_main: str
    given_names_main: Optional[str] = None
    surname_normalized: str
    given_names_normalized: Optional[str] = None
    dob_iso: Optional[str] = None
    nationality_iso3: Optional[str] = None
    passport_mrz_doc_number: Optional[str] = None
    embedding: Optional[Sequence[float]] = None  # 768-dim per text-embedding-3-small


class CanonicalPerson(BaseModel):
    """The canonical entity in rce.canonical_entities — person flavour."""

    model_config = ConfigDict(frozen=True)

    canonical_entity_id: str
    case_id: str
    surname_main: str
    given_names_main: Optional[str] = None
    surname_normalized: str
    given_names_normalized: Optional[str] = None
    dob_iso: Optional[str] = None
    nationality_iso3: Optional[str] = None
    passport_doc_numbers: Tuple[str, ...] = ()


class AnnHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    canonical_entity_id: str
    cosine_sim: float
    canonical: CanonicalPerson


class LinkDecision(BaseModel):
    """The output the orchestrator produces."""

    model_config = ConfigDict(frozen=True)

    canonical_entity_id: str
    link_method: LinkMethod
    confidence: float
    stage: LinkStage
    resolved_by_user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMResolverVerdict(BaseModel):
    """Structured output the LLM resolver returns (see C1-07P prompt task)."""

    model_config = ConfigDict(frozen=True)

    match: Optional[str] = None
    confidence: float = 0.0
    reasoning: Optional[str] = None


# ---------------------------------------------------------------------------
# Side-effect protocols
# ---------------------------------------------------------------------------


class CanonicalStore(Protocol):
    """Read-side of rce.canonical_entities used by stages 1–3."""

    def get_by_doc_number(self, case_id: str, doc_number: str) -> Optional[CanonicalPerson]:
        """Stage 1 — exact lookup on a known passport MRZ doc number."""
        ...

    def block_hits(
        self,
        case_id: str,
        surname_normalized: str,
        dob_iso: Optional[str],
        nationality_iso3: Optional[str],
    ) -> List[CanonicalPerson]:
        """Stage 2 — Splink-style block on (surname_normalized, dob, nationality)."""
        ...

    def ann_search(
        self,
        case_id: str,
        embedding: Sequence[float],
        top_k: int,
    ) -> List[AnnHit]:
        """Stage 3 — pgvector ANN top_k filtered by case + PERSON type."""
        ...

    def get_override(
        self,
        case_id: str,
        candidate_signature: str,
    ) -> Optional[CanonicalPerson]:
        """Honoured human override — see Architecture Report §3.5 'Human override'."""
        ...

    def create_new(self, candidate: ExtractedPerson) -> CanonicalPerson:
        """Stage 5 — write a fresh canonical_entities row."""
        ...


class LLMResolver(Protocol):
    """The C1-07P prompt wrapper. Called only in cosine band 0.80–0.92."""

    def resolve(
        self,
        candidate: ExtractedPerson,
        top_hits: Sequence[AnnHit],
    ) -> LLMResolverVerdict:
        ...


# ---------------------------------------------------------------------------
# Constants from the Architecture Report
# ---------------------------------------------------------------------------


ANN_TOP_K = 5
ANN_HIGH_GATE = 0.92
ANN_LLM_BAND_LOWER = 0.80
LLM_CONFIDENCE_GATE = 0.85

CONFIDENCE_MRZ = 0.99
CONFIDENCE_BLOCK = 0.95


# ---------------------------------------------------------------------------
# Signature helper — used by the override lookup
# ---------------------------------------------------------------------------


def signature(person: ExtractedPerson) -> str:
    """Stable signature an HR override uses to refer to a person across docs."""
    parts = [
        person.surname_normalized.lower(),
        (person.given_names_normalized or "").lower(),
        person.dob_iso or "",
        (person.nationality_iso3 or "").upper(),
    ]
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def resolve_person_entity(
    candidate: ExtractedPerson,
    *,
    store: CanonicalStore,
    llm: LLMResolver,
) -> LinkDecision:
    """
    Five-stage entity resolution. Returns the LinkDecision that the caller
    persists into rce.entity_links (link_method + confidence + the
    canonical_entity_id).

    Stage progression is verbatim from Architecture Report §3.5; see module
    docstring for the rationale.
    """
    # Human override beats every stage.
    override = store.get_override(candidate.case_id, signature(candidate))
    if override:
        return LinkDecision(
            canonical_entity_id=override.canonical_entity_id,
            link_method=LinkMethod.HUMAN,
            confidence=1.0,
            stage=LinkStage.HUMAN_OVERRIDE,
        )

    # Stage 1 — exact match on passport MRZ doc number.
    if candidate.passport_mrz_doc_number:
        hit = store.get_by_doc_number(candidate.case_id, candidate.passport_mrz_doc_number)
        if hit:
            return LinkDecision(
                canonical_entity_id=hit.canonical_entity_id,
                link_method=LinkMethod.DETERMINISTIC,
                confidence=CONFIDENCE_MRZ,
                stage=LinkStage.MRZ_DOC_NUMBER,
            )

    # Stage 2 — Splink-style block.
    block_hits = store.block_hits(
        case_id=candidate.case_id,
        surname_normalized=candidate.surname_normalized,
        dob_iso=candidate.dob_iso,
        nationality_iso3=candidate.nationality_iso3,
    )
    if len(block_hits) == 1:
        return LinkDecision(
            canonical_entity_id=block_hits[0].canonical_entity_id,
            link_method=LinkMethod.DETERMINISTIC,
            confidence=CONFIDENCE_BLOCK,
            stage=LinkStage.BLOCK,
        )

    # Stage 3 — pgvector ANN top-K with cosine gate.
    ann: List[AnnHit] = []
    if candidate.embedding is not None:
        ann = store.ann_search(
            case_id=candidate.case_id,
            embedding=candidate.embedding,
            top_k=ANN_TOP_K,
        )
    above_gate = [h for h in ann if h.cosine_sim >= ANN_HIGH_GATE]
    if len(above_gate) == 1:
        winner = above_gate[0]
        return LinkDecision(
            canonical_entity_id=winner.canonical_entity_id,
            link_method=LinkMethod.DETERMINISTIC,
            confidence=winner.cosine_sim,
            stage=LinkStage.ANN_HIGH,
        )

    # Stage 4 — LLM fallback (cosine band 0.80–0.92).
    if ann and ann[0].cosine_sim >= ANN_LLM_BAND_LOWER:
        verdict = llm.resolve(candidate, ann[:3])
        if verdict.match and verdict.confidence >= LLM_CONFIDENCE_GATE:
            return LinkDecision(
                canonical_entity_id=verdict.match,
                link_method=LinkMethod.LLM,
                confidence=verdict.confidence,
                stage=LinkStage.LLM_FALLBACK,
            )

    # Stage 5 — nothing matched, create a new canonical.
    new_canonical = store.create_new(candidate)
    return LinkDecision(
        canonical_entity_id=new_canonical.canonical_entity_id,
        link_method=LinkMethod.DETERMINISTIC,
        confidence=1.0,
        stage=LinkStage.NEW_CANONICAL,
    )


# ---------------------------------------------------------------------------
# In-memory CanonicalStore + LLMResolver for tests + future-DB swap
# ---------------------------------------------------------------------------


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity — pure-Python, dependency-free."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryCanonicalStore:
    """Reference implementation that satisfies CanonicalStore.

    Used by the C1-07 test suite. A production adapter lives in
    backend/app/services/canonical_store_pg.py (TBD when pgvector
    migration lands) and reads/writes rce.canonical_entities + the
    pgvector embedding column.
    """

    def __init__(self) -> None:
        self._canonicals: Dict[str, CanonicalPerson] = {}
        self._embeddings: Dict[str, Sequence[float]] = {}
        self._overrides: Dict[Tuple[str, str], CanonicalPerson] = {}
        self._next_id = 1

    # --- CanonicalStore protocol ----------------------------------------

    def get_by_doc_number(
        self, case_id: str, doc_number: str
    ) -> Optional[CanonicalPerson]:
        for c in self._canonicals.values():
            if c.case_id != case_id:
                continue
            if doc_number in c.passport_doc_numbers:
                return c
        return None

    def block_hits(
        self,
        case_id: str,
        surname_normalized: str,
        dob_iso: Optional[str],
        nationality_iso3: Optional[str],
    ) -> List[CanonicalPerson]:
        hits: List[CanonicalPerson] = []
        for c in self._canonicals.values():
            if c.case_id != case_id:
                continue
            if c.surname_normalized.lower() != surname_normalized.lower():
                continue
            if dob_iso and c.dob_iso and c.dob_iso != dob_iso:
                continue
            if nationality_iso3 and c.nationality_iso3 and c.nationality_iso3 != nationality_iso3:
                continue
            hits.append(c)
        return hits

    def ann_search(
        self,
        case_id: str,
        embedding: Sequence[float],
        top_k: int,
    ) -> List[AnnHit]:
        scored: List[AnnHit] = []
        for cid, vec in self._embeddings.items():
            canonical = self._canonicals.get(cid)
            if not canonical or canonical.case_id != case_id:
                continue
            sim = _cosine(embedding, vec)
            scored.append(
                AnnHit(canonical_entity_id=cid, cosine_sim=sim, canonical=canonical)
            )
        scored.sort(key=lambda h: h.cosine_sim, reverse=True)
        return scored[:top_k]

    def get_override(
        self,
        case_id: str,
        candidate_signature: str,
    ) -> Optional[CanonicalPerson]:
        return self._overrides.get((case_id, candidate_signature))

    def create_new(self, candidate: ExtractedPerson) -> CanonicalPerson:
        cid = f"canonical-{self._next_id:06d}"
        self._next_id += 1
        passport_set: Tuple[str, ...] = ()
        if candidate.passport_mrz_doc_number:
            passport_set = (candidate.passport_mrz_doc_number,)
        canonical = CanonicalPerson(
            canonical_entity_id=cid,
            case_id=candidate.case_id,
            surname_main=candidate.surname_main,
            given_names_main=candidate.given_names_main,
            surname_normalized=candidate.surname_normalized,
            given_names_normalized=candidate.given_names_normalized,
            dob_iso=candidate.dob_iso,
            nationality_iso3=candidate.nationality_iso3,
            passport_doc_numbers=passport_set,
        )
        self._canonicals[cid] = canonical
        if candidate.embedding is not None:
            self._embeddings[cid] = list(candidate.embedding)
        return canonical

    # --- Test helpers (NOT part of the Protocol) -------------------------

    def seed(self, canonical: CanonicalPerson, embedding: Optional[Sequence[float]] = None) -> None:
        self._canonicals[canonical.canonical_entity_id] = canonical
        if embedding is not None:
            self._embeddings[canonical.canonical_entity_id] = list(embedding)

    def add_override(
        self, case_id: str, candidate_signature: str, canonical: CanonicalPerson
    ) -> None:
        self._overrides[(case_id, candidate_signature)] = canonical


class FixedLLMResolver:
    """Test double for LLMResolver — returns a fixed verdict."""

    def __init__(self, verdict: LLMResolverVerdict) -> None:
        self.verdict = verdict
        self.calls: List[Tuple[ExtractedPerson, Sequence[AnnHit]]] = []

    def resolve(
        self,
        candidate: ExtractedPerson,
        top_hits: Sequence[AnnHit],
    ) -> LLMResolverVerdict:
        self.calls.append((candidate, top_hits))
        return self.verdict


class NeverCalledLLMResolver:
    """Asserts the LLM was never called — useful for stage 1-3 tests."""

    def resolve(
        self,
        candidate: ExtractedPerson,
        top_hits: Sequence[AnnHit],
    ) -> LLMResolverVerdict:
        raise AssertionError(
            "LLM resolver called when it shouldn't have been. "
            f"candidate.case_id={candidate.case_id}, "
            f"top_hits[0].cosine_sim={top_hits[0].cosine_sim if top_hits else 'n/a'}"
        )


__all__ = [
    "ANN_HIGH_GATE",
    "ANN_LLM_BAND_LOWER",
    "ANN_TOP_K",
    "AnnHit",
    "CONFIDENCE_BLOCK",
    "CONFIDENCE_MRZ",
    "CanonicalPerson",
    "CanonicalStore",
    "ExtractedPerson",
    "FixedLLMResolver",
    "InMemoryCanonicalStore",
    "LinkDecision",
    "LinkMethod",
    "LinkStage",
    "LLM_CONFIDENCE_GATE",
    "LLMResolver",
    "LLMResolverVerdict",
    "NeverCalledLLMResolver",
    "resolve_person_entity",
    "signature",
]

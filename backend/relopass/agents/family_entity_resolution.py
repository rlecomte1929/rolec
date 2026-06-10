"""Family-aware entity resolution (C2-01, deterministic-first / LLM-fallback).

When a BIRTH_CERT lists two parents, or a FOSTER_CARE_ORDER names a guardian,
those people are almost always *already* on the case as canonical PERSON
entities (the employee and their spouse). The resolver's job is to link the
extracted name back to the existing canonical entity instead of minting a
duplicate.

This is a focused, case-scoped sibling to the general C1-07 resolver in
``backend.relopass.agents.entity_resolution`` (the 5-stage
``resolve_person_entity`` cascade): C1-07 links any extracted person to a
canonical via MRZ/block/ANN/LLM stages, whereas this module solves the narrower
family case — matching a parent/guardian name against the small set of PERSONs
already on the case by name normalisation alone. The two are kept separate
because their inputs and contracts differ; a future task may fold this into
C1-07. It imports nothing outside ``backend.relopass`` (no SQLAlchemy / psycopg2 / SDK),
matching the package constraint in ``backend/relopass/__init__.py``. Persistence
of ``entity_links`` rows happens one layer up via the same sink pattern the
extraction agents use.

Resolution strategy (in order):

1. **Deterministic** — normalize both names via the C1-06 ``normalize_name``
   library (ICAO fold + Devanagari transliteration + particle handling) and
   compare ``surname_main`` plus given-name overlap. A surname-main equality
   with at least one shared given name (or a shared initial when one side has
   only an initial) is a deterministic match. ``link_method = DETERMINISTIC``.
2. **LLM fallback** — when deterministic matching is inconclusive, an optional
   injected callable may adjudicate. ``link_method = LLM``. The callable is a
   pure function ``(query_name, [candidate_names]) -> Optional[index]`` so this
   module stays SDK-free and trivially testable.
3. **No match** — return a result with ``matched = False``. The caller mints a
   new canonical PERSON and surfaces a ``Requires attention`` link so a human
   confirms the orphan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from backend.relopass.normalize import normalize_name


# ─────────────────────────────────────────────────────────────────────────────
# Canonical PERSON candidate (case-scoped)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CanonicalPerson:
    """A canonical PERSON entity already on the case.

    ``display_name`` is whatever form the canonical entity carries (e.g. the
    employee's passport name). ``issuing_state_iso3`` lets the resolver apply the
    right ICAO fold when normalising for comparison.
    """

    canonical_entity_id: UUID
    display_name: str
    issuing_state_iso3: Optional[str] = None


# The LLM adjudicator contract: given a query name and an ordered list of
# candidate display names, return the index of the match or None. Pure function;
# no SDK. Tests inject a stub.
LLMNameAdjudicator = Callable[[str, Sequence[str]], Optional[int]]


@dataclass(frozen=True)
class ResolutionResult:
    """Outcome of resolving one extracted name against the case canonical set."""

    matched: bool
    canonical_entity_id: Optional[UUID]
    link_method: Optional[str]  # 'DETERMINISTIC' | 'LLM' | None
    confidence: float
    query_name: str
    # When unmatched, the caller mints a new canonical and surfaces this status.
    resolution_status: str  # 'Resolved' | 'Requires attention'


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic comparison
# ─────────────────────────────────────────────────────────────────────────────


def _given_name_overlap(
    a: Tuple[str, ...], b: Tuple[str, ...]
) -> bool:
    """True if the two given-name tuples share a name, or one side carries only
    an initial that matches the other side's leading initial.
    """
    if not a or not b:
        return False
    a_lower = {g.lower() for g in a}
    b_lower = {g.lower() for g in b}
    if a_lower & b_lower:
        return True
    # Initial-only match: "J" vs "Jean".
    a_inits = {g[0].lower() for g in a if g}
    b_inits = {g[0].lower() for g in b if g}
    # Only treat as a match if at least one side is an initial-only token.
    a_has_initial_only = any(len(g) == 1 for g in a)
    b_has_initial_only = any(len(g) == 1 for g in b)
    if (a_has_initial_only or b_has_initial_only) and (a_inits & b_inits):
        return True
    return False


def _deterministic_match(
    query: str,
    candidate: CanonicalPerson,
) -> Tuple[bool, float]:
    """Return (is_match, confidence) for a deterministic surname+given comparison."""
    q = normalize_name(query, candidate.issuing_state_iso3)
    c = normalize_name(candidate.display_name, candidate.issuing_state_iso3)

    if not q.surname_main or not c.surname_main:
        return False, 0.0
    if q.surname_main != c.surname_main:
        return False, 0.0

    if _given_name_overlap(q.given_names, c.given_names):
        return True, 0.97
    # Surname matches but given names don't overlap — not a deterministic match.
    # (Could be a sibling, a parent with the same surname, etc.) Defer to LLM.
    return False, 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Resolver
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FamilyEntityResolver:
    """Resolves extracted person names to canonical PERSONs already on a case.

    ``canonical_persons`` is the case-scoped set of existing PERSON canonical
    entities (e.g. the employee + spouse). ``llm_adjudicator`` is optional; when
    supplied it is consulted only after deterministic matching is inconclusive.

    No new canonical entities are created here — that is the caller's
    responsibility, and only when :attr:`ResolutionResult.matched` is False.
    """

    canonical_persons: List[CanonicalPerson] = field(default_factory=list)
    llm_adjudicator: Optional[LLMNameAdjudicator] = None

    def resolve(self, query_name: Optional[str]) -> ResolutionResult:
        if not query_name or not query_name.strip():
            return ResolutionResult(
                matched=False,
                canonical_entity_id=None,
                link_method=None,
                confidence=0.0,
                query_name=query_name or "",
                resolution_status="Requires attention",
            )

        # 1. Deterministic pass.
        best: Optional[Tuple[CanonicalPerson, float]] = None
        for cand in self.canonical_persons:
            is_match, conf = _deterministic_match(query_name, cand)
            if is_match and (best is None or conf > best[1]):
                best = (cand, conf)
        if best is not None:
            return ResolutionResult(
                matched=True,
                canonical_entity_id=best[0].canonical_entity_id,
                link_method="DETERMINISTIC",
                confidence=best[1],
                query_name=query_name,
                resolution_status="Resolved",
            )

        # 2. LLM fallback (optional).
        if self.llm_adjudicator is not None and self.canonical_persons:
            candidate_names = [c.display_name for c in self.canonical_persons]
            idx = self.llm_adjudicator(query_name, candidate_names)
            if idx is not None and 0 <= idx < len(self.canonical_persons):
                return ResolutionResult(
                    matched=True,
                    canonical_entity_id=self.canonical_persons[idx].canonical_entity_id,
                    link_method="LLM",
                    confidence=0.80,
                    query_name=query_name,
                    resolution_status="Resolved",
                )

        # 3. Orphan — caller mints a new canonical + surfaces for review.
        return ResolutionResult(
            matched=False,
            canonical_entity_id=None,
            link_method=None,
            confidence=0.0,
            query_name=query_name,
            resolution_status="Requires attention",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entity-link record (sink-bound, mirrors rce.entity_links)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EntityLinkRecord:
    """One resolved link — maps 1:1 to ``rce.entity_links``.

    ``extracted_field_id`` ties the link to the field the name came from;
    ``canonical_entity_id`` is the existing (or newly minted) canonical PERSON.
    """

    extracted_field_id: UUID
    canonical_entity_id: UUID
    link_method: str  # 'DETERMINISTIC' | 'LLM' | 'HUMAN'
    confidence: Optional[float] = None


@dataclass
class InMemoryEntityLinkSink:
    """Test/standalone sink collecting ``rce.entity_links`` rows + minted canonicals."""

    links: List[EntityLinkRecord] = field(default_factory=list)
    # canonical_entity_ids the caller minted because no match was found.
    minted_canonical_ids: List[UUID] = field(default_factory=list)
    minted_by_name: Dict[UUID, str] = field(default_factory=dict)

    def write_link(self, link: EntityLinkRecord) -> None:
        self.links.append(link)

    def record_minted_canonical(self, canonical_entity_id: UUID, name: str) -> None:
        self.minted_canonical_ids.append(canonical_entity_id)
        self.minted_by_name[canonical_entity_id] = name

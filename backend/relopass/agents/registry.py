"""Agent persistence + Parsewise versioning (C1-05a).

Public surface:

* :class:`AgentStorage` — Protocol the registry calls into. The concrete
  Supabase/psycopg2 adapter lives one layer up (out of this primitive
  package); tests install :class:`InMemoryAgentStorage`.
* :class:`AgentRegistry` — High-level API.  Calling :meth:`save_agent`
  applies the Parsewise versioning rule: if any of the 8 versioned fields
  differs from the agent's current version, create a new
  :class:`ExtractionAgentVersion` and clear the prior version's
  ExtractedField rows.

Per the package constraint (``backend/relopass/__init__.py``), nothing in
this file imports SQLAlchemy, psycopg2, FastAPI, or any vendor SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Tuple
from uuid import UUID, uuid4

from .models import (
    ExtractionAgent,
    ExtractionAgentVersion,
    compute_version_hash,
    list_versioned_field_diffs,
)


class AgentRegistryError(Exception):
    """Raised on save/load violations (e.g. unknown agent, hash collision)."""


# ─────────────────────────────────────────────────────────────────────────────
# Storage Protocol
# ─────────────────────────────────────────────────────────────────────────────


class AgentStorage(Protocol):
    """Persistence contract the registry calls into.

    The concrete adapter (Supabase/psycopg2) lives outside this package
    (``backend/services/extraction_agents_storage.py`` — future task).
    Tests use :class:`InMemoryAgentStorage`.
    """

    def get_agent_id_by_name(self, name: str) -> Optional[UUID]:
        ...

    def insert_agent(self, agent_id: UUID, name: str, description: Optional[str]) -> None:
        ...

    def insert_version(self, version: ExtractionAgentVersion) -> None:
        ...

    def get_version(self, agent_version_id: UUID) -> Optional[ExtractionAgentVersion]:
        ...

    def get_current_version_id(self, agent_id: UUID) -> Optional[UUID]:
        ...

    def set_current_version(self, agent_id: UUID, agent_version_id: UUID) -> None:
        ...

    def next_version_number(self, agent_id: UUID) -> int:
        ...

    def clear_extractions_for_version(self, agent_version_id: UUID) -> int:
        """Delete ExtractedField rows produced by runs against this agent
        version. Returns the count deleted. Called when Parsewise versioning
        determines the prior version is now superseded.
        """
        ...

    def find_version_by_hash(
        self, agent_id: UUID, version_hash: str
    ) -> Optional[ExtractionAgentVersion]:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# In-memory storage (test default)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _AgentRecord:
    agent_id: UUID
    name: str
    description: Optional[str]
    current_version_id: Optional[UUID] = None


@dataclass
class InMemoryAgentStorage:
    """Thread-unsafe in-memory implementation of :class:`AgentStorage`.

    Used by tests and by any caller that wants to exercise the registry
    without a real DB. The shape mirrors what the SQL adapter does
    transactionally; the only behavioural shortcut is that nothing here
    enforces serializable isolation, so concurrent ``save_agent`` calls
    from multiple threads would race. In production, the SQL adapter
    wraps :meth:`AgentRegistry.save_agent` in a SERIALIZABLE transaction.
    """

    agents: Dict[UUID, _AgentRecord] = field(default_factory=dict)
    versions: Dict[UUID, ExtractionAgentVersion] = field(default_factory=dict)
    # extracted_field_id stored by version → set of ids
    extractions_by_version: Dict[UUID, List[UUID]] = field(default_factory=dict)
    # Auxiliary indexes
    _agents_by_name: Dict[str, UUID] = field(default_factory=dict)
    _version_counter: Dict[UUID, int] = field(default_factory=dict)

    # ---- AgentStorage interface ----

    def get_agent_id_by_name(self, name: str) -> Optional[UUID]:
        return self._agents_by_name.get(name)

    def insert_agent(self, agent_id: UUID, name: str, description: Optional[str]) -> None:
        if name in self._agents_by_name:
            raise AgentRegistryError(f"Agent with name {name!r} already exists")
        self.agents[agent_id] = _AgentRecord(agent_id=agent_id, name=name, description=description)
        self._agents_by_name[name] = agent_id

    def insert_version(self, version: ExtractionAgentVersion) -> None:
        if version.agent_version_id in self.versions:
            raise AgentRegistryError(
                f"Version {version.agent_version_id} already exists"
            )
        # version_hash uniqueness within an agent
        for existing in self.versions.values():
            if (
                existing.agent_id == version.agent_id
                and existing.version_hash == version.version_hash
            ):
                raise AgentRegistryError(
                    f"Agent {version.agent_id} already has a version with hash "
                    f"{version.version_hash[:12]}…"
                )
        self.versions[version.agent_version_id] = version
        self.extractions_by_version.setdefault(version.agent_version_id, [])

    def get_version(self, agent_version_id: UUID) -> Optional[ExtractionAgentVersion]:
        return self.versions.get(agent_version_id)

    def get_current_version_id(self, agent_id: UUID) -> Optional[UUID]:
        rec = self.agents.get(agent_id)
        return rec.current_version_id if rec else None

    def set_current_version(self, agent_id: UUID, agent_version_id: UUID) -> None:
        rec = self.agents.get(agent_id)
        if rec is None:
            raise AgentRegistryError(f"Unknown agent {agent_id}")
        rec.current_version_id = agent_version_id

    def next_version_number(self, agent_id: UUID) -> int:
        nxt = self._version_counter.get(agent_id, 0) + 1
        self._version_counter[agent_id] = nxt
        return nxt

    def clear_extractions_for_version(self, agent_version_id: UUID) -> int:
        rows = self.extractions_by_version.get(agent_version_id, [])
        count = len(rows)
        self.extractions_by_version[agent_version_id] = []
        return count

    def find_version_by_hash(
        self, agent_id: UUID, version_hash: str
    ) -> Optional[ExtractionAgentVersion]:
        for v in self.versions.values():
            if v.agent_id == agent_id and v.version_hash == version_hash:
                return v
        return None

    # ---- Test helpers (not part of AgentStorage) ----

    def record_extraction(self, agent_version_id: UUID, extracted_field_id: UUID) -> None:
        """Simulate the runtime writing an ExtractedField row tied to a
        version. Used in tests to verify the versioning rule's "clear old
        extractions" behaviour fires correctly.
        """
        self.extractions_by_version.setdefault(agent_version_id, []).append(extracted_field_id)


# ─────────────────────────────────────────────────────────────────────────────
# Registry — high-level API
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SaveResult:
    """What :meth:`AgentRegistry.save_agent` returns to the caller."""

    agent_id: UUID
    version: ExtractionAgentVersion
    created_new_agent: bool
    created_new_version: bool
    cleared_extractions_for_prior_version_id: Optional[UUID]
    cleared_extraction_count: int
    changed_fields: Tuple[str, ...] = ()


class AgentRegistry:
    """Save / load agents with Parsewise versioning enforced.

    Lifecycle:

    1. Caller constructs an :class:`ExtractionAgent` with the 9 Parsewise fields.
    2. :meth:`save_agent` computes a version hash over the 8 versioned fields.
    3. If the agent doesn't exist, the registry creates the agent row + a v1
       version row.
    4. If the agent exists and the new hash matches the current version's
       hash, the save is a no-op (returns the existing version).
    5. If the hashes differ, a new version row is created with
       ``version_number = prior + 1``, the agent's ``current_version_id`` is
       advanced, AND the prior version's ExtractedField rows are cleared
       (Parsewise rule).
    """

    def __init__(self, storage: AgentStorage) -> None:
        self._storage = storage

    # ---- API ----

    def save_agent(self, agent: ExtractionAgent) -> SaveResult:
        new_hash = compute_version_hash(agent)
        existing_id = self._storage.get_agent_id_by_name(agent.name)

        if existing_id is None:
            return self._create_first_version(agent, new_hash)

        return self._save_or_advance(agent, existing_id, new_hash)

    def load_current(self, name: str) -> ExtractionAgentVersion:
        """Return the current version of the agent with the given ``name``.

        Raises :class:`AgentRegistryError` if no such agent or if the
        agent has no current version (shouldn't happen in normal use; the
        registry sets ``current_version_id`` on every successful save).
        """
        agent_id = self._storage.get_agent_id_by_name(name)
        if agent_id is None:
            raise AgentRegistryError(f"No agent named {name!r}")
        version_id = self._storage.get_current_version_id(agent_id)
        if version_id is None:
            raise AgentRegistryError(f"Agent {name!r} has no current version")
        version = self._storage.get_version(version_id)
        if version is None:
            raise AgentRegistryError(
                f"Agent {name!r} current_version_id points at missing row {version_id}"
            )
        return version

    # ---- Internals ----

    def _create_first_version(
        self, agent: ExtractionAgent, version_hash: str
    ) -> SaveResult:
        agent_id = uuid4()
        self._storage.insert_agent(agent_id, agent.name, agent.description)
        # Bump the counter on the FIRST save too so subsequent saves return
        # 2, 3, … in order. Without this, v1 hardcoded to 1 but the next
        # next_version_number() call would also return 1 (bug).
        n = self._storage.next_version_number(agent_id)
        version = self._build_version(agent, agent_id, version_number=n, version_hash=version_hash)
        self._storage.insert_version(version)
        self._storage.set_current_version(agent_id, version.agent_version_id)
        return SaveResult(
            agent_id=agent_id,
            version=version,
            created_new_agent=True,
            created_new_version=True,
            cleared_extractions_for_prior_version_id=None,
            cleared_extraction_count=0,
            changed_fields=(),
        )

    def _save_or_advance(
        self, agent: ExtractionAgent, agent_id: UUID, new_hash: str
    ) -> SaveResult:
        current_version_id = self._storage.get_current_version_id(agent_id)
        current = (
            self._storage.get_version(current_version_id) if current_version_id else None
        )

        if current is not None and current.version_hash == new_hash:
            # No versioned-field change. The agent's non-versioned fields
            # (description, dimensions, output_schema_required_keys) MAY differ
            # but per the Parsewise rule those don't trigger a new version.
            # We leave the existing version as-is.
            return SaveResult(
                agent_id=agent_id,
                version=current,
                created_new_agent=False,
                created_new_version=False,
                cleared_extractions_for_prior_version_id=None,
                cleared_extraction_count=0,
                changed_fields=(),
            )

        # Sanity check — a same-hash version we don't know about would be a bug.
        # (Hash collisions in SHA-256 are not a real concern for our input space.)
        existing = self._storage.find_version_by_hash(agent_id, new_hash)
        if existing is not None and existing.version_hash == new_hash:
            # Same configuration as a historical version — make it current
            # again without re-inserting. Don't clear extractions on the
            # prior version: the user just switched back; their work isn't
            # invalidated.
            self._storage.set_current_version(agent_id, existing.agent_version_id)
            return SaveResult(
                agent_id=agent_id,
                version=existing,
                created_new_agent=False,
                created_new_version=False,
                cleared_extractions_for_prior_version_id=None,
                cleared_extraction_count=0,
                changed_fields=tuple(list_versioned_field_diffs(agent, current))
                if current
                else (),
            )

        next_n = self._storage.next_version_number(agent_id)
        new_version = self._build_version(
            agent, agent_id, version_number=next_n, version_hash=new_hash
        )
        self._storage.insert_version(new_version)
        self._storage.set_current_version(agent_id, new_version.agent_version_id)

        cleared = 0
        cleared_prior: Optional[UUID] = None
        if current is not None:
            # Parsewise rule: changing any of the versioned fields clears the
            # old version's extractions. This is the load-bearing behaviour the
            # brief calls out as "non-negotiable".
            cleared = self._storage.clear_extractions_for_version(current.agent_version_id)
            cleared_prior = current.agent_version_id

        return SaveResult(
            agent_id=agent_id,
            version=new_version,
            created_new_agent=False,
            created_new_version=True,
            cleared_extractions_for_prior_version_id=cleared_prior,
            cleared_extraction_count=cleared,
            changed_fields=tuple(list_versioned_field_diffs(agent, current))
            if current
            else (),
        )

    @staticmethod
    def _build_version(
        agent: ExtractionAgent,
        agent_id: UUID,
        *,
        version_number: int,
        version_hash: str,
    ) -> ExtractionAgentVersion:
        return ExtractionAgentVersion(
            agent_version_id=uuid4(),
            agent_id=agent_id,
            name=agent.name,
            version_number=version_number,
            version_hash=version_hash,
            extraction_instructions=agent.extraction_instructions,
            value_type=agent.value_type,
            unit=agent.unit,
            dimensions=agent.dimensions,
            resolution_instructions=agent.resolution_instructions,
            inconsistency_instructions=agent.inconsistency_instructions,
            enable_web_search=agent.enable_web_search,
            enable_complex_calculations_in_resolution=agent.enable_complex_calculations_in_resolution,
            examples=agent.examples,
            output_schema_required_keys=agent.output_schema_required_keys,
            created_at=datetime.now(tz=timezone.utc),
        )

"""ReloPass Extraction Agent runtime (C1-05a, Parsewise pattern).

Three layers:

* :mod:`backend.relopass.agents.models` — Pydantic shapes for the 9-field
  Parsewise agent definition, ExtractedField rows, ParsedDocument input.
* :mod:`backend.relopass.agents.registry` — Persistence layer + the
  Parsewise versioning rule.
* :mod:`backend.relopass.agents.runtime` — :class:`ExtractionRunner` that
  routes via the C1-13 LLM router, validates output against the per-agent
  schema, writes ExtractedField rows + an agent_runs entry.

Per the :file:`backend/relopass/__init__.py` constraint, no module here
imports from ``backend/app/``, FastAPI, SQLAlchemy, or any vendor SDK
beyond Pydantic. Storage is a Protocol; the concrete Supabase/psycopg2
adapter lives one layer up (``backend/services/extraction_agents_storage.py``,
future task).
"""

from .models import (
    VERSIONED_FIELDS,
    ExtractedField,
    ExtractionAgent,
    ExtractionAgentExample,
    ExtractionAgentVersion,
    ExtractionRunResult,
    ParsedDocument,
    ParsedWord,
    VersionedFieldSnapshot,
    compute_version_hash,
)
from .registry import (
    AgentRegistry,
    AgentRegistryError,
    AgentStorage,
    InMemoryAgentStorage,
)
from .runtime import (
    ExtractionRunner,
    ExtractionRuntimeError,
    SchemaValidationError,
)

__all__ = [
    "VERSIONED_FIELDS",
    "AgentRegistry",
    "AgentRegistryError",
    "AgentStorage",
    "ExtractedField",
    "ExtractionAgent",
    "ExtractionAgentExample",
    "ExtractionAgentVersion",
    "ExtractionRunResult",
    "ExtractionRunner",
    "ExtractionRuntimeError",
    "InMemoryAgentStorage",
    "ParsedDocument",
    "ParsedWord",
    "SchemaValidationError",
    "VersionedFieldSnapshot",
    "compute_version_hash",
]

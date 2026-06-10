"""E-PIPE-4 · Extraction orchestrator.

Given a parsed document (E-PIPE-2 OcrParseResult) + its document_type_code, route
to the right C1-05/C2-01 extraction agent, run it, and persist the ExtractedFields
+ agent_run via the production SupabaseExtractionSink / SupabaseAgentStorage
(E-PIPE-3). Per-document, idempotent, fail-soft.

Agent construction/run contracts differ by type:
  - MARRIAGE_CERT / BIRTH_CERT / FOSTER_CARE_ORDER : async ``run(document)`` (LLM);
    BIRTH/FOSTER also take a case-scoped FamilyEntityResolver (entity resolution is
    E-PIPE-5 — default empty resolver here → orphan links, no canonical match yet).
  - ID_CARD     : sync ``run(document, mrz_text=...)`` — MRZ-deterministic, no LLM,
    so this type runs fully end-to-end today.
  - PASSPORT_TD3: async ``run(document, mrz_text=...)`` (MRZ + DI + LLM).

All agents share ``(registry, sink)`` + ``register()``. We build AgentRegistry over
the Supabase storage and pass the Supabase sink; register() persists the agent
version, run() writes rce.agent_runs + rce.extracted_fields.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from backend.relopass.agents import AgentRegistry
from backend.relopass.agents.extraction import EXTRACTION_AGENT_REGISTRY
from backend.relopass.agents.extraction.passport_td3 import PassportTd3Agent

from .rce_ocr_parser import OcrParseResult

log = logging.getLogger(__name__)

# Types whose identity comes from an MRZ → run(document, mrz_text=...).
_MRZ_TYPES = {"ID_CARD", "PASSPORT_TD3", "PASSPORT"}
# Types whose run() is synchronous (no LLM). Everything else is async.
_SYNC_TYPES = {"ID_CARD"}
# Types whose agent takes a case-scoped FamilyEntityResolver.
_RESOLVER_TYPES = {"BIRTH_CERT", "FOSTER_CARE_ORDER"}


@dataclass(frozen=True)
class ExtractionOutcome:
    document_id: UUID
    document_type_code: Optional[str]
    status: str           # 'ok' | 'skipped_no_agent' | 'skipped_no_mrz' | 'failed'
    fields_written: int
    detail: str = ""


def _agent_class(document_type_code: str) -> Optional[type]:
    if document_type_code in ("PASSPORT_TD3", "PASSPORT"):
        return PassportTd3Agent
    return EXTRACTION_AGENT_REGISTRY.get(document_type_code)  # MARRIAGE/BIRTH/FOSTER/ID_CARD


async def dispatch_and_run(
    *,
    ocr_result: OcrParseResult,
    document_type_code: str,
    sink: Any,
    agent_storage: Any,
    resolver: Any = None,
) -> ExtractionOutcome:
    """Route → construct → register → run → persist (via the given sink/storage).

    Pure of transaction/engine concerns so it is unit-testable with in-memory
    backends. Fail-soft: never raises; returns an ExtractionOutcome describing what
    happened.
    """
    document = ocr_result.parsed_document
    doc_id = document.document_id
    code = (document_type_code or "").upper()

    agent_cls = _agent_class(code)
    if agent_cls is None:
        log.info("rce_extraction: no agent for document_type=%s (doc=%s)", code, doc_id)
        return ExtractionOutcome(doc_id, code, "skipped_no_agent", 0, "no registered agent")

    if code in _MRZ_TYPES and not ocr_result.mrz_text:
        log.info("rce_extraction: %s needs mrz_text but none present (doc=%s)", code, doc_id)
        return ExtractionOutcome(doc_id, code, "skipped_no_mrz", 0, "no mrz_text")

    try:
        registry = AgentRegistry(agent_storage)
        kwargs: dict = {"registry": registry, "sink": sink}
        if code in _RESOLVER_TYPES and resolver is not None:
            kwargs["resolver"] = resolver
        agent = agent_cls(**kwargs)
        agent.register()

        if code in _SYNC_TYPES:  # ID_CARD — deterministic, synchronous
            result = agent.run(document, mrz_text=ocr_result.mrz_text)
        elif code in _MRZ_TYPES:  # PASSPORT_TD3 — async, needs mrz_text
            result = await agent.run(document, mrz_text=ocr_result.mrz_text)
        else:  # family agents — async, LLM over document.text
            result = await agent.run(document)

        n = len(getattr(result, "fields", ()) or ())
        log.info("rce_extraction: %s doc=%s wrote %d fields", code, doc_id, n)
        return ExtractionOutcome(doc_id, code, "ok", n)
    except Exception as exc:  # never break the pipeline
        log.warning("rce_extraction failed-soft for doc=%s type=%s: %s", doc_id, code, exc)
        return ExtractionOutcome(doc_id, code, "failed", 0, str(exc))


async def run_extraction_for_document(
    *,
    ocr_result: OcrParseResult,
    document_type_code: str,
    resolver: Any = None,
    engine: Any = None,
) -> ExtractionOutcome:
    """Production entry: open one transaction, build the Supabase storage + sink,
    and dispatch. Commit on success; the whole agent run (version register +
    extracted fields + agent_run) is one transaction.
    """
    if engine is None:
        from backend.database import db  # lazy

        engine = db.engine
    from .extraction_agents_storage import SupabaseAgentStorage, SupabaseExtractionSink

    with engine.begin() as conn:
        return await dispatch_and_run(
            ocr_result=ocr_result,
            document_type_code=document_type_code,
            sink=SupabaseExtractionSink(conn),
            agent_storage=SupabaseAgentStorage(conn),
            resolver=resolver,
        )

"""E-PIPE-3 · Production persistence for the rce extraction agents.

The relopass extraction runtime writes through two Protocols and only ships
in-memory implementations:
  - ExtractionSink   (backend.relopass.agents.runtime) — agent_runs + extracted_fields
  - AgentStorage     (backend.relopass.agents.registry) — agent + version registry
This module supplies the Supabase-backed implementations so extraction output and
the Parsewise agent-version ledger land in rce.* . Access is the service-role
db.engine + text() pattern (rce.* is service-role-only), matching
contradiction_store_pg.py.

Schema mapping (verified against prod 2026-06-10):
  - rce.extraction_agents (agent_id, name, description, current_version_id)
  - rce.agent_versions   (agent_version_id, agent_id, version_number, version_hash,
        extraction_instructions, value_type, unit, dimensions, resolution_instructions,
        inconsistency_instructions, enable_web_search,
        enable_complex_calculations_in_resolution, examples jsonb, output_schema jsonb)
        UNIQUE(agent_id, version_hash), UNIQUE(agent_id, version_number)
  - rce.agent_runs       (agent_run_id, case_id, inputs_digest, output_digest, status,
        started_at, finished_at, llm_model_used, cost_tokens, agent_version_ref)
        NOTE: no document_id / cost_usd / separate tokens columns — the run's
        document link is recovered via rce.extracted_fields.agent_run_id; cost_tokens
        stores tokens_in+tokens_out; cost_usd is not persisted.
  - rce.extracted_fields (…, agent_run_id, phi_class NOT NULL ∈
        {NONE,PII,SENSITIVE,BIOMETRIC,CRIMINAL})
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import text

from backend.relopass.agents.models import (
    ExtractedField,
    ExtractionAgentExample,
    ExtractionAgentVersion,
)

_PHI_CLASSES = {"NONE", "PII", "SENSITIVE", "BIOMETRIC", "CRIMINAL"}


# ─────────────────────────────────────────────────────────────────────────────
# Pure mapping helpers (unit-tested)
# ─────────────────────────────────────────────────────────────────────────────


def _phi_class(field: ExtractedField) -> str:
    """rce.extracted_fields.phi_class is NOT NULL with a CHECK. The agents stash a
    phi_class hint inside value_canonical (e.g. passport biometric); fall back to
    'NONE'."""
    vc = field.value_canonical if isinstance(field.value_canonical, dict) else {}
    pc = vc.get("phi_class")
    return pc if pc in _PHI_CLASSES else "NONE"


def _extracted_field_params(f: ExtractedField) -> dict:
    return {
        "extracted_field_id": str(uuid4()),
        "document_id": str(f.document_id),
        "field_key": f.field_key,
        "value_raw": f.value_raw,
        "value_canonical": json.dumps(f.value_canonical) if f.value_canonical is not None else None,
        "confidence": f.confidence,
        "bbox_page": f.bbox_page,
        "bbox_x0": f.bbox_x0,
        "bbox_y0": f.bbox_y0,
        "bbox_x1": f.bbox_x1,
        "bbox_y1": f.bbox_y1,
        "agent_run_id": str(f.agent_run_id) if f.agent_run_id is not None else None,
        "resolution_status": f.resolution_status,
        "phi_class": _phi_class(f),
    }


def _version_params(v: ExtractionAgentVersion) -> dict:
    return {
        "agent_version_id": str(v.agent_version_id),
        "agent_id": str(v.agent_id),
        "version_number": v.version_number,
        "version_hash": v.version_hash,
        "extraction_instructions": v.extraction_instructions,
        "value_type": v.value_type,
        "unit": v.unit,
        "dimensions": v.dimensions,
        "resolution_instructions": v.resolution_instructions,
        "inconsistency_instructions": v.inconsistency_instructions,
        "enable_web_search": v.enable_web_search,
        "enable_complex_calculations_in_resolution": v.enable_complex_calculations_in_resolution,
        "examples": json.dumps([e.model_dump(mode="json") for e in v.examples]),
        "output_schema": json.dumps({"required_keys": list(v.output_schema_required_keys)}),
    }


def _row_to_version(r: Any) -> ExtractionAgentVersion:
    examples_raw = r["examples"] or []
    output_schema = r["output_schema"] or {}
    return ExtractionAgentVersion(
        agent_version_id=r["agent_version_id"],
        agent_id=r["agent_id"],
        name=r["name"],
        version_number=r["version_number"],
        version_hash=r["version_hash"],
        extraction_instructions=r["extraction_instructions"],
        value_type=r["value_type"],
        unit=r["unit"],
        dimensions=r["dimensions"],
        resolution_instructions=r["resolution_instructions"],
        inconsistency_instructions=r["inconsistency_instructions"],
        enable_web_search=r["enable_web_search"],
        enable_complex_calculations_in_resolution=r["enable_complex_calculations_in_resolution"],
        examples=tuple(ExtractionAgentExample(**e) for e in examples_raw),
        output_schema_required_keys=tuple(output_schema.get("required_keys", [])),
        created_at=r["created_at"],
    )


_VERSION_SELECT = """
    SELECT v.agent_version_id, v.agent_id, a.name, v.version_number, v.version_hash,
           v.extraction_instructions, v.value_type, v.unit, v.dimensions,
           v.resolution_instructions, v.inconsistency_instructions,
           v.enable_web_search, v.enable_complex_calculations_in_resolution,
           v.examples, v.output_schema, v.created_at
    FROM rce.agent_versions v
    JOIN rce.extraction_agents a ON a.agent_id = v.agent_id
"""


# ─────────────────────────────────────────────────────────────────────────────
# AgentStorage (rce.extraction_agents + rce.agent_versions)
# ─────────────────────────────────────────────────────────────────────────────


class SupabaseAgentStorage:
    """AgentStorage backed by rce.extraction_agents + rce.agent_versions.

    Construct with an open SQLAlchemy Connection (service-role engine). Implements
    the registry's persistence contract so AgentRegistry.save_agent / load_current
    work against prod.
    """

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def get_agent_id_by_name(self, name: str) -> Optional[UUID]:
        v = self._conn.execute(
            text("SELECT agent_id FROM rce.extraction_agents WHERE name = :name"),
            {"name": name},
        ).scalar()
        return v

    def insert_agent(self, agent_id: UUID, name: str, description: Optional[str]) -> None:
        self._conn.execute(
            text(
                """INSERT INTO rce.extraction_agents (agent_id, name, description)
                   VALUES (CAST(:id AS UUID), :name, :description)
                   ON CONFLICT (name) DO NOTHING"""
            ),
            {"id": str(agent_id), "name": name, "description": description},
        )

    def insert_version(self, version: ExtractionAgentVersion) -> None:
        self._conn.execute(
            text(
                """INSERT INTO rce.agent_versions
                     (agent_version_id, agent_id, version_number, version_hash,
                      extraction_instructions, value_type, unit, dimensions,
                      resolution_instructions, inconsistency_instructions,
                      enable_web_search, enable_complex_calculations_in_resolution,
                      examples, output_schema)
                   VALUES
                     (CAST(:agent_version_id AS UUID), CAST(:agent_id AS UUID),
                      :version_number, :version_hash, :extraction_instructions,
                      :value_type, :unit, :dimensions, :resolution_instructions,
                      :inconsistency_instructions, :enable_web_search,
                      :enable_complex_calculations_in_resolution,
                      CAST(:examples AS JSONB), CAST(:output_schema AS JSONB))
                   ON CONFLICT (agent_id, version_hash) DO NOTHING"""
            ),
            _version_params(version),
        )

    def get_version(self, agent_version_id: UUID) -> Optional[ExtractionAgentVersion]:
        r = self._conn.execute(
            text(_VERSION_SELECT + " WHERE v.agent_version_id = CAST(:id AS UUID)"),
            {"id": str(agent_version_id)},
        ).mappings().first()
        return _row_to_version(r) if r else None

    def get_current_version_id(self, agent_id: UUID) -> Optional[UUID]:
        return self._conn.execute(
            text("SELECT current_version_id FROM rce.extraction_agents WHERE agent_id = CAST(:id AS UUID)"),
            {"id": str(agent_id)},
        ).scalar()

    def set_current_version(self, agent_id: UUID, agent_version_id: UUID) -> None:
        self._conn.execute(
            text(
                """UPDATE rce.extraction_agents
                   SET current_version_id = CAST(:vid AS UUID), updated_at = now()
                   WHERE agent_id = CAST(:aid AS UUID)"""
            ),
            {"vid": str(agent_version_id), "aid": str(agent_id)},
        )

    def next_version_number(self, agent_id: UUID) -> int:
        n = self._conn.execute(
            text("SELECT COALESCE(MAX(version_number), 0) FROM rce.agent_versions WHERE agent_id = CAST(:id AS UUID)"),
            {"id": str(agent_id)},
        ).scalar()
        return int(n or 0) + 1

    def clear_extractions_for_version(self, agent_version_id: UUID) -> int:
        # Extractions link to a version via agent_runs.agent_version_ref; delete the
        # fields produced by that version's runs. Returns the number removed.
        result = self._conn.execute(
            text(
                """DELETE FROM rce.extracted_fields
                   WHERE agent_run_id IN (
                     SELECT agent_run_id FROM rce.agent_runs
                     WHERE agent_version_ref = CAST(:vid AS UUID)
                   )"""
            ),
            {"vid": str(agent_version_id)},
        )
        return result.rowcount or 0

    def find_version_by_hash(
        self, agent_id: UUID, version_hash: str
    ) -> Optional[ExtractionAgentVersion]:
        r = self._conn.execute(
            text(_VERSION_SELECT + " WHERE v.agent_id = CAST(:aid AS UUID) AND v.version_hash = :h"),
            {"aid": str(agent_id), "h": version_hash},
        ).mappings().first()
        return _row_to_version(r) if r else None


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionSink (rce.agent_runs + rce.extracted_fields)
# ─────────────────────────────────────────────────────────────────────────────


class SupabaseExtractionSink:
    """ExtractionSink backed by rce.agent_runs + rce.extracted_fields."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def write_agent_run(
        self,
        *,
        agent_run_id: UUID,
        agent_version_id: UUID,
        case_id: Optional[UUID],
        document_id: UUID,  # no column on rce.agent_runs; recovered via extracted_fields
        model_name: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,  # not persisted (no column); cost_tokens is the proxy
        inputs_digest: str,
        output_digest: str,
        started_at: Any,
        finished_at: Any,
        status: str,
    ) -> None:
        self._conn.execute(
            text(
                """INSERT INTO rce.agent_runs
                     (agent_run_id, agent_version_ref, case_id, inputs_digest,
                      output_digest, status, started_at, finished_at,
                      llm_model_used, cost_tokens)
                   VALUES
                     (CAST(:run_id AS UUID), CAST(:vref AS UUID), CAST(:case_id AS UUID),
                      :inputs_digest, :output_digest, :status, :started_at, :finished_at,
                      :model, :cost_tokens)
                   ON CONFLICT (agent_run_id) DO NOTHING"""
            ),
            {
                "run_id": str(agent_run_id),
                "vref": str(agent_version_id),
                "case_id": str(case_id) if case_id is not None else None,
                "inputs_digest": inputs_digest,
                "output_digest": output_digest,
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "model": model_name,
                "cost_tokens": (tokens_in or 0) + (tokens_out or 0),
            },
        )

    def write_extracted_fields(self, fields: Tuple[ExtractedField, ...]) -> None:
        params: List[dict] = [_extracted_field_params(f) for f in fields]
        if not params:
            return
        stmt = text(
            """INSERT INTO rce.extracted_fields
                 (extracted_field_id, document_id, field_key, value_raw, value_canonical,
                  confidence, bbox_page, bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                  agent_run_id, resolution_status, phi_class)
               VALUES
                 (CAST(:extracted_field_id AS UUID), CAST(:document_id AS UUID), :field_key,
                  :value_raw, CAST(:value_canonical AS JSONB), :confidence, :bbox_page,
                  :bbox_x0, :bbox_y0, :bbox_x1, :bbox_y1, CAST(:agent_run_id AS UUID),
                  :resolution_status, :phi_class)"""
        )
        for p in params:
            self._conn.execute(stmt, p)

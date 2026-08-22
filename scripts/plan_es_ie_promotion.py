#!/usr/bin/env python3
"""Produce the ES→IE promotion DRY-RUN plan. Generates; never writes to the database.

There is deliberately no execute path in this file. It reads the committed batch artifact and
emits (a) the exact rows a promotion would insert and (b) the rows it must not touch, as the
artifact a human approves at the gate.

WHY THIS TARGETS `requirement_facts` AND NOT `requirement_items`. Two requirement pipelines
exist. `backend/imports/otto/executor.promote()` writes `public.requirement_items` — that is
the pillar-aware path (#1983), feeding the public corridor endpoint and the rules engine.
The path this batch must reach is the other one: `compute_requirements_sufficiency` reads
`requirement_facts JOIN requirement_entities` (`backend/db/policies.py`
`list_approved_requirement_facts`), and that is what renders in the employee dossier's
RequirementsSufficiencyPanel. So the existing `--promote` tooling does NOT serve this batch,
and the pillar rule does not apply here: `requirement_facts` has no `pillar` column and the
batch's pillar rides inside `applies_to`.

WHY NOT `ON CONFLICT`. `requirement_facts` and `requirement_entities` carry a PRIMARY KEY on a
`gen_random_uuid()` `id` and NO other unique constraint (verified against production
2026-08-22). There is nothing for `ON CONFLICT` to match, so a naive re-run would insert all 38
rows again. Idempotency therefore comes from a DETERMINISTIC id: uuid5 over the natural key, so
re-running writes the same primary key and the insert is refused rather than duplicated.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BATCH = REPO / "docs/imports/es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.ndjson"
NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://relopass.com/ns/requirement_facts")


def entity_id(dest: str, topic_key: str) -> str:
    return str(uuid.uuid5(NS, f"entity:{dest}:{topic_key}"))


def fact_id(dest: str, topic_key: str, fact_key: str) -> str:
    return str(uuid.uuid5(NS, f"fact:{dest}:{topic_key}:{fact_key}"))


def doc_id(url: str) -> str:
    return str(uuid.uuid5(NS, f"doc:{url}"))


def build() -> dict:
    rows = [json.loads(l) for l in BATCH.read_text().splitlines() if l.strip()]
    entities, facts, docs = {}, [], {}
    for r in rows:
        ent = r["entity"]
        dest, topic = ent["destination_country"], ent["topic_key"]
        entities[(dest, topic)] = {
            "id": entity_id(dest, topic),
            "destination_country": dest,
            "topic_key": topic,
            "domain_area": ent.get("domain_area"),
            "title": ent.get("title"),
        }
        docs[r["source_url"]] = {"id": doc_id(r["source_url"]), "source_url": r["source_url"]}
        facts.append({
            "id": fact_id(dest, topic, r["fact_key"]),
            "entity_id": entity_id(dest, topic),
            "source_doc_id": doc_id(r["source_url"]),
            "fact_type": r["fact_type"],
            "fact_key": r["fact_key"],
            "fact_text": r["fact_text"],
            "applies_to": r["applies_to"],
            "required_fields": r.get("required_fields") or [],
            "source_url": r["source_url"],
            "evidence_quote": r["evidence_quote"],
            "confidence": r.get("confidence") or "medium",
            # Explicit, never defaulted. `list_approved_requirement_facts` serves only
            # status='approved', so 'pending' IS the gate: nothing here reaches a mover until
            # a human flips it.
            "status": "pending",
            # Left NULL on purpose. NULL means "never checked", and the dossier renders that as
            # "Source — not independently verified". Writing TRUE here would claim a check
            # nobody performed.
            "evidence_verified": None,
        })
    return {"entities": list(entities.values()), "facts": facts, "docs": list(docs.values())}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, ensure_ascii=False))

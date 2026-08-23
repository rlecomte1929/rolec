#!/usr/bin/env python3
"""Convert the ES→IE third-country batch into the flat shape `read_jsonl` accepts.

The batch as delivered CANNOT BE IMPORTED. `backend/imports/otto/parsers.read_jsonl` fails on
line 1 with `missing required field(s): entity_topic_key`, because the deliverable nests the
entity:

    {"entity": {"destination_country": "IE", "topic_key": "...", "title": "..."}, ...}

while the parser requires `entity_topic_key` and `entity_title` as FLAT top-level keys. The
NO→FR batch uses the flat shape and parses 17/17, so the two artifacts in `docs/imports/` speak
two different vocabularies. This is the same class of failure `convert_ve_ie_to_otto_jsonl.py`
was written for; convert, do not ask for a re-issue.

THIS CONVERTER INVENTS NOTHING. It moves three fields out of a nested object and copies the
rest verbatim. `topic_key` is carried through UNCHANGED, colons and all
(`ES-IE:thirdcountry:ppsn`), because the topic key is the entity's identity: rewriting it here
would silently repoint the facts at a different entity, and the promotion plan in
`docs/promotions/es-ie-thirdcountry-2026-08-22-dry-run.md` already derives its uuid5 entity ids
from these exact strings.

KNOWN LOSS, recorded rather than hidden: `required_fields` is neither required nor optional in
the parser's vocabulary, so it is dropped at import. It is what
`compute_requirements_sufficiency` turns into the dossier's "Details we still need from you",
so a fact promoted through this path arrives without its intake gaps. The field is preserved in
the converted file (it costs nothing to carry) and the loss happens later, in the parser.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "docs/imports/es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.ndjson"
OUT = REPO / "docs/imports/es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.flat.ndjson"

#: Copied across untouched when present.
PASSTHROUGH = (
    "fact_key", "fact_text", "fact_type", "source_url", "evidence_quote",
    "confidence", "applies_to", "required_fields",
)


def to_flat(rec: dict, lineno: int) -> dict:
    entity = rec.get("entity")
    if not isinstance(entity, dict):
        raise SystemExit(f"line {lineno}: expected a nested 'entity' object, got {type(entity).__name__}")
    dest = rec.get("destination_country") or entity.get("destination_country")
    if not dest:
        raise SystemExit(f"line {lineno}: no destination_country on the record or its entity")
    # The nested and top-level destination must agree; a record whose entity points at another
    # country is a data error, not something to silently prefer one side of.
    if rec.get("destination_country") and entity.get("destination_country") \
            and rec["destination_country"] != entity["destination_country"]:
        raise SystemExit(
            f"line {lineno}: destination_country disagrees — record {rec['destination_country']!r} "
            f"vs entity {entity['destination_country']!r}"
        )
    out = {
        "destination_country": dest,
        "entity_topic_key": entity.get("topic_key"),
        "entity_title": entity.get("title"),
    }
    if not out["entity_topic_key"]:
        raise SystemExit(f"line {lineno}: entity carries no topic_key")
    for key in PASSTHROUGH:
        if key in rec:
            out[key] = rec[key]
    return out


def main() -> int:
    rows = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    flat = [to_flat(r, i) for i, r in enumerate(rows, 1)]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in flat))
    print(f"converted {len(flat)} records -> {OUT.relative_to(REPO)}")

    # Prove it against the real parser rather than trusting the shape by eye.
    sys.path.insert(0, str(REPO))
    from backend.imports.otto.parsers import read_jsonl

    parsed, rejects = read_jsonl(OUT, batch_id="es-ie-thirdcountry-requirements-2026-08-22")
    print(f"parser: accepted={len(parsed)} rejected={len(rejects)}")
    for r in rejects:
        print(f"  REJECT: {r}")
    if len(parsed) != len(rows) or rejects:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

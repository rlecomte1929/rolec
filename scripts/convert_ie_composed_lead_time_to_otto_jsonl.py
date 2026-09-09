#!/usr/bin/env python3
"""Convert the composed Ireland permit-then-visa lead-time fact into otto JSONL.

    python scripts/convert_ie_composed_lead_time_to_otto_jsonl.py
    python scripts/convert_ie_composed_lead_time_to_otto_jsonl.py --check

Then (dry-run default — writes nothing to any database):

    python scripts/import_otto_facts.py ie-composed-lead-time-2026-09-09

This batch is one new IRELAND / THIRD_COUNTRY candidate. It does not edit the two source
requirements it cites (DETE 12-week lodgement; ISD sequence + existing ~8-week visa timing).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

BATCH_ID = "ie-composed-lead-time-2026-09-09"
SOURCE = (
    REPO_ROOT / "docs" / "imports" / BATCH_ID / "ie_composed_permit_then_visa_lead_time.ndjson"
)
MANIFEST = REPO_ROOT / "docs" / "imports" / BATCH_ID / "manifest.json"
OUT = REPO_ROOT / "audos-workspace-776786" / "data" / f"{BATCH_ID}.jsonl"

NATIONALITY_BY_CLASS: Dict[str, str] = {
    "THIRD_COUNTRY": "non-EEA",
    "EU_EEA": "EEA",
    "OWN_NATIONAL": "EEA",
}

DETE_URL = (
    "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/"
    "permit-types/critical-skills-employment-permit/"
)
ISD_URL = (
    "https://www.irishimmigration.ie/coming-to-work-in-ireland/what-are-my-work-visa-options/"
    "applying-for-a-long-stay-employment-visa/employment-visa/"
)


def nationality_for(rec: Dict[str, Any]) -> str:
    classes = rec.get("applies_to_nationality_classes") or []
    if not isinstance(classes, list) or not classes:
        raise ValueError(
            f"{rec.get('fact_uid')!r}: no applies_to_nationality_classes — do not guess"
        )
    mapped = {NATIONALITY_BY_CLASS.get(str(c).strip().upper()) for c in classes}
    if None in mapped:
        raise ValueError(
            f"{rec.get('fact_uid')!r}: unrecognised nationality class in {classes!r}"
        )
    if len(mapped) != 1:
        raise ValueError(
            f"{rec.get('fact_uid')!r}: spans several nationality classes {classes!r}"
        )
    return mapped.pop()


def compose_fact_text(rec: Dict[str, Any]) -> str:
    parts: List[str] = [str(rec["fact_text"]).strip()]
    note = rec.get("non_obvious_note") or {}
    if note:
        parts.append(f"Official guidance: {str(note['official_guidance']).strip()}")
        parts.append(f"Actually: {str(note['actual_reality']).strip()}")
        parts.append(f"Action required: {str(note['action_required']).strip()}")
    return "\n\n".join(parts)


def to_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    origin = str(rec["origin_country_code"]).strip().upper()
    dest = str(rec["destination_country_code"]).strip().upper()
    topic_key = str(rec["topic_key"]).strip()
    extras = rec.get("additional_citations") or []
    if isinstance(extras, dict):
        extras = [extras]

    return {
        "destination_country": dest,
        "entity_topic_key": topic_key,
        "fact_key": f"{origin.lower()}_{dest.lower()}_{topic_key}",
        "fact_text": compose_fact_text(rec),
        "source_url": str(rec["source_url"]).strip(),
        "entity_title": (
            "Ireland — sequential permit then visa lead time (approximately 20 weeks)"
        ),
        "fact_type": "deadline",
        "applies_to": {
            "corridor": f"{origin}->{dest}",
            "nationality": nationality_for(rec),
            "status": "professional",
            "fact_uid": str(rec["fact_uid"]).strip(),
            "pillar": str(rec.get("pillar") or "").strip() or None,
            "non_obvious": bool(rec.get("non_obvious")),
            "needs_lawyer_review": bool(rec.get("needs_lawyer_review")),
            "quote_verbatim_confirmed": bool(rec.get("quote_verbatim_confirmed")),
            "source_name": str(rec.get("source_name") or "").strip() or None,
            "batch_id": BATCH_ID,
            "additional_citations": extras,
            "timing": str(rec.get("timing") or "").strip() or None,
        },
        "evidence_quote": str(rec.get("evidence_quote") or "").strip() or None,
        "confidence": "medium",
    }


def source_records() -> List[Dict[str, Any]]:
    return [json.loads(l) for l in SOURCE.read_text(encoding="utf-8").splitlines() if l.strip()]


def build() -> List[Dict[str, Any]]:
    return [to_record(r) for r in source_records()]


def check(records: List[Dict[str, Any]]) -> List[str]:
    problems: List[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = int(manifest["record_count"])
    if len(records) != expected:
        problems.append(f"count {len(records)} != manifest record_count {expected}")

    keys = [(r["destination_country"], r["entity_topic_key"], r["fact_key"]) for r in records]
    if len(keys) != len(set(keys)):
        problems.append("duplicate dedupe_key")

    for rec, out in zip(source_records(), records):
        uid = rec["fact_uid"]
        if rec.get("applies_to_nationality_classes") != ["THIRD_COUNTRY"]:
            problems.append(f"{uid}: must be THIRD_COUNTRY only")
        if out["applies_to"]["nationality"] != "non-EEA":
            problems.append(f"{uid}: nationality {out['applies_to']['nationality']!r}")
        if out["applies_to"].get("status") != "professional":
            problems.append(f"{uid}: status is not professional")
        if out["source_url"] != DETE_URL:
            problems.append(f"{uid}: primary source_url is not the DETE citation")
        extras = out["applies_to"].get("additional_citations") or []
        extra_urls = {str(e.get("url") or "").strip() for e in extras if isinstance(e, dict)}
        if ISD_URL not in extra_urls:
            problems.append(f"{uid}: ISD citation missing from additional_citations")
        text = out["fact_text"]
        for needle in (
            "sequential",
            "20 weeks",
            "12 weeks",
            "8 weeks",
            "does not invent a new statutory 20-week figure",
            "not stated in that row's ISD evidence quote",
        ):
            if needle not in text:
                problems.append(f"{uid}: fact_text missing {needle!r}")
        if str(rec["review_status"]).lower() != "pending":
            problems.append(f"{uid}: review_status must be pending")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    records = build()
    problems = check(records)
    for p in problems:
        print(f"  ✖ {p}")
    if problems:
        print(f"\n✖ {len(problems)} problem(s) — nothing written")
        return 1

    print(f"✓ {len(records)} record(s), THIRD_COUNTRY only, both source citations present")
    if args.check:
        print("\n--check: nothing written")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n→ {OUT.relative_to(REPO_ROOT)}")
    print(f"  stage with: python scripts/import_otto_facts.py {BATCH_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

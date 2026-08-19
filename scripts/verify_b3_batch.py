#!/usr/bin/env python3
"""Re-verify the B3 research batch and regenerate its validation report.

The batch is a set of GCS-delivered NDJSON artifacts that have NOT been loaded into any
database (see docs/imports/B3-facts-enrichment.md for why). This script is the gate that
lets a reviewer trust the committed copies: it re-hashes every artifact, reconciles the
record counts against the batch manifest, and asserts the no-fabrication invariant that
every fact either cites a real source or is explicitly flagged source_missing.

Run:  python3 scripts/verify_b3_batch.py [--write]

Exits non-zero if any gate fails. --write refreshes data/B3/validation_report.json.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import sys

BATCH_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "imports" / "data" / "B3"
REPORT = BATCH_DIR / "validation_report.json"

# Artifact file -> the manifest `artifact` key it must reconcile against.
ARTIFACTS = {
    "corridor_facts.ndjson": "corridor_facts",
    "city_stavanger.ndjson": "city_stavanger",
    "city_copenhagen.ndjson": "city_copenhagen",
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_ndjson(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="rewrite validation_report.json")
    args = ap.parse_args()

    manifest = json.loads((BATCH_DIR / "manifest.json").read_text())
    by_artifact = {f["artifact"]: f for f in manifest["files"]}
    gates: list[dict] = []

    def gate(name: str, ok: bool, detail: str) -> None:
        gates.append({"gate": name, "pass": bool(ok), "detail": detail})

    files_meta: dict[str, dict] = {}
    for fname, key in ARTIFACTS.items():
        path = BATCH_DIR / fname
        rows = read_ndjson(path)
        expected = by_artifact[key]["record_count"]
        gate(f"count:{key}", len(rows) == expected,
             f"{len(rows)} records, manifest declares {expected}")
        files_meta[fname] = {
            "artifact": key,
            "sha256": sha256(path),
            "record_count": len(rows),
            "manifest_record_count": expected,
        }

    facts = read_ndjson(BATCH_DIR / "corridor_facts.ndjson")

    # No-fabrication invariant: a fact is honest if it cites a source OR admits it has none.
    dishonest = [
        f for f in facts
        if not f.get("source_url") and not f.get("source_missing")
    ]
    gate("no_fabrication", not dishonest,
         f"{len(dishonest)} facts with neither source_url nor source_missing=true")

    directions = collections.Counter(f["corridor"] for f in facts)
    declared = by_artifact["corridor_facts"]["by_direction"]
    gate("direction_breakdown", dict(directions) == declared,
         f"{dict(sorted(directions.items()))} vs manifest {declared}")

    # employee_type is a wildcard on this batch; record it rather than inventing a mapping.
    emp_types = sorted({f.get("employee_type") for f in facts})
    gate("employee_type_unambiguous", emp_types == ["all"],
         f"employee_type values present: {emp_types}")

    # Nothing in this batch may carry a served/verified status.
    forbidden = {"live", "verified", "lawyer_verified", "user_verified", "active", "approved"}
    tainted = [
        f for f in facts
        if str(f.get("status", "")).lower() in forbidden
        or str(f.get("verification_state", "")).lower() in forbidden
    ]
    gate("candidate_only", not tainted, f"{len(tainted)} records carry a served status")

    report = {
        "batch": manifest["batch"],
        "manifest_sha256": sha256(BATCH_DIR / "manifest.json"),
        "files": files_meta,
        "totals": {
            "corridor_facts": len(facts),
            "directions": len(directions),
            "enrichment_records": sum(
                files_meta[f]["record_count"] for f in ("city_stavanger.ndjson", "city_copenhagen.ndjson")
            ),
        },
        "provenance": {
            "distinct_source_urls": len({f["source_url"] for f in facts if f.get("source_url")}),
            "source_missing": sum(1 for f in facts if f.get("source_missing")),
            "flagged": sum(1 for f in facts if f.get("flagged")),
        },
        "loaded_into_database": False,
        "target_table": None,
        "gates": gates,
        "all_pass": all(g["pass"] for g in gates),
    }

    if args.write:
        REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    for g in gates:
        print(f"{'PASS' if g['pass'] else 'FAIL'}  {g['gate']}: {g['detail']}")
    print(f"\nall_pass={report['all_pass']}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

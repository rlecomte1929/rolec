#!/usr/bin/env python3
"""Batch gate for the Otto vendor-candidate delivery (2026-09-08).

Re-hashes each committed source artifact against `manifest.json`, reconciles record counts
against Otto's own per-batch manifests, and re-runs the tier gate over the converted CSV so
the pass/reject split in the README can never silently drift from the code. Exit 0 = the
committed batch is exactly what was fetched and the gate result is unchanged.

    python docs/imports/vendor-candidates-2026-09-08/verify_batch.py

A GCS object with no repo record is one bucket cleanup away from gone, and a "verified" count
nobody can diff is not verified — this is the diff.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

EXPECT_PASS = 15
EXPECT_REJECT = 235


def main() -> int:
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    problems = []

    for e in manifest["files"]:
        p = HERE / e["file"]
        if not p.exists():
            problems.append(f"missing artifact: {e['file']}")
            continue
        data = p.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != e["sha256"]:
            problems.append(f"sha256 mismatch: {e['file']}")
        if "record_count" in e:
            n = sum(1 for line in data.decode("utf-8").splitlines() if line.strip())
            if n != e["record_count"]:
                problems.append(f"count drift: {e['file']} {n} != {e['record_count']}")
            if e.get("otto_manifest_count") is not None and n != e["otto_manifest_count"]:
                problems.append(
                    f"reconcile fail: {e['file']} {n} != otto {e['otto_manifest_count']}"
                )

    # Re-run the tier gate over the converted CSV, using the repo's own validate().
    from backend.imports.suppliers.parsers import read_csv
    from backend.app.services.vendor_harvester import validate, HarvestRejected

    npass = nrej = 0
    for cand in read_csv(HERE / "vendor_candidates_all.csv"):
        try:
            validate(cand)
            npass += 1
        except HarvestRejected:
            nrej += 1
    if (npass, nrej) != (EXPECT_PASS, EXPECT_REJECT):
        problems.append(
            f"tier-gate drift: pass/reject = {npass}/{nrej}, "
            f"expected {EXPECT_PASS}/{EXPECT_REJECT}"
        )

    if problems:
        print("✖ batch gate FAILED:")
        for pb in problems:
            print(f"  - {pb}")
        return 1
    print(f"✔ batch gate OK — {len(manifest['files'])} artifacts hash-verified, counts "
          f"reconcile, tier gate {npass} pass / {nrej} reject unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

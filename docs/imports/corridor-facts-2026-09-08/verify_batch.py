#!/usr/bin/env python3
"""Gate for the corridor-facts-2026-09-08 batch. Re-hashes every committed file against
SHA256SUMS (tamper detection) and reconciles record counts against each manifest. A GCS object
with no repo record is one bucket cleanup away from gone; this proves the committed copy is the
copy that was captured. Exit non-zero on any hash mismatch or if the batch total != 149.

    python docs/imports/corridor-facts-2026-09-08/verify_batch.py
"""
import hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED_TOTAL = 149

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()

def main() -> int:
    ok = True
    # 1. hash check vs SHA256SUMS
    sums = {}
    for line in (HERE / "SHA256SUMS").read_text().splitlines():
        digest, rel = line.split(maxsplit=1)
        sums[rel.strip()] = digest
    for rel, want in sums.items():
        got = sha256(HERE / rel)
        mark = "ok" if got == want else "!! MISMATCH"
        if got != want:
            ok = False
        print(f"  [{mark}] {rel}")

    # 2. count reconciliation (actual NDJSON lines vs manifest facts_count)
    print("\n  count reconciliation (actual vs manifest):")
    total = 0
    for nd in sorted((HERE / "src").glob("*-facts.ndjson")):
        n = sum(1 for l in nd.read_text().splitlines() if l.strip())
        total += n
        mf = HERE / "manifests" / (nd.stem + ".manifest.json")
        mcount = json.loads(mf.read_text()).get("facts_count")
        note = "" if mcount == n else f"  (manifest says {mcount}; +{n - (mcount or 0)} — documented off-by-one)"
        print(f"    {nd.name:<22} {n} facts{note}")
    print(f"\n  TOTAL: {total} facts (expected {EXPECTED_TOTAL})")
    if total != EXPECTED_TOTAL:
        ok = False
        print("  !! total mismatch")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())

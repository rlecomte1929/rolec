#!/usr/bin/env python3
"""Offline audit gate for the committed vendor-enrichment batch.

Re-hashes each committed `src/<slice>.ndjson` against its `manifest_<slice>.json`, reconciles the
record count, and asserts every `key` in the NDJSON is present in the exported `target_<slice>.csv`
(so no invented/stray supplier_id can slip in). No DB, no network — it diffs the committed
artifacts, because "a verified count nobody can diff is not verified." Exit 1 on any drift.

    python docs/imports/vendor-enrichment-2026-09-09/gate.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _keys_from_target(path: str) -> set:
    keys = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and line.split("|", 1)[0].strip().lower() not in ("key", "id", ""):
                keys.add(line.split("|", 1)[0].strip())
    return keys


def main() -> int:
    failures = []
    manifests = sorted(glob.glob(os.path.join(HERE, "manifest_*.json")))
    if not manifests:
        print("no manifest_*.json yet (batch awaiting Otto delivery) — nothing to gate")
        return 0
    for man_path in manifests:
        slice_name = os.path.basename(man_path)[len("manifest_"):-len(".json")]
        man = json.load(open(man_path, encoding="utf-8"))
        nd_path = os.path.join(HERE, "src", f"{slice_name}.ndjson")
        if not os.path.exists(nd_path):
            failures.append(f"{slice_name}: src/{slice_name}.ndjson missing"); continue
        raw = open(nd_path, "rb").read()
        rows = [l for l in raw.decode("utf-8", "replace").splitlines() if l.strip()]

        want = man.get("sha256_ndjson") or man.get("sha256")
        got = hashlib.sha256(raw).hexdigest()
        if want and want != got:
            failures.append(f"{slice_name}: sha256 {got[:12]}… != manifest {str(want)[:12]}…")
        rc = man.get("record_count")
        if rc is not None and int(rc) != len(rows):
            failures.append(f"{slice_name}: record_count {rc} != {len(rows)} lines")

        target = os.path.join(HERE, f"target_{slice_name}.csv")
        if os.path.exists(target):
            allowed = _keys_from_target(target)
            stray = []
            for l in rows:
                k = str(json.loads(l).get("key", "")).strip()
                if k not in allowed:
                    stray.append(k)
            if stray:
                failures.append(f"{slice_name}: {len(stray)} key(s) not in target set: {stray[:5]}")
        print(f"  {slice_name}: sha256 {got[:12]}…, {len(rows)} rows"
              + (f", keys ⊆ target({len(allowed)})" if os.path.exists(target) else ""))

    if failures:
        print("\n✖ GATE FAILED:")
        for f in failures:
            print("   -", f)
        return 1
    print("\n✓ gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

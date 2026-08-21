#!/usr/bin/env python3
"""Gate for the `ve-ie-entry-family-2026-08-20` batch: re-hash, reconcile, re-convert.

    ./.venv311/bin/python scripts/check_ve_ie_batch.py

Exits non-zero on any failure. Runs no database query and writes nothing, so it is safe in
CI and safe to re-run.

A GCS object with no repo record is one bucket cleanup away from gone, and a "verified" fact
nobody can diff is not verified — so this re-derives every number the batch doc claims rather
than trusting the prose. Three independent things are checked:

1. **Integrity** — the artifact still hashes to the sha256 the manifest declares. A silent
   edit to the NDJSON is the failure this catches; the batch doc's counts would still read
   fine.
2. **Reconciliation** — record count, non-obvious count and needs-lawyer-review count all
   agree with the manifest exactly. A discrepancy is the batch's problem to explain.
3. **Conversion** — every row survives `convert_ve_ie_to_otto_jsonl.build()` and then parses
   through the real `read_jsonl` reader with zero rejections. This is the gate the deliverable
   failed as originally delivered.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.otto.parsers import UNOFFICIAL, read_jsonl  # noqa: E402

BATCH_ID = "ve-ie-entry-family-2026-08-20"
BATCH_DIR = REPO_ROOT / "docs" / "imports" / BATCH_ID
NDJSON = BATCH_DIR / "ve_ie_entry_family_requirement_facts.ndjson"
MANIFEST = BATCH_DIR / "manifest.json"

_SCRIPT = REPO_ROOT / "scripts" / "convert_ve_ie_to_otto_jsonl.py"
_spec = importlib.util.spec_from_file_location("convert_ve_ie_to_otto_jsonl", _SCRIPT)
assert _spec and _spec.loader
convert = importlib.util.module_from_spec(_spec)
sys.modules["convert_ve_ie_to_otto_jsonl"] = convert
_spec.loader.exec_module(convert)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    failures: List[str] = []

    for path in (NDJSON, MANIFEST):
        if not path.is_file():
            print(f"✖ missing artifact: {path.relative_to(REPO_ROOT)}")
            return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # 1. integrity
    actual = sha256(NDJSON)
    declared = str(manifest["sha256"]).strip()
    if actual == declared:
        print(f"✓ sha256 matches manifest: {actual[:16]}…")
    else:
        failures.append(f"sha256 {actual} != manifest {declared}")

    # 2. reconciliation
    records = [json.loads(l) for l in NDJSON.read_text(encoding="utf-8").splitlines() if l.strip()]
    checks = {
        "record_count": (len(records), int(manifest["record_count"])),
        "non_obvious_count": (
            sum(1 for r in records if r.get("non_obvious")),
            int(manifest["non_obvious_count"]),
        ),
        "needs_lawyer_review_count": (
            sum(1 for r in records if r.get("needs_lawyer_review")),
            int(manifest["needs_lawyer_review_count"]),
        ),
    }
    for name, (got, want) in checks.items():
        if got == want:
            print(f"✓ {name}: {got}")
        else:
            failures.append(f"{name}: artifact has {got}, manifest declares {want}")

    # Candidates only. A row arriving already approved would publish unreviewed immigration
    # content the moment anything promoted it.
    forbidden = {"approved", "verified", "lawyer_verified", "live", "expert_verified"}
    bad = [r["fact_uid"] for r in records if str(r.get("review_status", "")).lower() in forbidden]
    if bad:
        failures.append(f"review_status must be a candidate state, not: {bad}")
    else:
        print(f"✓ every row review_status='pending' — candidates only")

    # 3. conversion + the real reader
    try:
        converted = convert.build()
        problems = convert.check(converted)
        if problems:
            failures.extend(problems)
        tmp = Path(tempfile.mkdtemp()) / f"{BATCH_ID}.jsonl"
        tmp.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in converted) + "\n",
            encoding="utf-8",
        )
        rows, rejections = read_jsonl(tmp, batch_id=BATCH_ID)
        if rejections:
            failures.extend(f"reader rejected: {r}" for r in rejections)
        elif len(rows) != len(records):
            failures.append(f"reader parsed {len(rows)} of {len(records)} rows")
        else:
            print(f"✓ all {len(rows)} rows parse through read_jsonl with 0 rejections")
        for row in rows:
            if row.source_class == UNOFFICIAL:
                failures.append(f"{row.dedupe_key}: source scored UNOFFICIAL")
        tiers = {}
        for row in rows:
            tiers[row.accuracy_tier] = tiers.get(row.accuracy_tier, 0) + 1
        print(f"  accuracy tiers: {tiers}")
        # AIQ-2034 made this a hard failure rather than the warning it used to print.
        # `grade()` now downgrades any row carrying `quote_verbatim_confirmed: false`, so a row
        # that still reaches `auto_accepted` means the guard regressed — and a reviewer would
        # read that badge on a counsel-flagged row as "already cleared".
        unconfirmed_auto = [
            row.dedupe_key
            for row in rows
            if row.accuracy_tier == "auto_accepted"
            and (row.applies_to or {}).get("quote_verbatim_confirmed") is False
        ]
        for key in unconfirmed_auto:
            failures.append(
                f"{key}: auto_accepted despite quote_verbatim_confirmed=false — the "
                "grade() guard has regressed"
            )
        if not unconfirmed_auto:
            print("✓ no unconfirmed-quote row scored auto_accepted")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"conversion failed: {exc}")

    if failures:
        print(f"\n✖ {len(failures)} failure(s):")
        for f in failures:
            print(f"    - {f}")
        return 1
    print(f"\n✔ batch {BATCH_ID} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

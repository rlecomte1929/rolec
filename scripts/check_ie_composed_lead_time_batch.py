#!/usr/bin/env python3
"""Gate for `ie-composed-lead-time-2026-09-09`: re-hash, reconcile, re-convert.

    python scripts/check_ie_composed_lead_time_batch.py

Exits non-zero on any failure. Runs no database query and writes nothing.
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

from backend.imports.otto.mappings import NATIONALITY_CLASSES  # noqa: E402
from backend.imports.otto.parsers import UNOFFICIAL, read_jsonl  # noqa: E402

BATCH_ID = "ie-composed-lead-time-2026-09-09"
BATCH_DIR = REPO_ROOT / "docs" / "imports" / BATCH_ID
NDJSON = BATCH_DIR / "ie_composed_permit_then_visa_lead_time.ndjson"
MANIFEST = BATCH_DIR / "manifest.json"

_SCRIPT = REPO_ROOT / "scripts" / "convert_ie_composed_lead_time_to_otto_jsonl.py"
_spec = importlib.util.spec_from_file_location("convert_ie_composed_lead_time", _SCRIPT)
assert _spec and _spec.loader
convert = importlib.util.module_from_spec(_spec)
sys.modules["convert_ie_composed_lead_time"] = convert
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
    actual = sha256(NDJSON)
    declared = str(manifest["sha256"]).strip()
    if actual == declared:
        print(f"✓ sha256 matches manifest: {actual[:16]}…")
    else:
        failures.append(f"sha256 {actual} != manifest {declared}")

    records = [json.loads(l) for l in NDJSON.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(records) != int(manifest["record_count"]):
        failures.append(
            f"record_count: artifact has {len(records)}, manifest declares "
            f"{manifest['record_count']}"
        )
    else:
        print(f"✓ record_count: {len(records)}")

    forbidden = {"approved", "verified", "lawyer_verified", "live", "expert_verified"}
    bad = [r["fact_uid"] for r in records if str(r.get("review_status", "")).lower() in forbidden]
    if bad:
        failures.append(f"review_status must be a candidate state, not: {bad}")
    else:
        print("✓ every row review_status='pending' — candidates only")

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
            mapped = NATIONALITY_CLASSES.get((row.applies_to or {}).get("nationality") or "")
            if mapped != ["THIRD_COUNTRY"]:
                failures.append(
                    f"{row.dedupe_key}: converter nationality does not map to THIRD_COUNTRY "
                    f"only ({mapped!r})"
                )
            extras = (row.applies_to or {}).get("additional_citations") or []
            if not extras:
                failures.append(f"{row.dedupe_key}: additional_citations dropped by reader")
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

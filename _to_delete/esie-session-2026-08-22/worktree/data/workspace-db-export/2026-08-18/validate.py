#!/usr/bin/env python3
"""Offline integrity check for the 2026-08-18 ReloPass WorkspaceDB snapshot.

Re-verifies every file in this directory against MANIFEST.json:
  * sha256 of the bytes on disk
  * byte size
  * JSON parses, and len(rows) matches the manifest
    (per-file partRowCount for split files; parts sum to the table rowCount)
  * ids are unique within each table that has an `id` field

The two PII tables (persons, person_identities) live in the git-ignored `_pii/`
subdirectory, so a fresh clone does not have them. They are verified normally
when present and reported as POLICY-SKIP when absent. Absence is only tolerated
for those two: any OTHER missing file is still a hard FAIL.

Usage:  python3 validate.py            (run from anywhere)
Exit code 0 only when every table passes.

Stdlib only — json, hashlib, pathlib. No network access, no dependencies.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "MANIFEST.json"

#: Tables deliberately kept out of git (personal data). Their files live in the
#: git-ignored `_pii/` subdirectory. Absence here is policy, not corruption --
#: but ONLY for these two, and only when the file is genuinely not on disk.
PII_TABLES = {"persons", "person_identities"}
PII_DIR = HERE / "_pii"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_table(entry):
    """Return (ok, [problem, ...]) for one manifest table entry."""
    problems = []
    files = entry["files"]
    split = len(files) > 1
    rows_seen = 0
    ids = []
    has_id = False

    for meta in files:
        name = meta["file"]
        is_pii = entry["table"] in PII_TABLES
        path = (PII_DIR if is_pii else HERE) / name

        if not path.exists():
            if is_pii:
                # Expected on any clone: the file is git-ignored by policy.
                # Still not a silent pass -- the caller reports it as POLICY-SKIP
                # and excludes its rows from the verified total.
                return None, [], 0
            problems.append(f"{name}: missing from this directory")
            continue

        actual_bytes = path.stat().st_size
        if actual_bytes != meta["bytes"]:
            problems.append(
                f"{name}: size {actual_bytes} != manifest {meta['bytes']}"
            )

        actual_sha = sha256_of(path)
        if actual_sha != meta["sha256"]:
            problems.append(
                f"{name}: sha256 {actual_sha} != manifest {meta['sha256']}"
            )
            # A hash mismatch makes every downstream check meaningless.
            continue

        try:
            with open(path, "rb") as fh:
                doc = json.load(fh)
        except Exception as exc:  # noqa: BLE001 - report any parse failure verbatim
            problems.append(f"{name}: JSON parse failed: {exc}")
            continue

        rows = doc.get("rows")
        if not isinstance(rows, list):
            problems.append(f"{name}: `rows` is not a list")
            continue

        # Per-file row count: split files declare partRowCount; whole files
        # declare the table's rowCount.
        expected_here = doc.get("partRowCount") if split else doc.get("rowCount")
        if expected_here is None:
            problems.append(
                f"{name}: no {'partRowCount' if split else 'rowCount'} in file"
            )
        elif len(rows) != expected_here:
            problems.append(
                f"{name}: {len(rows)} rows != declared {expected_here}"
            )

        if doc.get("rowCount") != entry["rowCount"]:
            problems.append(
                f"{name}: file rowCount {doc.get('rowCount')} != manifest "
                f"{entry['rowCount']}"
            )
        if doc.get("table") != entry["table"]:
            problems.append(
                f"{name}: file table {doc.get('table')!r} != manifest "
                f"{entry['table']!r}"
            )

        rows_seen += len(rows)
        for row in rows:
            if isinstance(row, dict) and "id" in row:
                has_id = True
                ids.append(row["id"])

    # Parts must concatenate to the whole table.
    if rows_seen != entry["rowCount"]:
        problems.append(
            f"total rows {rows_seen} != manifest rowCount {entry['rowCount']}"
        )

    # Uniqueness only applies to tables that actually carry an id
    # (`employee_types` has no id column at all).
    if has_id and len(set(ids)) != len(ids):
        dupes = sorted({str(i) for i in ids if ids.count(i) > 1})[:5]
        problems.append(
            f"duplicate ids ({len(ids) - len(set(ids))}): {', '.join(dupes)}"
        )

    return (not problems), problems, rows_seen


def main():
    if not MANIFEST.exists():
        print(f"FAIL: {MANIFEST} not found")
        return 1

    manifest = json.loads(MANIFEST.read_text())
    tables = manifest["tables"]

    passed = failed = skipped = 0
    total_rows = 0
    total_files = 0
    skipped_rows = 0
    empty_tables = 0
    all_problems = []

    for entry in sorted(tables, key=lambda t: t["table"]):
        ok, problems, rows_seen = check_table(entry)
        if ok is None:
            # PII table, git-ignored and not on disk. Reported, never hidden.
            skipped += 1
            skipped_rows += entry["rowCount"]
            files = ", ".join(f["file"] for f in entry["files"])
            print(f"SKIP  {entry['table']:<34} {entry['rowCount']:>6} rows  "
                  f"{files}  (git-ignored _pii/, not on disk)")
            continue
        total_files += len(entry["files"])
        total_rows += rows_seen
        if entry["rowCount"] == 0:
            empty_tables += 1
        status = "PASS" if ok else "FAIL"
        files = ", ".join(f["file"] for f in entry["files"])
        print(f"{status}  {entry['table']:<34} {rows_seen:>6} rows  {files}")
        for problem in problems:
            print(f"        !! {problem}")
            all_problems.append(f"{entry['table']}: {problem}")
        passed += ok
        failed += not ok

    print()
    print(f"manifest exported_at : {manifest['exported_at']}")
    print(f"tables               : {passed} pass, {failed} fail, "
          f"{skipped} skipped "
          f"(manifest totalTables {manifest['totalTables']})")
    print(f"files verified       : {total_files}")
    print(f"rows verified        : {total_rows}")
    if skipped:
        print(f"rows in _pii/        : {skipped_rows} "
              f"(personal data, git-ignored -- verified only when present)")
    print(f"rows total           : {total_rows + skipped_rows} "
          f"(manifest totalRows {manifest['totalRows']})")
    print(f"empty tables         : {empty_tables} "
          f"(manifest emptyTables {len(manifest['emptyTables'])})")

    # The reconciliation still has to close: verified rows plus the rows we
    # knowingly skipped must equal the manifest total, or something is missing
    # that policy does not explain.
    if total_rows + skipped_rows != manifest["totalRows"]:
        all_problems.append(
            f"row total {total_rows + skipped_rows} != manifest "
            f"{manifest['totalRows']}"
        )
    if len(tables) != manifest["totalTables"]:
        all_problems.append(
            f"table count {len(tables)} != manifest {manifest['totalTables']}"
        )

    if all_problems:
        print(f"\nRESULT: FAIL ({len(all_problems)} problem(s))")
        return 1
    if skipped:
        print(f"\nRESULT: PASS — {passed} tables verified against MANIFEST.json; "
              f"{skipped} PII table(s) git-ignored and not on disk")
    else:
        print("\nRESULT: PASS — all tables verified against MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

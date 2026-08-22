#!/usr/bin/env python3
"""Re-hash the artifacts and reconcile every declared count. Exit 1 on any failure.

A batch whose numbers nobody can re-derive is not verified. This re-reads the files from
disk rather than trusting the manifest's own summary.
"""
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
FAIL: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        FAIL.append(label)


def main() -> int:
    manifest = json.loads((HERE / "manifest.json").read_text())
    data = json.loads((HERE / "isd_visa_required_map.json").read_text())

    print("file integrity")
    for entry in manifest.get("files", []):
        # the manifest names the artifact by its Otto-side filename; the map was renamed on
        # landing to avoid colliding with the shipped lookup of the same name.
        name = entry.get("name") or entry.get("path")
        local = HERE / ("isd_visa_required_map.json" if name == "isd_visa_required.json" else name)
        blob = local.read_bytes()
        declared_bytes = entry.get("bytes", entry.get("size_bytes"))
        check(f"{local.name} sha256", hashlib.sha256(blob).hexdigest() == entry.get("sha256"))
        check(f"{local.name} length", declared_bytes == len(blob), f"{len(blob)} bytes")

    print("count reconciliation")
    counts = manifest["counts"]
    vr = data["visa_required"]
    unmapped = data["unmapped_entries"]
    true_n = sum(1 for v in vr.values() if v is True)
    false_n = sum(1 for v in vr.values() if v is False)

    check("entries_mapped_to_iso2", counts["entries_mapped_to_iso2"] == len(vr) == len(data["entries"]))
    check("entries_unmapped", counts["entries_unmapped"] == len(unmapped))
    check("visa_required_true", counts["visa_required_true"] == true_n, str(true_n))
    check("visa_required_false", counts["visa_required_false"] == false_n, str(false_n))
    check("isd_rows_total == mapped + unmapped", counts["isd_rows_total"] == len(vr) + len(unmapped))
    check("every determination is a bool", all(isinstance(v, bool) for v in vr.values()))

    print("temporary-determination discipline")
    temp = [r for r in unmapped if r.get("determination_is_temporary")]
    check("a temporary row is flagged", len(temp) >= 1)
    for row in temp:
        prov = row.get("temporary_provision", {})
        check("no expiry inferred", prov.get("expiry_determinable_from_source") is False,
              row.get("isd_nationality_label", ""))

    if FAIL:
        print(f"\nFAILED: {len(FAIL)} check(s): {', '.join(FAIL)}")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

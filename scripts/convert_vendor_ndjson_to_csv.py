#!/usr/bin/env python3
"""Convert an Otto vendor-candidate NDJSON file to the harvest CSV the importer reads.

Otto's flywheel batches (Paris/Oslo, Madrid/Dublin, …) are NDJSON. The existing reader
``backend/imports/suppliers/parsers.py::read_csv`` only accepts the nine-column header in
``EXPECTED_HEADER``. This is the adapter: one CSV row per ORIGIN-DEST corridor pair, no
invented accreditation, and a report of evidence domains that ``_DOMAIN_TO_SOURCE`` does
not yet know (those become SELF_DECLARED / tier-3 and the harvester rejects them).

    python scripts/convert_vendor_ndjson_to_csv.py in.ndjson --out out.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.suppliers.parsers import (  # noqa: E402
    EXPECTED_HEADER,
    SELF_DECLARED,
    source_for_url,
)

#: Otto writes "FR-NO,NO-FR", "FR↔DE", "ES-IE,IE-ES". The CSV corridor must be a single
#: ORIGIN-DEST token — parsers._dest_iso_from_corridor takes the second half of the first
#: separator it finds, so "FR-NO,NO-FR" would try to parse "NO,NO-FR" as an ISO code.
_PAIR = re.compile(
    r"\b([A-Za-z]{2})\s*(↔|->|→|—|–|-)\s*([A-Za-z]{2})\b"
)
_BIDIRECTIONAL = frozenset({"↔"})


class ConvertError(ValueError):
    """A file or record that cannot be turned into the harvest CSV."""


def _cell(rec: Dict[str, Any], *keys: str) -> str:
    """First non-empty string among keys. Null / 'null' / 'none' are empty — never invented."""
    for key in keys:
        raw = rec.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text and text.lower() not in ("null", "none"):
            return text
    return ""


def corridor_pairs(raw: str, *, country: str = "") -> List[str]:
    """ORIGIN-DEST tokens from Otto's free-text corridor field.

    When ``country`` is a two-letter ISO, keep only pairs whose destination is that country
    so parsers._dest_iso_from_corridor (token 2) matches the vendor's market. If that filter
    would drop every pair, keep all of them rather than inventing a corridor.
    """
    pairs: List[str] = []
    seen: Set[str] = set()

    def add(origin: str, dest: str) -> None:
        token = f"{origin}-{dest}"
        if token not in seen:
            seen.add(token)
            pairs.append(token)

    for match in _PAIR.finditer(raw or ""):
        origin, sep, dest = match.group(1).upper(), match.group(2), match.group(3).upper()
        add(origin, dest)
        if sep in _BIDIRECTIONAL:
            add(dest, origin)
    iso = (country or "").strip().upper()
    if len(iso) == 2:
        dest_matched = [p for p in pairs if p.split("-", 1)[1] == iso]
        if dest_matched:
            return dest_matched
    return pairs


def evidence_url(rec: Dict[str, Any]) -> str:
    """Registry page if Otto cited one; otherwise the research source_url.

    parsers.source_for_url keys off this URL's domain, not source_name. Prefer
    accreditation_source_url so a company homepage in source_url does not hide a register.
    """
    return _cell(rec, "accreditation_source_url", "source_url")


def csv_row(rec: Dict[str, Any], corridor: str) -> Dict[str, str]:
    return {
        "corridor": corridor,
        "service_category": _cell(rec, "service_category", "category"),
        "company_name": _cell(rec, "company_name", "name", "vendor_name", "provider_name"),
        "website_url": _cell(rec, "website_url", "website"),
        "source_name": _cell(rec, "source_name"),
        "source_url": evidence_url(rec),
        # Absent means blank. Do not copy a number from notes, legal_name, or external_id.
        "accreditation_body": _cell(rec, "accreditation_body"),
        "accreditation_number": _cell(rec, "accreditation_number"),
        "accreditation_expiry": _cell(rec, "accreditation_expiry"),
    }


def records_from_ndjson(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                rec = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ConvertError(f"{path}:{lineno}: invalid JSON — {exc}") from exc
            if not isinstance(rec, dict):
                raise ConvertError(f"{path}:{lineno}: expected an object, got {type(rec).__name__}")
            rows.append(rec)
    return rows


def convert_record(rec: Dict[str, Any]) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """CSV rows for one Otto record, plus a skip reason if it produces none."""
    pairs = corridor_pairs(_cell(rec, "corridor"), country=_cell(rec, "country"))
    if not pairs:
        return [], "no ORIGIN-DEST corridor token"
    name = _cell(rec, "company_name", "name", "vendor_name", "provider_name")
    if not name:
        return [], "no company_name"
    return [csv_row(rec, corridor) for corridor in pairs], None


def unknown_source_domain(url: str) -> Optional[str]:
    """Host of an evidence URL that parsers will treat as SELF_DECLARED, else None."""
    if not url.strip():
        return None
    if source_for_url(url).name != SELF_DECLARED:
        return None
    from urllib.parse import urlsplit

    raw = url.strip()
    if "//" not in raw:
        raw = "//" + raw
    host = (urlsplit(raw).hostname or "").lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def convert(records: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    """Return (csv_rows, unknown_domains sorted, skip notes)."""
    rows: List[Dict[str, str]] = []
    unknown: Set[str] = set()
    skips: List[str] = []
    for i, rec in enumerate(records, start=1):
        converted, skip = convert_record(rec)
        if skip:
            label = _cell(rec, "name", "company_name", "external_id") or f"record {i}"
            skips.append(f"{label}: {skip}")
            continue
        rows.extend(converted)
        host = unknown_source_domain(converted[0]["source_url"])
        if host:
            unknown.add(host)
    return rows, sorted(unknown), skips


def write_csv(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXPECTED_HEADER, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in EXPECTED_HEADER})


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ndjson", type=Path, help="Otto vendor NDJSON (one JSON object per line)")
    ap.add_argument("--out", type=Path, required=True, help="harvest CSV (EXPECTED_HEADER)")
    args = ap.parse_args(argv)

    if not args.ndjson.exists():
        print(f"✖ no such file: {args.ndjson}", file=sys.stderr)
        return 2

    try:
        records = records_from_ndjson(args.ndjson)
        rows, unknown, skips = convert(records)
    except ConvertError as exc:
        print(f"✖ {exc}", file=sys.stderr)
        return 2

    write_csv(args.out, rows)
    print(f"wrote {len(rows)} row(s) from {len(records)} record(s) → {args.out}")
    if skips:
        print(f"skipped {len(skips)} record(s):", file=sys.stderr)
        for note in skips:
            print(f"  - {note}", file=sys.stderr)
    if unknown:
        print(
            "unknown source domains (not in parsers._DOMAIN_TO_SOURCE — "
            "SELF_DECLARED / rejected until the applier extends the map):",
            file=sys.stderr,
        )
        for host in unknown:
            print(f"  - {host}", file=sys.stderr)
    else:
        print("unknown source domains: (none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

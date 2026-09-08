#!/usr/bin/env python3
"""Convert Otto vendor-candidate NDJSON into the 9-column harvest CSV.

Otto delivers vendor candidates as NDJSON on GCS (see `docs/imports/OTTO_BACKLOG.md` §A2).
`scripts/import_supplier_candidates.py` reads only the CSV shape declared by
`backend/imports/suppliers/parsers.py::EXPECTED_HEADER`. This is the bridge between the two.

It is a pure text transform: every output field comes verbatim from the record, except the
two derivations below, both of which are recorded rather than invented.

**corridor** — the batch records carry a multi-corridor / arrow string
(``"NO-GB,GB-NO"``, ``"IT↔DE"``, ``"FR↔DE, ES↔DE, NO↔DE"``) that the parser cannot read; it
wants one ``ORIGIN-DEST`` code. A supplier's capability is scoped to the DESTINATION country,
which is the country the vendor operates in (``record.country``). So we emit the in-scope
corridor whose destination token equals ``record.country`` (``FR`` → ``NO-FR``, ``NO`` →
``FR-NO``, ``IE`` → ``ES-IE``, ``DE`` → ``FR-DE``), falling back to the ``XX-<ISO>``
destination-coverage pseudo-corridor for the rest (``IT`` → ``XX-IT``). ``_dest_iso_from_corridor``
then recovers the country_code from the second token, so the capability scopes correctly.

**source_url** — passed through verbatim. It is NOT substituted with the vendor's website or
with ``accreditation_source_url``: the whole point of the tier gate in ``parsers.py`` /
``vendor_harvester.validate()`` is that a row whose only evidence is the provider's own site
(or an aggregator) is SELF_DECLARED tier-3 and must reject onto the re-sourcing worklist. If
Otto recorded no registry evidence URL, laundering one in here would defeat the gate. A blank
``source_url`` also passes through blank (validate() rejects it, correctly).

**accreditation_expiry** — the NDJSON carries no expiry field, so this column is ALWAYS blank.
A date is never invented; `coerce_expiry` in the parser turns blank into NULL.

Usage:

    python scripts/convert_vendor_ndjson_to_csv.py OUT.csv IN1.ndjson [IN2.ndjson ...]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.requirements_country_key import to_iso_alpha2  # noqa: E402
from backend.imports.suppliers.parsers import EXPECTED_HEADER  # noqa: E402

#: Destination country ISO-2 -> the in-scope corridor whose second token is that country.
#: These are the corridors already declared in `registry_sources.CORRIDORS`; a vendor country
#: not listed here falls back to the `XX-<ISO>` destination-coverage form, which is also in
#: CORRIDORS for the coverage-master destinations.
_DEST_TO_CORRIDOR: Dict[str, str] = {
    "FR": "NO-FR",
    "NO": "FR-NO",
    "IE": "ES-IE",
    "DE": "FR-DE",
    "SG": "FR-SG",
    "EC": "US-EC",
}


def corridor_for(country: Optional[str]) -> str:
    """The single ORIGIN-DEST corridor for a vendor operating in `country`."""
    iso = to_iso_alpha2(country or "")
    if not iso:
        return ""
    return _DEST_TO_CORRIDOR.get(iso, f"XX-{iso}")


def _row(rec: dict) -> Dict[str, str]:
    return {
        "corridor": corridor_for(rec.get("country")),
        "service_category": (rec.get("category") or "").strip(),
        "company_name": (rec.get("name") or "").strip(),
        "website_url": (rec.get("website") or "").strip(),
        "source_name": (rec.get("source_name") or "").strip(),
        "source_url": (rec.get("source_url") or "").strip(),
        "accreditation_body": (rec.get("accreditation_body") or "").strip(),
        "accreditation_number": (rec.get("accreditation_number") or "").strip()
        if rec.get("accreditation_number") is not None else "",
        "accreditation_expiry": "",  # never invented — the NDJSON carries no expiry
    }


def convert(out_csv: Path, ndjson_paths: List[Path]) -> int:
    seen_ids = set()
    rows: List[Dict[str, str]] = []
    dupes = 0
    for p in ndjson_paths:
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            ext = rec.get("external_id")
            if ext and ext in seen_ids:
                dupes += 1
                continue
            if ext:
                seen_ids.add(ext)
            rows.append(_row(rec))
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXPECTED_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} row(s) to {out_csv}"
          + (f"  ({dupes} duplicate external_id(s) skipped)" if dupes else ""))
    return len(rows)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    out_csv = Path(sys.argv[1])
    ndjson_paths = [Path(a) for a in sys.argv[2:]]
    for p in ndjson_paths:
        if not p.exists():
            print(f"✖ no such file: {p}")
            return 2
    convert(out_csv, ndjson_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

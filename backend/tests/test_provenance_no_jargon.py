"""Wave 1 P2 — HR-facing readiness/compliance copy must not leak internal artifacts.

The audit found provenance microcopy shown to HR users referencing internal
filenames and developer concepts ("mobility_rules.json", "assignment profile
JSON", "template store, migrations", "apply DB migrations"). Source-inspection
guard so the plain-language rewrites can't silently regress.
"""
from __future__ import annotations

import glob
import json
import os
import re
from typing import Any, Iterator

# Any "<name>.json" token in a rendered value is an internal-artifact leak.
_INTERNAL_FILENAME = re.compile(r"\.json\b", re.IGNORECASE)


def _backend_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend")


def _read(rel: str) -> str:
    with open(os.path.join(_backend_dir(), rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _iter_strings(obj: Any) -> Iterator[str]:
    """Yield every string value reachable in a nested dict/list structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


_BANNED = [
    "mobility_rules.json",
    "assignment profile JSON",
    "template store, migrations",
    "apply DB migrations",
]


def test_readiness_view_has_no_internal_jargon():
    src = _read("hr_case_readiness_view.py")
    for bad in _BANNED:
        assert bad not in src, f"HR-facing readiness copy still leaks: {bad!r}"


def test_provenance_catalog_has_no_internal_filenames():
    src = _read("provenance_catalog.py")
    assert "mobility_rules.json" not in src


def test_seed_data_values_have_no_internal_filenames():
    """No rendered seed value may carry an internal filename (e.g. 'mobility_rules.json').
    Scans every value in backend/seed_data/*.json (AIQ-1315 — extends the guard to seed_data)."""
    seed_files = glob.glob(os.path.join(_backend_dir(), "seed_data", "*.json"))
    assert seed_files, "no seed_data/*.json files found — path drift?"
    for path in seed_files:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for s in _iter_strings(data):
            assert not _INTERNAL_FILENAME.search(s), (
                f"{os.path.basename(path)} leaks an internal filename: {s!r}"
            )


def test_enriched_compliance_report_has_no_internal_filenames():
    """The enriched compliance report (built from the seed rule pack) must not surface an
    internal filename in any field — source_title / rule_pack_title / rationale_legal_safety."""
    from backend import provenance_catalog

    report = {
        "checks": [{"id": "c1", "status": "COMPLIANT", "title": "Housing cap"}],
        "actions": ["Confirm lease"],
        "overallStatus": "COMPLIANT",
    }
    enriched = provenance_catalog.enrich_assignment_compliance_report(
        report, assignment_id="probe-assignment", profile_present=True
    )
    for s in _iter_strings(enriched):
        assert not _INTERNAL_FILENAME.search(s), f"enriched report leaks an internal filename: {s!r}"

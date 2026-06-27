"""Wave 1 P2 — HR-facing readiness/compliance copy must not leak internal artifacts.

The audit found provenance microcopy shown to HR users referencing internal
filenames and developer concepts ("mobility_rules.json", "assignment profile
JSON", "template store, migrations", "apply DB migrations"). Source-inspection
guard so the plain-language rewrites can't silently regress.
"""
from __future__ import annotations

import os


def _read(rel: str) -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    with open(os.path.join(root, "backend", rel), "r", encoding="utf-8") as fh:
        return fh.read()


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

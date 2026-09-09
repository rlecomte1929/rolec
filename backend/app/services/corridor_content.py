"""
corridor_content.py — a PURE loader for the curated multi-country export corpus.

Reads the NDJSON files under ``data/corridor-content/<ISO>.ndjson`` (Otto's Multi-Country Export
deliverable: one record per curated relocation step, carrying its authority, official portal,
deadline offset, responsible party and the 4-part non-obvious contrast framework). Used as the
FALLBACK render source when a case's destination has no authored data-sheet ``form_template``.

Deliberately dependency-free — ``json`` + ``pathlib`` only — so it can be imported by the
serving-root ``data_sheet_service`` without widening the LLM-isolation closure.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

# backend/app/services/corridor_content.py → parents[3] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DIR = _REPO_ROOT / "data" / "corridor-content"


def _path(country_iso: str) -> Path:
    return _DIR / f"{(country_iso or '').upper()}.ndjson"


def has_corridor_content(country_iso: str) -> bool:
    """True when a curated corridor-content file exists for this destination ISO."""
    return bool(country_iso) and _path(country_iso).is_file()


def load_corridor_content(country_iso: str) -> List[Dict[str, Any]]:
    """Parse ``<ISO>.ndjson`` into a list of records. Missing file → empty list; a malformed
    line is skipped rather than failing the whole load (a preview sheet degrades gracefully)."""
    p = _path(country_iso)
    if not p.is_file():
        return []
    records: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    return records

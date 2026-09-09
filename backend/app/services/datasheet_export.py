"""
datasheet_export.py — Document Data Sheet export (Phase 3): the sheet-PDF renderer.

Turns a case's data sheet into a downloadable artifact. Today that is the print-grade
`render_data_sheet` PDF (the deliverable for corridors with no fillable government form — FR→NO,
DE). The CSV export is client-side (see frontend/src/features/datasheet/datasheetCsv.ts).

**Multi-country scaffold (Otto's Multi-Country Datasheet Export methodology).** The export is
data-driven so "add a country" stays data-only:
  * `data/export-channels.json`      — country_iso → channel (acroform | data_sheet | portal_only)
  * `data/export-schema.json`        — the sections + render_columns layout (consult last)
  * `data/corridor-content/{ISO}.ndjson` — per-country section/step content
Those files land from Otto (via GCS). Until they do, the loaders below degrade to safe defaults
(channel = data_sheet, i.e. render_data_sheet), so the export works now and gains per-country
routing/content as the data drops in. NOT a serving root — this is a rendering/export path.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text as _sql_text

from .case_service import _pg_table
from .data_sheet_service import _as_json
from .data_sheet_pdf import render_data_sheet
from ...database import db as main_db

logger = logging.getLogger(__name__)

# Export channels — how a country's official deliverable is produced.
CHANNEL_ACROFORM = "acroform"       # a fillable government AcroForm (form_prefill_service)
CHANNEL_DATA_SHEET = "data_sheet"   # a print-grade personal data sheet (render_data_sheet)
CHANNEL_PORTAL_ONLY = "portal_only" # portal-only; the sheet is a carry-along reference

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _REPO_ROOT / "data"


def _load_export_channels() -> Dict[str, str]:
    """country_iso (upper) → channel. Reads data/export-channels.json (Otto deliverable);
    returns {} when absent so callers fall back to the default channel. Handles either a
    dict keyed by ISO or a list of {country_iso, channel} rows — Otto's exact shape drops in."""
    path = _DATA_DIR / "export-channels.json"
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.debug("datasheet_export: export-channels.json unreadable", exc_info=True)
        return {}
    out: Dict[str, str] = {}
    if isinstance(doc, dict):
        # {"NO": {"channel": "data_sheet"}} or {"NO": "data_sheet"} or {"channels": [...]}
        rows = doc.get("channels") if isinstance(doc.get("channels"), list) else None
        if rows is None:
            for iso, v in doc.items():
                ch = v.get("channel") if isinstance(v, dict) else v
                if isinstance(iso, str) and isinstance(ch, str):
                    out[iso.upper()] = ch
            return out
        doc = rows
    if isinstance(doc, list):
        for row in doc:
            if isinstance(row, dict):
                iso = row.get("country_iso") or row.get("iso") or row.get("country")
                ch = row.get("channel")
                if isinstance(iso, str) and isinstance(ch, str):
                    out[iso.upper()] = ch
    return out


def resolve_export_channel(country_iso: Optional[str]) -> str:
    """The export channel for a country. Defaults to `data_sheet` (render_data_sheet) — correct
    for every corridor shipping today (FR→NO, DE) and a safe default for one we have no data on."""
    if not country_iso:
        return CHANNEL_DATA_SHEET
    return _load_export_channels().get(country_iso.upper(), CHANNEL_DATA_SHEET)


def _safe_slug(value: str) -> str:
    keep = [c if c.isalnum() or c in "-_" else "_" for c in (value or "")]
    return "".join(keep).strip("_") or "datasheet"


def _load_data_sheet_form(conn, case_id: str) -> Optional[Dict[str, Any]]:
    return conn.execute(
        _sql_text(
            f"""
            SELECT cf.id AS case_form_id, ft.code, ft.name, ft.fields, ft.sections,
                   ft.source_language, ft.authority_name
            FROM {_pg_table('case_forms')} cf
            JOIN {_pg_table('form_templates')} ft ON cf.form_template_id = ft.id
            WHERE cf.case_id = :cid AND ft.category = 'data_sheet'
            ORDER BY cf.updated_at DESC
            LIMIT 1
            """
        ),
        {"cid": case_id},
    ).mappings().first()


def build_datasheet_pdf(case_id: str) -> Tuple[Optional[bytes], str]:
    """Render the case's data sheet to PDF bytes + a download filename. ``case_id`` must be the
    resolved canonical id. Returns (None, filename) when the case has no data-sheet form or
    reportlab is unavailable — the router turns None into a 404/placeholder, never a 500.

    Channel-aware: `acroform` countries would route to the AcroForm fill path; every corridor
    shipping today is `data_sheet` (flattened/portal), so we render the sheet. The AcroForm
    branch is a scaffold hook — it falls through to the sheet until that path is wired per Otto's
    export-channels data.
    """
    with main_db.engine.connect() as conn:
        form_row = _load_data_sheet_form(conn, case_id)
        if not form_row:
            return None, "datasheet.pdf"

        cf_id = form_row["case_form_id"]
        country_iso = conn.execute(
            _sql_text(f"SELECT dest_country_code FROM {_pg_table('cases')} WHERE id = :cid"),
            {"cid": case_id},
        ).scalar()

        value_rows = conn.execute(
            _sql_text(
                f"SELECT field_id, value, source FROM {_pg_table('case_form_field_values')} "
                f"WHERE case_form_id = :cf AND value IS NOT NULL AND value != ''"
            ),
            {"cf": cf_id},
        ).mappings().all()

    values: Dict[str, str] = {str(r["field_id"]): str(r["value"]) for r in value_rows}
    sources: Dict[str, str] = {str(r["field_id"]): str(r["source"]) for r in value_rows if r.get("source")}
    fields: List[Dict[str, Any]] = _as_json(form_row.get("fields"), [])
    sections: List[Dict[str, Any]] = _as_json(form_row.get("sections"), [])

    channel = resolve_export_channel(country_iso)
    # `acroform` would fill the government form here; until that path is wired for a country that
    # actually has a fillable form, all channels render the print sheet (the correct deliverable
    # for FR→NO / DE and a safe fallback everywhere).
    _ = channel

    pdf_bytes = render_data_sheet(
        title=form_row.get("name") or "Personal Relocation Data Sheet",
        subtitle=form_row.get("authority_name") or None,
        fields=fields,
        values=values,
        sources=sources,
        source_language=form_row.get("source_language"),
        sections=sections or None,
    )

    filename = f"{_safe_slug(form_row.get('code') or 'RP-DATASHEET')}.pdf"
    return pdf_bytes, filename

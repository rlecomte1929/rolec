"""
P2-06d · Corridor-corpus → immigration_requirements ingester
─────────────────────────────────────────────────────────────────────────────
Maps the `required_documents` array of a corridor corpus file (schema_version
1.0.0 — the format produced by P2-06a / P2-06b / the P3-03 corridor research
tasks) onto rows of `public.immigration_requirements`, and emits an idempotent,
replay-safe SQL migration that UPSERTs them.

WHY a new script: there was no existing pipeline that consumed corridor corpus
JSON. `seed_immigration_requirements.py` hardcodes its rows as Python dicts; this
script reads the corpus files instead, so new corridors land by dropping a JSON
file in `corpus/` rather than editing Python.

Mapping notes
  • `source_url`  →  immigration_requirements.instructions_url
  • corpus `fetched_at`  →  last_verified_date
  • source tag set to 'corridor_corpus' (overrides the table's 'relopass_team' default)
  • corpus-only fields with no column (`id`, `validity_min_days_after_visa_expiry`,
    `source_tier`) are intentionally dropped — see KNOWN GAPS in the task notes.

Supersede
  A corpus file may declare a top-level `supersedes_db_seed` block. When present
  (and --supersede is passed), the emitted SQL first DELETEs every existing row
  for each (corridor_from, corridor_to, visa_type) covered by that file, then
  inserts the corpus rows — so stale rows whose document_type is no longer in the
  corpus are removed, not just shadowed. Delete + inserts run in one transaction.

Usage
  # Emit the migration SQL for review (does NOT touch any DB):
  python -m scripts.ingest_corridor_corpus \\
      ../corpus/us_fr_corridor.json ../corpus/in_de_corridor.json \\
      --supersede --emit-sql

Run from the `backend/` directory. This script is pure-Python (no DB driver):
it only reads JSON and prints SQL. Apply the SQL via the Supabase migration tooling.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

# Columns of public.immigration_requirements that this ingester populates, in a
# stable order, with their Postgres type class so values are rendered correctly.
# (id/created_at/updated_at are DB-managed and omitted.)
_TEXT = "text"
_BOOL = "bool"
_INT = "int"
_DATE = "date"
_JSONB = "jsonb"

COLUMNS: List[tuple[str, str]] = [
    ("corridor_from", _TEXT),
    ("corridor_to", _TEXT),
    ("visa_type", _TEXT),
    ("employee_type", _TEXT),
    ("document_type", _TEXT),
    ("document_name", _TEXT),
    ("is_required", _BOOL),
    ("is_conditional", _BOOL),
    ("condition_expression", _TEXT),
    ("freshness_days", _INT),
    ("requires_apostille", _BOOL),
    ("apostille_countries", _JSONB),
    ("requires_translation", _BOOL),
    ("translation_languages", _JSONB),
    ("can_be_prefilled", _BOOL),
    ("can_be_ocr_extracted", _BOOL),
    ("vault_field_mapping", _TEXT),
    ("typical_processing_days", _INT),
    ("book_early_flag", _BOOL),
    ("book_early_reason", _TEXT),
    ("success_tips", _JSONB),
    ("common_rejection_reasons", _JSONB),
    ("form_url", _TEXT),
    ("form_version", _TEXT),
    ("instructions_url", _TEXT),
    ("last_verified_date", _DATE),
    ("source", _TEXT),
]

# The unique key used for ON CONFLICT (matches idx_immigration_requirements_key).
CONFLICT_KEY = ("corridor_from", "corridor_to", "visa_type", "employee_type", "document_type")

_SOURCE_TAG = "corridor_corpus"


def map_document(doc: Dict[str, Any], fetched_at: str | None) -> Dict[str, Any]:
    """Map one corpus `required_documents` entry to an immigration_requirements row dict."""
    return {
        "corridor_from": doc["corridor_from"],
        "corridor_to": doc["corridor_to"],
        "visa_type": doc["visa_type"],
        "employee_type": doc.get("employee_type") or "any",
        "document_type": doc["document_type"],
        "document_name": doc["document_name"],
        "is_required": bool(doc.get("is_required", True)),
        "is_conditional": bool(doc.get("is_conditional", False)),
        "condition_expression": doc.get("condition_expression"),
        "freshness_days": doc.get("freshness_days"),
        "requires_apostille": bool(doc.get("requires_apostille", False)),
        "apostille_countries": doc.get("apostille_countries") or [],
        "requires_translation": bool(doc.get("requires_translation", False)),
        "translation_languages": doc.get("translation_languages") or [],
        "can_be_prefilled": bool(doc.get("can_be_prefilled", False)),
        "can_be_ocr_extracted": bool(doc.get("can_be_ocr_extracted", False)),
        "vault_field_mapping": doc.get("vault_field_mapping"),
        "typical_processing_days": doc.get("typical_processing_days"),
        "book_early_flag": bool(doc.get("book_early_flag", False)),
        "book_early_reason": doc.get("book_early_reason"),
        "success_tips": doc.get("success_tips") or [],
        "common_rejection_reasons": doc.get("common_rejection_reasons") or [],
        "form_url": doc.get("form_url"),
        "form_version": doc.get("form_version"),
        # corpus source_url is the per-document official reference → instructions_url
        "instructions_url": doc.get("source_url"),
        "last_verified_date": fetched_at,
        "source": _SOURCE_TAG,
    }


def map_corpus(corpus: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map a whole corridor corpus file to a list of row dicts."""
    fetched_at = corpus.get("fetched_at")
    return [map_document(d, fetched_at) for d in corpus.get("required_documents", [])]


def _sql_literal(value: Any, col_type: str) -> str:
    if value is None:
        return "NULL"
    if col_type == _BOOL:
        return "true" if value else "false"
    if col_type == _INT:
        return str(int(value))
    if col_type == _JSONB:
        return _quote(json.dumps(value, ensure_ascii=False)) + "::jsonb"
    # text / date
    return _quote(str(value))


def _quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _row_values_sql(row: Dict[str, Any]) -> str:
    return "(" + ", ".join(_sql_literal(row[name], typ) for name, typ in COLUMNS) + ")"


def build_sql(corpus_files: List[str], supersede: bool, wrap_transaction: bool = False) -> str:
    """
    Build a single idempotent SQL block for all corpus files.

    By default emits NO BEGIN/COMMIT — Supabase migration runners (and MCP
    apply_migration) wrap each migration in their own transaction, matching the
    repo convention. Pass wrap_transaction=True for standalone `psql -f` runs
    where you want the delete+upserts to be atomic on their own.
    """
    parsed = [(f, json.load(open(f, encoding="utf-8"))) for f in corpus_files]

    lines: List[str] = []
    lines.append("-- P2-06d · Ingest corridor corpus → public.immigration_requirements")
    lines.append("-- Generated by backend/scripts/ingest_corridor_corpus.py — do not hand-edit.")
    if wrap_transaction:
        lines.append("BEGIN;")
    lines.append("")

    # 1) Supersede deletes (covered corridor/visa combos for files that declare it).
    if supersede:
        for path, corpus in parsed:
            if not corpus.get("supersedes_db_seed"):
                continue
            combos = sorted({(r["corridor_from"], r["corridor_to"], r["visa_type"])
                             for r in map_corpus(corpus)})
            for cf, ct, vt in combos:
                lines.append(
                    f"-- supersede stale rows for ({cf}, {ct}, {vt}) per "
                    f"supersedes_db_seed in {path.split('/')[-1]}"
                )
                lines.append(
                    "DELETE FROM public.immigration_requirements "
                    f"WHERE corridor_from = {_quote(cf)} AND corridor_to = {_quote(ct)} "
                    f"AND visa_type = {_quote(vt)};"
                )
            lines.append("")

    # 2) Upserts.
    col_list = ", ".join(name for name, _ in COLUMNS)
    conflict = ", ".join(CONFLICT_KEY)
    update_cols = [name for name, _ in COLUMNS if name not in CONFLICT_KEY]
    set_clause = ",\n    ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

    for path, corpus in parsed:
        rows = map_corpus(corpus)
        c = corpus.get("corridor", {})
        lines.append(
            f"-- {c.get('from')}→{c.get('to')} : {len(rows)} required_documents "
            f"from {path.split('/')[-1]}"
        )
        lines.append(f"INSERT INTO public.immigration_requirements ({col_list}) VALUES")
        lines.append(",\n".join("  " + _row_values_sql(r) for r in rows))
        lines.append(f"ON CONFLICT ({conflict}) DO UPDATE SET")
        lines.append("    " + set_clause + ",")
        lines.append("    updated_at = now();")
        lines.append("")

    if wrap_transaction:
        lines.append("COMMIT;")
        lines.append("")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest corridor corpus → immigration_requirements")
    ap.add_argument("corpus_files", nargs="+", help="Path(s) to corridor corpus JSON file(s)")
    ap.add_argument("--supersede", action="store_true",
                    help="Honor supersedes_db_seed: DELETE existing rows for covered "
                         "(corridor_from, corridor_to, visa_type) before insert.")
    ap.add_argument("--emit-sql", action="store_true",
                    help="Print the migration SQL to stdout (default action).")
    ap.add_argument("--wrap-transaction", action="store_true",
                    help="Wrap output in BEGIN/COMMIT (for standalone psql -f runs; "
                         "omit for Supabase migrations, which wrap their own txn).")
    args = ap.parse_args(argv)

    sql = build_sql(args.corpus_files, supersede=args.supersede,
                    wrap_transaction=args.wrap_transaction)
    # --emit-sql is the only mode (the script never connects to a DB itself).
    sys.stdout.write(sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

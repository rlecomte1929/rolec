#!/usr/bin/env python3
"""
AI-I.4b / AIQ-622 — Embedding-migration dry-run: read-only impact report.

Quantifies the cost + downtime of re-embedding the corpus BEFORE the real
migration (AI-I.4c) runs, so a model swap (text-embedding-3-small -> BGE-M3 /
Cohere v3, per AI-W1.2) never surprises us with a runaway token bill or an
unplanned index rebuild.

What it reports
---------------
For every table that has a pgvector ``embedding`` column it auto-discovers
(so it stays correct as tables are added/renamed — it does NOT hardcode a stale
``policy_chunks`` name), it prints:
  - row count,
  - estimated re-embed tokens (source-text chars / chars-per-token),
  - estimated re-embed cost in USD,
  - the vector-index (HNSW / IVFFlat) rebuild plan + a seconds estimate.

…and a roll-up:  {rows, estimated_tokens, estimated_cost_usd, index_rebuild_seconds_est}

STRICTLY READ-ONLY. It opens a ``readonly=True`` psycopg2 session and issues only
SELECTs against catalog + data tables — it never writes, and re-embedding /
index rebuilding is NOT performed here. This is a planning report only.

Usage
-----
    # Live (read-only) against the configured DB:
    DATABASE_URL=postgresql://... python scripts/embedding_migration_dryrun.py
    DATABASE_URL=postgresql://... python scripts/embedding_migration_dryrun.py --json

    # Offline (no DB): supply counts/chars yourself to run the cost math anywhere:
    python scripts/embedding_migration_dryrun.py --offline --rows 355 --chars 113554

Exit codes: 0 = report produced; 2 = could not connect / DATABASE_URL unset
(and not --offline).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- Estimation constants (provenance noted; override via flags) -------------

# text-embedding-3-small list price, $0.02 per 1M tokens, as documented in
# backend/app/services/policy_assistant_embedder.py (price as of 2026-04). Kept
# here as a standalone constant so this planning script has no backend import
# (matches the convention of scripts/check_rls_coverage.py).
DEFAULT_PRICE_PER_1M_TOKENS_USD = 0.02

# OpenAI embedding tokenisation averages ~4 chars/token for English policy text.
# A heuristic, not exact — the real migration logs true token counts.
DEFAULT_CHARS_PER_TOKEN = 4.0

# HNSW build throughput heuristic (rows indexed per second). Conservative; the
# real rebuild is wall-clock-logged. Used only to flag "seconds vs minutes vs
# hours" of index downtime, not to promise a precise number.
DEFAULT_HNSW_BUILD_ROWS_PER_SEC = 2000.0

# Preference order for the column whose text is fed to the embedder. First match
# (case-insensitive) wins; jsonb columns are cast to text for length.
_TEXT_COLUMN_PREFERENCE = (
    "chunk_text",
    "text",
    "content",
    "body",
    "canonical_form",
)


@dataclass
class TableImpact:
    schema: str
    table: str
    embedding_col: str
    dim: Optional[int]
    text_col: Optional[str]
    rows: int = 0
    chars: int = 0
    indexes: List[str] = field(default_factory=list)  # "schema.indexname (hnsw)"

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.table}"

    def tokens(self, chars_per_token: float) -> int:
        if chars_per_token <= 0:
            return 0
        return int(round(self.chars / chars_per_token))

    def index_rebuild_seconds(self, rows_per_sec: float) -> float:
        if not self.indexes or self.rows == 0 or rows_per_sec <= 0:
            return 0.0
        # One rebuild per vector index on the table.
        return len(self.indexes) * max(1.0, self.rows / rows_per_sec)


# --- Live (read-only) discovery ---------------------------------------------

_VECTOR_COLUMNS_SQL = """
SELECT n.nspname, c.relname, a.attname,
       format_type(a.atttypid, a.atttypmod) AS col_type
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE a.attnum > 0 AND NOT a.attisdropped AND c.relkind = 'r'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND format_type(a.atttypid, a.atttypmod) LIKE 'vector%'
ORDER BY n.nspname, c.relname;
"""

_TEXTISH_COLUMNS_SQL = """
SELECT a.attname, format_type(a.atttypid, a.atttypmod) AS col_type
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relname = %s
  AND a.attnum > 0 AND NOT a.attisdropped
  AND format_type(a.atttypid, a.atttypmod) ~ '(text|char|json)'
ORDER BY a.attnum;
"""

_VECTOR_INDEXES_SQL = """
SELECT schemaname, indexname, tablename, indexdef
FROM pg_indexes
WHERE schemaname = %s AND tablename = %s
  AND (indexdef ILIKE '%%using hnsw%%' OR indexdef ILIKE '%%using ivfflat%%');
"""


def _dim_from_coltype(col_type: str) -> Optional[int]:
    # e.g. "vector(1536)" -> 1536
    if "(" in col_type and col_type.endswith(")"):
        try:
            return int(col_type[col_type.index("(") + 1 : -1])
        except ValueError:
            return None
    return None


def _pick_text_column(candidates: List[tuple]) -> Optional[str]:
    names = {name.lower(): name for name, _type in candidates}
    for pref in _TEXT_COLUMN_PREFERENCE:
        if pref in names:
            return names[pref]
    # No preferred name — fall back to the first text/jsonb column if any.
    return candidates[0][0] if candidates else None


def _connect_readonly(db_url: str):
    try:
        import psycopg2
    except ImportError:
        print(
            "psycopg2 not installed — `pip install psycopg2-binary` or run from the backend venv",
            file=sys.stderr,
        )
        sys.exit(2)

    if db_url.startswith("postgres://"):  # legacy Supabase pooler scheme
        db_url = "postgresql://" + db_url[len("postgres://") :]

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:  # connection / DNS / auth
        print(f"could not connect to DATABASE_URL: {exc}", file=sys.stderr)
        sys.exit(2)

    # Hard guarantee: this session cannot write.
    conn.set_session(readonly=True, autocommit=True)
    return conn


def discover_live(db_url: str) -> List[TableImpact]:
    conn = _connect_readonly(db_url)
    impacts: List[TableImpact] = []
    try:
        with conn.cursor() as cur:
            cur.execute(_VECTOR_COLUMNS_SQL)
            vector_cols = cur.fetchall()

            for schema, table, embed_col, col_type in vector_cols:
                cur.execute(_TEXTISH_COLUMNS_SQL, (schema, table))
                text_col = _pick_text_column(cur.fetchall())

                impact = TableImpact(
                    schema=schema,
                    table=table,
                    embedding_col=embed_col,
                    dim=_dim_from_coltype(col_type),
                    text_col=text_col,
                )

                # Row count + source-text char total (read-only). Identifiers are
                # catalog-derived (not user input), so quoting is safe here.
                if text_col is not None:
                    cur.execute(
                        f'SELECT count(*), '
                        f'coalesce(sum(length("{text_col}"::text)), 0) '
                        f'FROM "{schema}"."{table}";'
                    )
                    impact.rows, impact.chars = cur.fetchone()
                else:
                    cur.execute(f'SELECT count(*) FROM "{schema}"."{table}";')
                    (impact.rows,) = cur.fetchone()

                cur.execute(_VECTOR_INDEXES_SQL, (schema, table))
                for idx_schema, idx_name, _tbl, idx_def in cur.fetchall():
                    method = "hnsw" if "hnsw" in idx_def.lower() else "ivfflat"
                    impact.indexes.append(f"{idx_schema}.{idx_name} ({method})")

                impacts.append(impact)
    finally:
        conn.close()
    return impacts


# --- Reporting ---------------------------------------------------------------

def build_report(
    impacts: List[TableImpact],
    *,
    price_per_1m: float,
    chars_per_token: float,
    rows_per_sec: float,
) -> dict:
    per_table = []
    total_rows = 0
    total_tokens = 0
    total_index_seconds = 0.0
    for im in impacts:
        tokens = im.tokens(chars_per_token)
        idx_seconds = im.index_rebuild_seconds(rows_per_sec)
        total_rows += im.rows
        total_tokens += tokens
        total_index_seconds += idx_seconds
        per_table.append(
            {
                "table": im.qualified,
                "embedding_col": im.embedding_col,
                "dim": im.dim,
                "text_col": im.text_col,
                "rows": im.rows,
                "chars": im.chars,
                "estimated_tokens": tokens,
                "estimated_cost_usd": round(tokens / 1_000_000 * price_per_1m, 6),
                "vector_indexes": im.indexes,
                "index_rebuild_seconds_est": round(idx_seconds, 1),
            }
        )

    return {
        "rows": total_rows,
        "estimated_tokens": total_tokens,
        "estimated_cost_usd": round(total_tokens / 1_000_000 * price_per_1m, 6),
        "index_rebuild_seconds_est": round(total_index_seconds, 1),
        "assumptions": {
            "price_per_1m_tokens_usd": price_per_1m,
            "chars_per_token": chars_per_token,
            "hnsw_build_rows_per_sec": rows_per_sec,
        },
        "per_table": per_table,
    }


def _print_human(report: dict) -> None:
    lines = [
        "",
        "=== AIQ-622 Embedding-Migration Dry-Run (READ-ONLY — no DB writes) ===",
        f"Embedded tables: {len(report['per_table'])}",
        "",
        f"{'table':<42}{'rows':>8}{'tokens':>12}{'cost USD':>12}{'idx rebuild s':>15}",
        f"{'-' * 89}",
    ]
    for t in report["per_table"]:
        lines.append(
            f"{t['table']:<42}{t['rows']:>8}{t['estimated_tokens']:>12}"
            f"{t['estimated_cost_usd']:>12.6f}{t['index_rebuild_seconds_est']:>15.1f}"
        )
        for idx in t["vector_indexes"]:
            lines.append(f"    index: {idx}")
        if not t["vector_indexes"]:
            lines.append("    index: (no vector index — nothing to rebuild)")
    a = report["assumptions"]
    lines += [
        f"{'-' * 89}",
        f"{'TOTAL':<42}{report['rows']:>8}{report['estimated_tokens']:>12}"
        f"{report['estimated_cost_usd']:>12.6f}{report['index_rebuild_seconds_est']:>15.1f}",
        "",
        "Assumptions: "
        f"${a['price_per_1m_tokens_usd']}/1M tokens (text-embedding-3-small), "
        f"{a['chars_per_token']} chars/token, "
        f"{a['hnsw_build_rows_per_sec']:.0f} rows/s HNSW build.",
        "Roll-up: "
        + json.dumps(
            {
                "rows": report["rows"],
                "estimated_tokens": report["estimated_tokens"],
                "estimated_cost_usd": report["estimated_cost_usd"],
                "index_rebuild_seconds_est": report["index_rebuild_seconds_est"],
            }
        ),
        "",
    ]
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="AIQ-622 embedding-migration dry-run (read-only impact report)."
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of the table.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not connect to a DB; use --rows/--chars (and optional --indexes) instead.",
    )
    parser.add_argument("--rows", type=int, default=0, help="[offline] total rows to re-embed.")
    parser.add_argument("--chars", type=int, default=0, help="[offline] total source-text chars.")
    parser.add_argument(
        "--indexes",
        type=int,
        default=1,
        help="[offline] number of vector indexes to rebuild (default 1).",
    )
    parser.add_argument(
        "--price-per-1m", type=float, default=DEFAULT_PRICE_PER_1M_TOKENS_USD,
        help="USD per 1M tokens (default text-embedding-3-small list price).",
    )
    parser.add_argument(
        "--chars-per-token", type=float, default=DEFAULT_CHARS_PER_TOKEN,
        help="Chars per token heuristic (default 4.0).",
    )
    parser.add_argument(
        "--hnsw-rows-per-sec", type=float, default=DEFAULT_HNSW_BUILD_ROWS_PER_SEC,
        help="HNSW index build throughput (rows/sec) for the rebuild estimate.",
    )
    args = parser.parse_args(argv)

    if args.offline:
        impacts = [
            TableImpact(
                schema="(offline)",
                table="corpus",
                embedding_col="embedding",
                dim=None,
                text_col="(supplied)",
                rows=args.rows,
                chars=args.chars,
                indexes=[f"(offline)#{i + 1} (hnsw)" for i in range(max(0, args.indexes))],
            )
        ]
    else:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print(
                "DATABASE_URL not set. Set it for a live read-only report, or use "
                "--offline --rows N --chars M.",
                file=sys.stderr,
            )
            return 2
        impacts = discover_live(db_url)

    report = build_report(
        impacts,
        price_per_1m=args.price_per_1m,
        chars_per_token=args.chars_per_token,
        rows_per_sec=args.hnsw_rows_per_sec,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

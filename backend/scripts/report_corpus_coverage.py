"""
H3 · Immigration corpus coverage report (READ-ONLY diagnostic)
─────────────────────────────────────────────────────────────────────────────
Answers one question for launch readiness: **which relocation corridors render a
real, corridor-specific roadmap, and which fall back to the generic deterministic
seed?**

The roadmap pipeline is:

    POST submit
      → case_roadmap_profile.generate_ai_roadmap_for_case
      → rag_pipeline.generate_roadmap
      → immigration_retriever.retrieve_for_profile(...)   (corridor-scoped)

`retrieve_for_profile` reads ``immigration_corpus_chunks`` filtered by corridor.
When a corridor has **no** corpus chunks the retrieval is empty, the generator
raises ``RULE_NOT_FOUND``, and the employee page falls back to a generic
deterministic seed roadmap — populated, but NOT grounded in authoritative,
corridor-specific immigration rules. This report makes that split explicit so
Romain knows exactly where authoritative content still has to be sourced.

This script is a DIAGNOSTIC only. It never writes to the corpus, never seeds
synthetic rules, and never invents content. A corridor with zero corpus chunks
is reported honestly as ``generic seed (needs content)``.

Two modes (auto-selected):

  • DB mode   — when ``DATABASE_URL`` is set: a single read-only ``SELECT`` over
                ``immigration_corpus_chunks`` (grouped by corridor). Reflects the
                live, ingested corpus.
  • Offline   — otherwise (or with ``--offline``): coverage is computed over the
                committed corpus JSON (the same files the ingestion indexer reads),
                by running them through ``index_corridor_corpus_chunks.build_chunks``
                — the exact chunk model the indexer would load. Runs in CI without
                a DB.

The corridor "universe" is the union of:
  • the configured corridor registry (``corridors/<id>/corridor.yaml``), i.e.
    corridors the product is set up to handle, and
  • every corridor that has committed corpus content (DB rows or corpus files).
A registry corridor with no corpus content is the headline gap: configured, but
served by the generic seed.

Usage (run from repo root):
  python backend/scripts/report_corpus_coverage.py            # auto: DB if DATABASE_URL else offline
  python backend/scripts/report_corpus_coverage.py --offline  # force offline (over committed corpus)
  python backend/scripts/report_corpus_coverage.py --json     # machine-readable to stdout
  python backend/scripts/report_corpus_coverage.py --corpus-dir corpus --corpus-dir backend/tests/fixtures/rag_eval/corpus

Always writes a dated report pair (unless ``--no-write``):
  audit/corpus_coverage_<YYYYMMDD>.md
  audit/corpus_coverage_<YYYYMMDD>.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import corridor_registry  # noqa: E402
from backend.scripts.index_corridor_corpus_chunks import build_chunks  # noqa: E402

# Default committed corpus locations scanned in offline mode: the live ingestion
# source (repo-root corpus/) plus the eval fixtures. Both are committed, so the
# offline report runs in CI with no DB.
_DEFAULT_CORPUS_DIRS = (
    "corpus",
    "backend/tests/fixtures/rag_eval/corpus",
)

COVERED = "covered (corridor-specific roadmap)"
UNCOVERED = "generic seed (needs content)"


@dataclass
class CorridorCoverage:
    """Coverage record for one corridor. ``corridor`` is the underscore key
    (e.g. ``FR_NO``) used by ``immigration_corpus_chunks.corridor``."""

    corridor: str
    covered: bool
    status: str
    chunk_count: int
    pathway_types: List[str] = field(default_factory=list)
    in_registry: bool = False
    has_corpus_source: bool = False
    sources: List[str] = field(default_factory=list)


# --- offline coverage (committed corpus files) ------------------------------

def _iter_corpus_files(corpus_dirs: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    for d in corpus_dirs:
        root = Path(d)
        if not root.is_absolute():
            root = Path(_REPO_ROOT) / root
        if not root.is_dir():
            continue
        files.extend(sorted(root.glob("*_corridor.json")))
    return files


def _pathway_types(chunks: List[Dict[str, Any]]) -> List[str]:
    return sorted({c["pathway_type"] for c in chunks if c.get("pathway_type")})


def offline_corpus_index(corpus_dirs: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Map corridor (underscore key) -> {chunk_count, pathway_types, sources}
    built from the committed corpus JSON via the indexer's own ``build_chunks``.
    A file that does not parse or lacks corridor.from/.to is skipped (best-effort,
    never raises) — it simply does not contribute coverage.

    Each ``*_corridor.json`` is a *complete* corridor corpus and the indexer
    replaces a corridor's chunks wholesale (DELETE-then-INSERT), so when the same
    corridor appears in more than one scanned dir we report the representative
    (max) single-file chunk count rather than summing duplicates."""
    index: Dict[str, Dict[str, Any]] = {}
    for path in _iter_corpus_files(corpus_dirs):
        try:
            corpus = json.loads(path.read_text(encoding="utf-8"))
            chunks = build_chunks(corpus)
        except Exception:  # noqa: BLE001 — a malformed file must not crash the report
            continue
        if not chunks:
            continue
        corridor = corridor_registry.normalize_corridor_id(chunks[0]["corridor"])
        entry = index.setdefault(
            corridor, {"chunk_count": 0, "pathway_types": set(), "sources": []}
        )
        entry["chunk_count"] = max(entry["chunk_count"], len(chunks))
        entry["pathway_types"].update(_pathway_types(chunks))
        rel = os.path.relpath(path, _REPO_ROOT)
        if rel not in entry["sources"]:
            entry["sources"].append(rel)
    return index


def build_coverage_offline(
    corpus_dirs: Sequence[str],
    registry_corridors: Optional[Sequence[str]] = None,
) -> List[CorridorCoverage]:
    """Coverage over the committed corpus files, cross-referenced with the
    configured corridor registry. Pure / no DB / no network — the unit-test seam."""
    if registry_corridors is None:
        registry_corridors = corridor_registry.list_corridors()
    registry = {corridor_registry.normalize_corridor_id(c) for c in registry_corridors}
    corpus = offline_corpus_index(corpus_dirs)

    universe = sorted(registry | set(corpus.keys()))
    out: List[CorridorCoverage] = []
    for corridor in universe:
        entry = corpus.get(corridor)
        chunk_count = int(entry["chunk_count"]) if entry else 0
        covered = chunk_count > 0
        out.append(
            CorridorCoverage(
                corridor=corridor,
                covered=covered,
                status=COVERED if covered else UNCOVERED,
                chunk_count=chunk_count,
                pathway_types=sorted(entry["pathway_types"]) if entry else [],
                in_registry=corridor in registry,
                has_corpus_source=bool(entry),
                sources=list(entry["sources"]) if entry else [],
            )
        )
    return out


# --- DB coverage (live immigration_corpus_chunks) ---------------------------

def build_coverage_db(engine, registry_corridors: Optional[Sequence[str]] = None) -> List[CorridorCoverage]:
    """Coverage over the live ``immigration_corpus_chunks`` (read-only).
    One grouped SELECT; pathway types come from ``chunk_metadata->>'pathway_type'``."""
    from sqlalchemy import text  # local import: only needed in DB mode

    if registry_corridors is None:
        registry_corridors = corridor_registry.list_corridors()
    registry = {corridor_registry.normalize_corridor_id(c) for c in registry_corridors}

    is_sqlite = engine.dialect.name == "sqlite"
    pathway_expr = (
        "json_extract(chunk_metadata, '$.pathway_type')" if is_sqlite
        else "chunk_metadata->>'pathway_type'"
    )
    active = "is_active = 1" if is_sqlite else "is_active = true"
    sql = text(
        f"SELECT corridor, COUNT(*) AS n, "
        f"       GROUP_CONCAT(DISTINCT {pathway_expr}) AS pathways "
        f"FROM immigration_corpus_chunks WHERE {active} GROUP BY corridor"
        if is_sqlite else
        f"SELECT corridor, COUNT(*) AS n, "
        f"       ARRAY_AGG(DISTINCT {pathway_expr}) AS pathways "
        f"FROM immigration_corpus_chunks WHERE {active} GROUP BY corridor"
    )
    db_index: Dict[str, Dict[str, Any]] = {}
    with engine.begin() as conn:
        for row in conn.execute(sql).mappings().all():
            corridor = corridor_registry.normalize_corridor_id(row["corridor"])
            pathways_raw = row["pathways"]
            if isinstance(pathways_raw, str):
                pathways = [p for p in pathways_raw.split(",") if p]
            elif isinstance(pathways_raw, (list, tuple)):
                pathways = [p for p in pathways_raw if p]
            else:
                pathways = []
            db_index[corridor] = {"chunk_count": int(row["n"]), "pathway_types": sorted(set(pathways))}

    universe = sorted(registry | set(db_index.keys()))
    out: List[CorridorCoverage] = []
    for corridor in universe:
        entry = db_index.get(corridor)
        chunk_count = int(entry["chunk_count"]) if entry else 0
        covered = chunk_count > 0
        out.append(
            CorridorCoverage(
                corridor=corridor,
                covered=covered,
                status=COVERED if covered else UNCOVERED,
                chunk_count=chunk_count,
                pathway_types=entry["pathway_types"] if entry else [],
                in_registry=corridor in registry,
                has_corpus_source=bool(entry),
                sources=["immigration_corpus_chunks"] if entry else [],
            )
        )
    return out


# --- reporting --------------------------------------------------------------

def summarize(rows: Sequence[CorridorCoverage]) -> Dict[str, Any]:
    covered = [r for r in rows if r.covered]
    uncovered = [r for r in rows if not r.covered]
    # The headline gap: corridors the product is configured for (registry) that
    # are served by the generic seed because they have no corpus content.
    registry_gaps = [r.corridor for r in uncovered if r.in_registry]
    return {
        "total_corridors": len(rows),
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "covered_corridors": [r.corridor for r in covered],
        "uncovered_corridors": [r.corridor for r in uncovered],
        "registry_corridors_needing_content": registry_gaps,
    }


def build_report(rows: Sequence[CorridorCoverage], *, mode: str) -> Dict[str, Any]:
    return {
        "report": "immigration_corpus_coverage",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "mode": mode,
        "disclaimer": (
            "READ-ONLY diagnostic. No synthetic immigration rules are added to the "
            "corpus. Uncovered corridors render a generic deterministic seed roadmap "
            "(RULE_NOT_FOUND), not corridor-specific authoritative guidance."
        ),
        "summary": summarize(rows),
        "corridors": [asdict(r) for r in rows],
    }


def render_markdown(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines: List[str] = []
    lines.append("# Immigration corpus coverage report")
    lines.append("")
    lines.append(f"- Generated: `{report['generated_at']}`")
    lines.append(f"- Mode: **{report['mode']}**")
    lines.append(
        f"- Corridors: **{s['covered_count']} covered** "
        f"/ **{s['uncovered_count']} generic-seed** of {s['total_corridors']} known"
    )
    lines.append("")
    lines.append(f"> {report['disclaimer']}")
    lines.append("")
    lines.append("## Per-corridor coverage")
    lines.append("")
    lines.append("| Corridor | Status | Chunks | In registry | Pathway types |")
    lines.append("| --- | --- | ---: | :---: | --- |")
    for r in report["corridors"]:
        pts = ", ".join(r["pathway_types"]) or "—"
        reg = "yes" if r["in_registry"] else "no"
        mark = "✅" if r["covered"] else "⚠️"
        lines.append(
            f"| `{r['corridor']}` | {mark} {r['status']} | {r['chunk_count']} | {reg} | {pts} |"
        )
    lines.append("")
    gaps = s["registry_corridors_needing_content"]
    lines.append("## Configured corridors needing authoritative content")
    lines.append("")
    if gaps:
        lines.append(
            "These corridors are configured in the corridor registry but have no "
            "corpus content, so they render the **generic seed**. They are the "
            "priority list for sourcing authoritative immigration rules:"
        )
        lines.append("")
        for c in gaps:
            lines.append(f"- `{c}`")
    else:
        lines.append("None — every configured corridor has corpus content.")
    lines.append("")
    return "\n".join(lines)


def write_reports(report: Dict[str, Any], out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    json_path = out_dir / f"corpus_coverage_{stamp}.json"
    md_path = out_dir / f"corpus_coverage_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return [md_path, json_path]


def _make_engine():
    """Read-only engine from DATABASE_URL. Returns None if unset/unavailable."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return None
    try:
        from sqlalchemy import create_engine

        from backend import db_config

        return create_engine(db_config.DATABASE_URL, **db_config.sqlalchemy_engine_kwargs(db_config.DATABASE_URL))
    except Exception as exc:  # noqa: BLE001
        print(f"warning: could not build DB engine ({exc}); falling back to offline", file=sys.stderr)
        return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="Force offline mode (ignore DATABASE_URL).")
    ap.add_argument("--json", action="store_true", help="Print the JSON report to stdout.")
    ap.add_argument(
        "--corpus-dir", action="append", default=None,
        help="Corpus directory for offline mode (repeatable). "
             f"Default: {', '.join(_DEFAULT_CORPUS_DIRS)}",
    )
    ap.add_argument("--no-write", action="store_true", help="Do not write the dated report files.")
    ap.add_argument("--out-dir", default="audit", help="Directory for the dated report (default: audit).")
    args = ap.parse_args(argv)

    corpus_dirs = args.corpus_dir or list(_DEFAULT_CORPUS_DIRS)

    engine = None if args.offline else _make_engine()
    if engine is not None:
        try:
            rows = build_coverage_db(engine)
            mode = "db"
        except Exception as exc:  # noqa: BLE001 — table may not exist locally
            print(f"warning: DB query failed ({exc}); falling back to offline", file=sys.stderr)
            rows = build_coverage_offline(corpus_dirs)
            mode = "offline"
    else:
        rows = build_coverage_offline(corpus_dirs)
        mode = "offline"

    report = build_report(rows, mode=mode)

    if not args.no_write:
        out_dir = Path(args.out_dir)
        if not out_dir.is_absolute():
            out_dir = Path(_REPO_ROOT) / out_dir
        paths = write_reports(report, out_dir)
        for p in paths:
            print(f"wrote {os.path.relpath(p, _REPO_ROOT)}", file=sys.stderr)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
AIQ-806 · P3-04f — Corridor corpus → public.source_pages tier/freshness backfill
─────────────────────────────────────────────────────────────────────────────
The employee roadmap shows a per-step ConfidenceBadge. On the LIVE roadmap path
(`/api/cases/{id}/roadmap/tracks`, P3-04e-FU) that badge is resolved from
``source_pages.tier`` joined by URL to the form's ``source_url``. But source_pages
was only seed-bootstrapped from form_templates at the default tier '1' — so every
step resolved to the same uniform confidence (effectively meaningless) and most
real official URLs had no row at all.

This script reads the corridor corpus files (the same `corpus/*.json` consumed by
``ingest_corridor_corpus.py``), which carry the *real* per-document trust tier
(`source_tier`: 1/2/3) and per-corridor `fetched_at`, and emits an idempotent,
replay-safe SQL block that UPSERTs one ``source_pages`` row per distinct official
URL with its true tier. Confidence then resolves to honest HIGH/MEDIUM/LOW across
the covered corridors instead of a flat default.

Why source_pages (not requirements/roadmap_steps): the persisted ``requirements``
and ``roadmap_steps`` tables are empty/dead — the live roadmap projects from
``case_forms`` at read time and reads provenance from ``source_pages``. This
backfill targets the table the live path actually reads.

URL sources collected from each corpus file:
  • required_documents[].source_url  + .source_tier
  • primary_sources[].url            + .tier
  • per-corridor `fetched_at`         → last_fetched_at (only if not already set)

Idempotency / replay-safety (ON CONFLICT (url)):
  • tier            = EXCLUDED.tier         (corpus is authoritative for tier)
  • last_fetched_at = COALESCE(existing, EXCLUDED)  (never clobber a real crawl ts)

Usage
  # Print the planned upserts + counts, write nothing:
  python -m scripts.backfill_source_pages_from_corpus ../corpus/*.json --dry-run

  # Emit the migration SQL to stdout (default):
  python -m scripts.backfill_source_pages_from_corpus ../corpus/us_fr_corridor.json

Run from the `backend/` directory. Pure-Python (no DB driver): it reads JSON and
prints SQL. Apply the SQL via the Supabase migration tooling, then commit the
matching migration file to reconcile the ledger.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple


def _coerce_tier(value: Any) -> Optional[str]:
    """Normalise a corpus tier (int 1/2/3 or str) to the TEXT form source_pages stores.

    Returns None for missing/blank so the caller can skip URLs with no tier rather
    than inventing a default '1' (which is exactly the uniform-confidence bug this
    backfill fixes).
    """
    if value is None:
        return None
    if isinstance(value, float):
        value = int(value)
    s = str(value).strip()
    return s or None


def collect_source_pages(corpus: Dict[str, Any]) -> Dict[str, Tuple[str, Optional[str]]]:
    """Map one corridor corpus file → {url: (tier, fetched_at)}.

    Within a single file a URL may appear in both required_documents and
    primary_sources; we keep the first tier seen and prefer a non-null tier.
    """
    fetched_at = corpus.get("fetched_at")
    out: Dict[str, Tuple[str, Optional[str]]] = {}

    def _add(url: Any, tier: Any) -> None:
        if not url or not isinstance(url, str):
            return
        u = url.strip()
        if not u:
            return
        t = _coerce_tier(tier)
        if t is None:
            return  # honest: no tier → no source_pages provenance row from here
        # First non-null tier wins; don't downgrade a tier already recorded.
        if u not in out:
            out[u] = (t, fetched_at)

    for doc in corpus.get("required_documents", []) or []:
        _add(doc.get("source_url"), doc.get("source_tier"))
    for src in corpus.get("primary_sources", []) or []:
        _add(src.get("url"), src.get("tier"))
    return out


def collect_all(corpus_files: List[str]) -> List[Tuple[str, str, Optional[str]]]:
    """Merge all corpus files → sorted list of (url, tier, fetched_at), deduped by url.

    Across files, the first file that declares a URL wins (files are processed in
    the order given). Returns rows sorted by url for stable, reviewable SQL output.
    """
    merged: Dict[str, Tuple[str, Optional[str]]] = {}
    for path in corpus_files:
        with open(path, encoding="utf-8") as fh:
            corpus = json.load(fh)
        for url, (tier, fetched_at) in collect_source_pages(corpus).items():
            if url not in merged:
                merged[url] = (tier, fetched_at)
    return [(url, tier, fetched_at) for url, (tier, fetched_at) in sorted(merged.items())]


def _quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _value_sql(url: str, tier: str, fetched_at: Optional[str]) -> str:
    ts = _quote(fetched_at) + "::timestamptz" if fetched_at else "NULL"
    return f"  ({_quote(url)}, {_quote(tier)}, {ts})"


def build_sql(corpus_files: List[str], wrap_transaction: bool = False) -> str:
    """Build a single idempotent UPSERT block for all corpus files."""
    rows = collect_all(corpus_files)

    lines: List[str] = []
    lines.append("-- AIQ-806 / P3-04f · Backfill public.source_pages tiers from corridor corpus")
    lines.append("-- Generated by backend/scripts/backfill_source_pages_from_corpus.py — do not hand-edit.")
    lines.append(f"-- {len(rows)} distinct official source URLs across "
                 f"{len(corpus_files)} corpus file(s).")
    if wrap_transaction:
        lines.append("BEGIN;")
    lines.append("")

    if not rows:
        lines.append("-- (no source URLs with a declared tier found — nothing to upsert)")
        if wrap_transaction:
            lines.append("COMMIT;")
        lines.append("")
        return "\n".join(lines)

    lines.append("INSERT INTO public.source_pages (url, tier, last_fetched_at) VALUES")
    lines.append(",\n".join(_value_sql(url, tier, ts) for url, tier, ts in rows))
    lines.append("ON CONFLICT (url) DO UPDATE SET")
    # tier: corpus is authoritative. last_fetched_at: keep any real crawler value.
    lines.append("    tier = EXCLUDED.tier,")
    lines.append("    last_fetched_at = COALESCE(public.source_pages.last_fetched_at, EXCLUDED.last_fetched_at),")
    lines.append("    updated_at = now();")
    lines.append("")

    if wrap_transaction:
        lines.append("COMMIT;")
        lines.append("")
    return "\n".join(lines)


def _print_dry_run(corpus_files: List[str]) -> None:
    rows = collect_all(corpus_files)
    by_tier: Dict[str, int] = {}
    for _, tier, _ in rows:
        by_tier[tier] = by_tier.get(tier, 0) + 1
    sys.stderr.write(f"[dry-run] {len(rows)} distinct source URLs from {len(corpus_files)} file(s)\n")
    for tier in sorted(by_tier):
        sys.stderr.write(f"[dry-run]   tier {tier}: {by_tier[tier]} URL(s)\n")
    for url, tier, ts in rows:
        sys.stderr.write(f"[dry-run]   tier={tier} fetched_at={ts or '-'}  {url}\n")
    sys.stderr.write("[dry-run] no SQL emitted (use without --dry-run to print the migration SQL)\n")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Backfill source_pages tiers/freshness from corridor corpus JSON")
    ap.add_argument("corpus_files", nargs="+", help="Path(s) to corridor corpus JSON file(s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the planned upserts + per-tier counts to stderr; emit no SQL.")
    ap.add_argument("--wrap-transaction", action="store_true",
                    help="Wrap output in BEGIN/COMMIT (for standalone psql -f runs; "
                         "omit for Supabase migrations, which wrap their own txn).")
    args = ap.parse_args(argv)

    if args.dry_run:
        _print_dry_run(args.corpus_files)
        return 0

    sys.stdout.write(build_sql(args.corpus_files, wrap_transaction=args.wrap_transaction))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

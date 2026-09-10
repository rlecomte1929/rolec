#!/usr/bin/env python3
"""Confirm evidence quotes against HTTP-cached or browser-grounded page text.

This module never fetches over the network. The integrator grafts it onto
``scripts/verify_batch_quotes.py`` with the repo's ``fact_evidence.normalise`` and
that script's live fetch/cache. Standalone CLI + tests use a default normaliser
and an optional ``--fetched-cache`` directory.

Browser-grounded confirmations are reported as ``grounded_by='browser_grounded'``
and never written onto the researcher's ``quote_verbatim_confirmed`` flag.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

TextResolver = Callable[[str], Union[Tuple[Optional[str], str], Optional[str]]]
NormaliseFn = Callable[[str], str]

_PUNCT = str.maketrans("", "", ".,;:!?\"'`“”’‘")


def default_normalise(text: str) -> str:
    """Standalone stand-in: lowercase, collapse whitespace, strip light punctuation.

    Tests/CLI only. The integrated path injects
    ``backend.app.services.fact_evidence.normalise`` (which does not case-fold).
    """
    out = (text or "").lower()
    out = re.sub(r"\s+", " ", out).strip()
    return out.translate(_PUNCT)


def derive_dedupe_key(record: dict) -> str:
    if record.get("dedupe_key"):
        return str(record["dedupe_key"])
    return (
        f"{record.get('destination_country')}"
        f"|{record.get('entity_topic_key')}"
        f"|{record.get('fact_key')}"
    )


def slug_url(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:120]


@dataclass
class QuoteVerdict:
    dedupe_key: str
    source_url: str
    evidence_quote: Optional[str]
    status: str  # confirmed | not_on_page | unreachable | no_quote
    grounded_by: Optional[str]  # http_fetch | browser_grounded | None


def grounding_text_for(url: str, grounding_dir: Path) -> Optional[str]:
    """Read captured page text for ``url`` from a grounding directory.

    ``index.json`` mapping ``source_url -> relative .txt`` is authoritative when
    the URL is listed. If the index is absent, or has no entry for this URL,
    fall back to ``<slug(url)>.txt``.
    """
    index_path = grounding_dir / "index.json"
    if index_path.is_file():
        try:
            mapping = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            mapping = {}
        if isinstance(mapping, dict) and url in mapping:
            path = grounding_dir / str(mapping[url])
            if path.is_file():
                return path.read_text(encoding="utf-8")
            return None
    slug_path = grounding_dir / f"{slug_url(url)}.txt"
    if slug_path.is_file():
        return slug_path.read_text(encoding="utf-8")
    return None


def load_text_index(cache_dir: Path) -> Dict[str, str]:
    """Load URL -> page text from a cache dir (``index.json`` + files)."""
    fetched: Dict[str, str] = {}
    index_path = cache_dir / "index.json"
    if index_path.is_file():
        mapping = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(mapping, dict):
            for url, rel in mapping.items():
                path = cache_dir / str(rel)
                if path.is_file():
                    fetched[str(url)] = path.read_text(encoding="utf-8")
        return fetched
    for txt in cache_dir.glob("*.txt"):
        fetched[txt.stem] = txt.read_text(encoding="utf-8")
    return fetched


def make_text_resolver(
    fetched: Dict[str, str],
    grounding_dir: Optional[Path],
) -> Callable[[str], Tuple[Optional[str], str]]:
    def resolve(url: str) -> Tuple[Optional[str], str]:
        if grounding_dir is not None:
            g = grounding_text_for(url, grounding_dir)
            if g is not None:
                return g, "browser_grounded"
        t = fetched.get(url)
        return (t, "http_fetch") if t is not None else (None, "http_fetch")

    return resolve


def check_quotes(
    records: List[dict],
    *,
    text_for_url: TextResolver,
    normalise: NormaliseFn,
) -> List[QuoteVerdict]:
    verdicts: List[QuoteVerdict] = []
    for rec in records:
        key = derive_dedupe_key(rec)
        url = str(rec.get("source_url") or "")
        raw_quote = rec.get("evidence_quote")
        quote: Optional[str]
        if raw_quote is None or not str(raw_quote).strip():
            quote = None
            verdicts.append(
                QuoteVerdict(
                    dedupe_key=key,
                    source_url=url,
                    evidence_quote=None,
                    status="no_quote",
                    grounded_by=None,
                )
            )
            continue
        quote = str(raw_quote)
        resolved = text_for_url(url)
        if isinstance(resolved, tuple):
            page_text = resolved[0]
            tag = resolved[1] if len(resolved) > 1 else "http_fetch"
        else:
            page_text, tag = resolved, "http_fetch"
        if page_text is None:
            verdicts.append(
                QuoteVerdict(
                    dedupe_key=key,
                    source_url=url,
                    evidence_quote=quote,
                    status="unreachable",
                    grounded_by=None,
                )
            )
            continue
        present = normalise(quote) in normalise(page_text)
        verdicts.append(
            QuoteVerdict(
                dedupe_key=key,
                source_url=url,
                evidence_quote=quote,
                status="confirmed" if present else "not_on_page",
                grounded_by=tag or "http_fetch",
            )
        )
    return verdicts


def build_report(
    verdicts: Iterable[QuoteVerdict],
    *,
    ndjson: str,
    grounding_dir: Optional[str],
) -> dict:
    items = list(verdicts)
    counts = Counter(v.status for v in items)
    by = Counter(v.grounded_by for v in items if v.grounded_by)
    needs = [
        {
            "source_url": v.source_url,
            "evidence_quote": v.evidence_quote,
            "dedupe_key": v.dedupe_key,
        }
        for v in items
        if v.status == "unreachable"
    ]
    return {
        "ndjson": ndjson,
        "grounding_dir": grounding_dir,
        "counts": {
            "confirmed": counts.get("confirmed", 0),
            "not_on_page": counts.get("not_on_page", 0),
            "unreachable": counts.get("unreachable", 0),
            "no_quote": counts.get("no_quote", 0),
        },
        "grounded_by": {
            "http_fetch": by.get("http_fetch", 0),
            "browser_grounded": by.get("browser_grounded", 0),
        },
        "needs_grounding": needs,
        "verdicts": [
            {
                "dedupe_key": v.dedupe_key,
                "source_url": v.source_url,
                "status": v.status,
                "grounded_by": v.grounded_by,
            }
            for v in items
        ],
    }


def load_ndjson(path: Path) -> List[dict]:
    rows: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def gating_exit(verdicts: Sequence[QuoteVerdict]) -> int:
    # `no_quote` gates too. A fact with no evidence_quote can never be verbatim-confirmed, so it
    # is exactly as unservable as one whose quote is not on the page — and letting it pass was the
    # same class of hole as the empty-string substring bug (norm("") is a substring of anything).
    # A quote-less row is a batch defect to fix or withhold, not a silent pass.
    if any(v.status in ("not_on_page", "unreachable", "no_quote") for v in verdicts):
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ndjson", type=Path, help="fact stream (one JSON object per line)")
    ap.add_argument("--grounding-dir", type=Path, default=None)
    ap.add_argument("--fetched-cache", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args(argv)

    if not args.ndjson.is_file():
        print(f"usage: ndjson not found: {args.ndjson}", file=sys.stderr)
        return 2

    records = load_ndjson(args.ndjson)
    fetched: Dict[str, str] = {}
    if args.fetched_cache is not None:
        fetched = load_text_index(args.fetched_cache)

    resolver = make_text_resolver(fetched, args.grounding_dir)
    verdicts = check_quotes(records, text_for_url=resolver, normalise=default_normalise)
    report = build_report(
        verdicts,
        ndjson=str(args.ndjson),
        grounding_dir=str(args.grounding_dir) if args.grounding_dir is not None else None,
    )
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    c = report["counts"]
    print(
        f"quotes: confirmed={c['confirmed']} not_on_page={c['not_on_page']} "
        f"unreachable={c['unreachable']} no_quote={c['no_quote']}"
    )
    return gating_exit(verdicts)


if __name__ == "__main__":
    raise SystemExit(main())

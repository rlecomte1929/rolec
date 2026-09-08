#!/usr/bin/env python3
"""Check that every `evidence_quote` in a batch actually appears on the page it cites.

Nothing in this repo did this. `check_corridor_facts` asserts a quote is present and long
enough; the delivery gate asserts it is non-empty. Neither ever opened the source. That gap is
how production came to hold 705 facts whose quote is not a substring of the document they cite,
and 74 approved facts served with `evidence_verified = FALSE`.

It also produces the SOURCE TEXT the promotion needs. `requirement_facts.source_doc_id` is NOT
NULL, and 8 of the ES→IE batch's 10 URLs had no `knowledge_docs` row. The alternative — a
placeholder document — is precisely what makes a quote unverifiable forever, so the text is
fetched and stored instead.

NORMALISATION, and why each step is not cheating:
  * HTML is stripped, entities decoded, whitespace collapsed. A quote is about words, not markup.
  * Curly quotes/apostrophes, en/em dashes and hyphens are folded, because a source and a
    researcher's clipboard routinely disagree on those and the words are identical.
  * List bullets are dropped and a space before `,.;:!?)` is closed up: stripping `<li>` and
    `<a>` leaves `note :` and `(dsp) .` where the page renders `note:` and `(dsp).`.
  * Nothing reorders, drops or substitutes a WORD. A paraphrase still fails, which is the
    entire point.

PDFs are extracted with pypdf — the Irish health-entitlement primary
(HSE National Assessment Guidelines) is a 53-page PDF served from an HTML-looking URL, and
regex-stripping it yields binary noise that reads exactly like a dead source.

Quote matching is delegated to ``backend.imports.otto.quote_grounding.check_quotes`` with
this module's ``norm`` (``fact_evidence.normalise`` + case-fold). Browser-grounded hits are
tagged ``grounded_by='browser_grounded'`` and are never written as
``applies_to.quote_verbatim_confirmed``.

Usage:
    python3 scripts/verify_batch_quotes.py <batch-dir> [--refetch]
        [--grounding-dir DIR] [--report JSON] [--target NDJSON] [--stamp]
Exit code is non-zero if any quote is not found or any source is unreachable.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.fact_evidence import normalise as _normalise  # noqa: E402
from backend.imports.otto.quote_grounding import (  # noqa: E402
    build_report,
    check_quotes,
    derive_dedupe_key,
    grounding_text_for,
    make_text_resolver,
)

UA = "Mozilla/5.0 (compatible; ReloPass-evidence-check/1.0)"


def fetch(url: str) -> bytes:
    """curl, not urllib. Several statutory sites (the French ones especially) sit behind a WAF
    that answers urllib with 403 and curl with 200, so a urllib fetch reports a live source as
    dead — the same false negative that once had us replacing a working HSE URL."""
    proc = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "60", "-A", UA, url],
        capture_output=True, check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"fetch failed ({proc.returncode}): {proc.stderr.decode()[:200]}")
    return proc.stdout


def to_text(raw: bytes) -> str:
    if raw[:5] == b"%PDF-":
        import io

        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    s = raw.decode("utf-8", errors="ignore")
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html.unescape(s)


def norm(s: str) -> str:
    """Delegates. There is one quote normaliser and it lives with the evidence semantics.

    This function used to carry its own copy, and it drifted: it folded every dash and every
    "/" into a space, which merges "e-mail" into "e mail" and destroys "and/or". Those change
    words, not markup. Meanwhile a third, hand-rolled SQL copy lagged behind BOTH and
    under-verified 9 Irish facts and then 3 French ones on consecutive runs — each time looking
    like a data problem and each time being a normalisation problem.

    `fact_evidence.normalise` is now the definition; this only adds the case-fold, because that
    module deliberately preserves case so a reviewer is shown the real sentence.
    """
    return _normalise(s).lower()


def _select_stream(batch_dir: Path, target: Optional[Path]) -> Path:
    if target is not None:
        if target.is_file():
            return target
        cand = batch_dir / target
        if cand.is_file():
            return cand
        raise FileNotFoundError(f"--target not found: {target}")
    return next(p for p in sorted(batch_dir.glob("*.ndjson")) if ".flat." not in p.name)


def _http_fetched(sources_dir: Path, index: dict, urls: list[str]) -> dict[str, str]:
    fetched: dict[str, str] = {}
    for url in urls:
        meta = index.get(url)
        if not isinstance(meta, dict):
            continue
        name = meta.get("file")
        if not name:
            continue
        path = sources_dir / str(name)
        if path.is_file():
            fetched[url] = path.read_text(encoding="utf-8")
    return fetched


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_dir", type=Path)
    ap.add_argument("--refetch", action="store_true", help="re-download even if cached")
    ap.add_argument("--stamp", action="store_true",
                    help="write applies_to.quote_verbatim_confirmed on each row from THIS HTTP check")
    ap.add_argument("--grounding-dir", type=Path, default=None,
                    help="browser-captured page text (index.json + .txt); wins over HTTP cache")
    ap.add_argument("--report", type=Path, default=None,
                    help="write machine-readable per-source verdicts")
    ap.add_argument("--target", type=Path, default=None,
                    help="NDJSON to check (file or name under batch-dir); default: first *.ndjson")
    args = ap.parse_args(argv)

    try:
        stream = _select_stream(args.batch_dir, args.target)
    except (FileNotFoundError, StopIteration) as exc:
        print(f"usage: {exc}", file=sys.stderr)
        return 2

    rows = [json.loads(l) for l in stream.read_text().splitlines() if l.strip()]
    sources_dir = args.batch_dir / "sources"
    sources_dir.mkdir(exist_ok=True)
    index_path = sources_dir / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    fetch_failed: list[str] = []

    urls = sorted({r.get("source_url") for r in rows if r.get("source_url")})
    for url in urls:
        if args.grounding_dir is not None and grounding_text_for(url, args.grounding_dir) is not None:
            continue
        slug = hashlib.sha256(url.encode()).hexdigest()[:16]
        txt_path = sources_dir / f"{slug}.txt"
        if args.refetch or not txt_path.exists():
            try:
                raw = fetch(url)
            except RuntimeError as exc:
                print(f"  FETCH FAILED: {url}\n    {exc}")
                fetch_failed.append(url)
                continue
            text = to_text(raw)
            txt_path.write_text(text)
            index[url] = {
                "file": txt_path.name,
                "bytes_fetched": len(raw),
                "text_chars": len(text),
                "sha256_of_text": hashlib.sha256(text.encode()).hexdigest(),
                "is_pdf": raw[:5] == b"%PDF-",
            }
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")

    fetched = _http_fetched(sources_dir, index, urls)
    resolver = make_text_resolver(fetched, args.grounding_dir)
    verdicts = check_quotes(rows, text_for_url=resolver, normalise=norm)

    report = build_report(
        verdicts,
        ndjson=str(stream),
        grounding_dir=str(args.grounding_dir) if args.grounding_dir is not None else None,
    )
    report["sources"] = [
        {
            "source_url": v.source_url,
            "evidence_quote": v.evidence_quote,
            "dedupe_key": v.dedupe_key,
            "status": v.status,
            "grounded_by": v.grounded_by,
        }
        for v in verdicts
    ]
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.stamp:
        # Records what THIS HTTP check confirmed. Browser-grounded confirmations are a
        # distinct provenance and must never be laundered into the researcher's flag.
        by_key = {v.dedupe_key: v for v in verdicts}
        for row in rows:
            key = derive_dedupe_key(row)
            v = by_key.get(key)
            http_ok = (
                v is not None
                and v.status == "confirmed"
                and v.grounded_by == "http_fetch"
            )
            row.setdefault("applies_to", {})["quote_verbatim_confirmed"] = bool(http_ok)
        stream.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(f"stamped quote_verbatim_confirmed on {len(rows)} rows in {stream.name}")

    missing = [v.dedupe_key for v in verdicts if v.status == "not_on_page"]
    unreachable = [v.source_url for v in verdicts if v.status == "unreachable"]
    confirmed = sum(1 for v in verdicts if v.status == "confirmed")
    checked = sum(1 for v in verdicts if v.status in ("confirmed", "not_on_page"))
    print(
        f"{stream.name}: {confirmed}/{checked} quotes verbatim-present"
        + (f" ({len(unreachable)} unchecked — source unreachable)" if unreachable else "")
    )
    for key in missing:
        print(f"  NOT FOUND: {key}")
    for url in list(dict.fromkeys(unreachable + fetch_failed)):
        print(f"  UNREACHABLE: {url}")
    return 1 if (missing or unreachable) else 0


if __name__ == "__main__":
    raise SystemExit(main())

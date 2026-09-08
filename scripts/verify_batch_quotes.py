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

Usage:
    python3 scripts/verify_batch_quotes.py <batch-dir> [--refetch]
Exit code is non-zero if any quote is not found, so this can gate a batch.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.fact_evidence import normalise as _normalise  # noqa: E402
from backend.imports.otto import quote_grounding  # noqa: E402

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
        import pypdf, io
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_dir", type=Path)
    ap.add_argument("--refetch", action="store_true", help="re-download even if cached")
    ap.add_argument("--stamp", action="store_true",
                    help="write applies_to.quote_verbatim_confirmed on each row from THIS check")
    ap.add_argument("--target", type=Path, default=None,
                    help="explicit NDJSON to check (default: the batch dir's non-.flat stream)")
    ap.add_argument("--grounding-dir", type=Path, default=None,
                    help="applier-captured page text (index.json + <slug>.txt); grounded text wins over the fetch")
    ap.add_argument("--report", type=Path, default=None,
                    help="write the machine-readable quote report the harness reads to decide the pause")
    args = ap.parse_args()

    stream = args.target if args.target else next(
        p for p in sorted(args.batch_dir.glob("*.ndjson")) if ".flat." not in p.name)
    rows = [json.loads(l) for l in stream.read_text().splitlines() if l.strip()]
    sources_dir = args.batch_dir / "sources"
    sources_dir.mkdir(exist_ok=True)
    index_path = sources_dir / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    unreachable: list[str] = []

    urls = sorted({r["source_url"] for r in rows})
    for url in urls:
        slug = hashlib.sha256(url.encode()).hexdigest()[:16]
        txt_path = sources_dir / f"{slug}.txt"
        if args.refetch or not txt_path.exists():
            try:
                raw = fetch(url)
            except RuntimeError as exc:
                print(f"  FETCH FAILED: {url}\n    {exc}")
                unreachable.append(url)
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

    pages = {u: norm((sources_dir / index[u]["file"]).read_text()) for u in urls if u in index}
    missing, unchecked = [], []
    for r in rows:
        page = pages.get(r["source_url"])
        if page is None:
            unchecked.append(r["fact_key"])
        elif norm(r["evidence_quote"] or "") not in page:
            missing.append(r["fact_key"])

    if args.stamp:
        # The flag records what WE confirmed, never what a deliverable claimed. A batch that
        # marks its own quotes confirmed is asserting the thing under test.
        for row in rows:
            page = pages.get(row["source_url"])
            row.setdefault("applies_to", {})["quote_verbatim_confirmed"] = bool(
                page is not None and norm(row["evidence_quote"] or "") in page
            )
        stream.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(f"stamped quote_verbatim_confirmed on {len(rows)} rows in {stream.name}")

    checked = len(rows) - len(unchecked)
    print(f"{stream.name}: {checked - len(missing)}/{checked} quotes verbatim-present"
          + (f" ({len(unchecked)} unchecked — source unreachable)" if unchecked else ""))
    for key in missing:
        print(f"  NOT FOUND: {key}")
    for url in unreachable:
        print(f"  UNREACHABLE: {url}")

    # Grafted (Brief B): the machine-readable report + grounding-dir path. Uses the SAME `norm`
    # as the legacy check above, so with no --grounding-dir the verdicts agree by construction;
    # a --grounding-dir lets an applier's browser capture confirm a source the HTTP fetch could
    # not reach (reported grounded_by='browser_grounded', never the researcher's flag).
    if args.report is not None or args.grounding_dir is not None:
        fetched = {u: (sources_dir / index[u]["file"]).read_text() for u in urls if u in index}
        resolver = quote_grounding.make_text_resolver(fetched, args.grounding_dir)
        verdicts = quote_grounding.check_quotes(rows, text_for_url=resolver, normalise=norm)
        if args.report is not None:
            report = quote_grounding.build_report(
                verdicts, ndjson=str(stream),
                grounding_dir=str(args.grounding_dir) if args.grounding_dir else None)
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")
        return quote_grounding.gating_exit(verdicts)

    # An unreachable source is not a pass. It is also not a disproof — say which it is.
    return 1 if (missing or unreachable) else 0


if __name__ == "__main__":
    raise SystemExit(main())

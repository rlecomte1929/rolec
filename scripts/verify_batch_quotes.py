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
import unicodedata
from pathlib import Path

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
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[‘’ʼ′']", "'", s)
    s = re.sub(r"[“”]", '"', s)
    s = re.sub(r"[‐-―\-]", " ", s)
    s = s.replace(" ", " ")
    s = re.sub(r"[•·▪◦]", " ", s)
    # service-public.fr renders a literal `titlecontent` template token inside its sentences
    # (a tooltip anchor). It is site furniture, not text a reader or a researcher ever sees.
    s = re.sub(r"\btitlecontent\b", " ", s, flags=re.I)
    # A researcher copying a bulleted list flattens it with "/" where the page uses list items.
    s = s.replace("/", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,.;:!?)])", r"\1", s)
    # French elision across a tag boundary: service-public.fr and CLEISS render "L' article"
    # where the sentence reads "l'article", because the elided article sits in its own element.
    s = re.sub(r"(')\s+", r"\1", s)
    return s.strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_dir", type=Path)
    ap.add_argument("--refetch", action="store_true", help="re-download even if cached")
    args = ap.parse_args()

    stream = next(p for p in sorted(args.batch_dir.glob("*.ndjson")) if ".flat." not in p.name)
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

    checked = len(rows) - len(unchecked)
    print(f"{stream.name}: {checked - len(missing)}/{checked} quotes verbatim-present"
          + (f" ({len(unchecked)} unchecked — source unreachable)" if unchecked else ""))
    for key in missing:
        print(f"  NOT FOUND: {key}")
    for url in unreachable:
        print(f"  UNREACHABLE: {url}")
    # An unreachable source is not a pass. It is also not a disproof — say which it is.
    return 1 if (missing or unreachable) else 0


if __name__ == "__main__":
    raise SystemExit(main())

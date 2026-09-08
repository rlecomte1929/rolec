#!/usr/bin/env python3
"""confirm_quotes.py — independent quote-confirmation referee for Otto fact batches.

Complements ``scripts/verify_ledger.py``. verify_ledger's HTTP fetcher is blind to three
things that recur constantly on official government sources: PDF binaries, WAF/JS-gated
portals, and non-UTF-8 encodings. Across the 2026-08-31 destination-coverage campaign the
applier hand-ran the same investigation every time a source failed to confirm, and the
failure modes turned out to cluster into a small, learnable taxonomy. This tool encodes
that taxonomy as a deterministic classifier and emits, per fact:

  - a VERDICT (below), and
  - a machine-readable outcome row appended to a shared ledger — the accumulating
    "training signal" that lets the priors (docs/imports/_verification_priors.md) and the
    thresholds here improve over time instead of living only in one operator's head.

VERDICTS
  CONFIRMED        quote reproduced verbatim (exact substring, OR >= BIGRAM_OK word-bigram
                   overlap through markup, OR after re-decoding latin-1/cp1252).
  REVIEW_BROWSER   source blocked/tiny/JS-shell, OR a borderline match — cannot decide from
                   a headless fetch; confirm in a real browser before promoting.
  HOLD_IMAGE_PDF   `%PDF` with no extractable text layer in any extractor (scanned image) —
                   re-source via OCR or the rendered HTML equivalent.
  HOLD_WRONG_SRC   the source extracted plenty of text but the quote shares almost none of
                   it — the cited URL is almost certainly wrong (misattribution).
  HOLD_ABSENT      text extracted fine and is topically related, but the quote is genuinely
                   not on the page.

The land/hold rule the campaign settled on: promote CONFIRMED; browser-verify REVIEW_BROWSER
and promote only if it checks out; never promote a HOLD_* on the researcher's say-so.

Usage:
  python scripts/confirm_quotes.py docs/imports/<batch>/facts.ndjson
  python scripts/confirm_quotes.py <batch>/facts.ndjson --ledger docs/imports/_verification_ledger.ndjson

Advisory only: always exits 0. Writes <batch-dir>/confirm_report.json and appends one
ledger row per fact. Requires curl on PATH; pypdf and pdfplumber for PDFs (optional —
degrades to "extractor unavailable" which is treated as REVIEW_BROWSER, never CONFIRMED).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from urllib.parse import urlsplit

# Thresholds — tuned on the campaign's hand-labelled outcomes. Change here, re-run against a
# labelled batch, and check the confusion counts before trusting a new value.
BIGRAM_OK = 0.85        # >= this word-bigram overlap counts as confirmed (markup-split quotes)
BIGRAM_MID = 0.5        # [MID, OK): quote is probably present but markup-split => browser-confirm
BIGRAM_WRONG = 0.15     # text-rich source but < this overlap => the cited URL is wrong
MIN_TEXT_RICH = 500     # chars of extracted text below which we don't call a source "text-rich"
MIN_BODY_BYTES = 800    # response smaller than this is a stub/block, not a page
# A genuinely-wrong large source (scanned/scrambled PDF, misattributed URL) extracts a LOT of
# text at ~0 overlap. A WAF/JS challenge page also extracts "text" at 0 overlap but is small and
# carries challenge markers — that is a BLOCK to route to the browser, not a wrong source. This
# floor + the markers below were added after gov.cy (an 8 KB WAF interstitial) was false-held as
# HOLD_WRONG_SRC — the ledger doing its job.
WRONG_SRC_MINCHARS = 25000
WAF_MARKERS = (
    "just a moment", "enable javascript", "captcha", "cloudflare", "attention required",
    "access denied", "incapsula", "cf-browser-verification", "challenge-platform",
    "请开启", "verifying you are human", "ddos-guard",
)
FETCH_TIMEOUT = 40


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _words(s: str):
    return re.findall(r"[a-z0-9]+", s)


def _bigrams(s: str):
    w = _words(s)
    return set(zip(w, w[1:]))


def _curl(url: str) -> bytes:
    fn = tempfile.mktemp()
    try:
        subprocess.run(
            ["curl", "-sL", "--max-time", str(FETCH_TIMEOUT), "-A", "Mozilla/5.0", "-o", fn, url],
            check=False,
        )
        with open(fn, "rb") as fh:
            return fh.read()
    except Exception:
        return b""
    finally:
        try:
            os.remove(fn)
        except OSError:
            pass


def _pdf_texts(raw: bytes):
    """Return {method: normalised_text} for every PDF extractor available."""
    out = {}
    fn = tempfile.mktemp(suffix=".pdf")
    with open(fn, "wb") as fh:
        fh.write(raw)
    try:
        try:
            import pdfplumber

            with pdfplumber.open(fn) as pdf:
                out["pdfplumber"] = _norm(" ".join((p.extract_text() or "") for p in pdf.pages))
                out["pdfplumber_layout"] = _norm(
                    " ".join((p.extract_text(layout=True) or "") for p in pdf.pages)
                )
        except Exception:
            pass
        try:
            from pypdf import PdfReader

            out["pypdf"] = _norm(" ".join((p.extract_text() or "") for p in PdfReader(fn).pages))
        except Exception:
            pass
    finally:
        try:
            os.remove(fn)
        except OSError:
            pass
    return out


def _html_texts(raw: bytes):
    """Return {encoding: normalised_text} — the encoding cascade that catches latin-1 pages."""
    out = {}
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            out[enc] = _norm(raw.decode(enc, errors="ignore"))
        except Exception:
            continue
    return out


def _best_match(quote: str, texts: dict):
    """Best (full, bigram_frac, method) across all candidate extractions of one source."""
    q = _norm(quote)
    qb = _bigrams(q)
    best = (False, 0.0, None)
    for method, txt in texts.items():
        if not txt or txt.startswith("__"):
            continue
        full = q in txt
        frac = (len(qb & _bigrams(txt)) / len(qb)) if qb else (1.0 if full else 0.0)
        if (full, frac) > (best[0], best[1]):
            best = (full, frac, method)
    return best


def classify(rec: dict, cache: dict):
    """Fetch + classify one fact. Returns an outcome dict (also the ledger row shape)."""
    url = rec.get("source_url", "")
    host = (urlsplit(url).hostname or "").lower().lstrip(".")
    quote = rec.get("evidence_quote", "")
    if url not in cache:
        cache[url] = _curl(url)
    raw = cache[url]
    is_pdf = raw.startswith(b"%PDF")  # NB: `raw[:5] == b"%PDF"` is always False (5-byte slice vs 4-byte literal)
    ctype = "pdf" if is_pdf else "html"

    if len(raw) < MIN_BODY_BYTES and not is_pdf:
        return _row(rec, host, ctype, "REVIEW_BROWSER", 0.0, None, "blocked/stub response")

    texts = _pdf_texts(raw) if is_pdf else _html_texts(raw)
    max_chars = max((len(t) for t in texts.values() if isinstance(t, str)), default=0)

    if is_pdf and max_chars == 0:
        # Either a scanned/image PDF or no extractor installed. Either way: not confirmable here.
        why = "image/scanned PDF (0 extractable chars)" if texts else "no PDF extractor available"
        return _row(rec, host, ctype, "HOLD_IMAGE_PDF" if texts else "REVIEW_BROWSER",
                    0.0, None, why)

    full, frac, method = _best_match(quote, texts)
    if full or frac >= BIGRAM_OK:
        return _row(rec, host, ctype, "CONFIRMED", frac, method,
                    "exact" if full else f"{frac:.0%} bigram")
    if frac >= BIGRAM_MID:
        # Present but not contiguous (HTML markup / PDF column layout splits the exact string).
        # verify_ledger's own fetch resolved several of these; a browser check settles it.
        return _row(rec, host, ctype, "REVIEW_BROWSER", frac, method,
                    f"{frac:.0%} overlap — likely present but markup-split; confirm in a browser")
    # frac < BIGRAM_MID: near-zero overlap. Separate a real wrong-source from a block/challenge.
    blob = " ".join(t for t in texts.values() if isinstance(t, str))
    if any(m in blob for m in WAF_MARKERS) or max_chars < WRONG_SRC_MINCHARS:
        return _row(rec, host, ctype, "REVIEW_BROWSER", frac, method,
                    f"{max_chars} chars, {frac:.0%} overlap — looks like a WAF/JS challenge or thin "
                    "page, not the real content; confirm in a browser")
    if frac < BIGRAM_WRONG:
        return _row(rec, host, ctype, "HOLD_WRONG_SRC", frac, method,
                    f"text-rich source ({max_chars} chars) but {frac:.0%} overlap — cited URL likely wrong")
    return _row(rec, host, ctype, "HOLD_ABSENT", frac, method,
                f"page extracted ({max_chars} chars) but quote not present ({frac:.0%})")


def _row(rec, host, ctype, verdict, frac, method, reason):
    return {
        "batch": rec.get("_batch"),
        "destination_country": rec.get("destination_country"),
        "entity_topic_key": rec.get("entity_topic_key"),
        "host": host,
        "content_type": ctype,
        "verdict": verdict,
        "bigram": round(frac, 3),
        "method": method,
        "reason": reason,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ndjson", help="path to a batch facts.ndjson / clean.ndjson")
    ap.add_argument("--ledger", default="docs/imports/_verification_ledger.ndjson",
                    help="shared outcome ledger to append to (the accumulating training signal)")
    args = ap.parse_args()

    path = args.ndjson
    batch = os.path.basename(os.path.dirname(os.path.abspath(path)))
    facts = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    for f in facts:
        f["_batch"] = batch

    cache: dict = {}
    rows = [classify(f, cache) for f in facts]

    counts = Counter(r["verdict"] for r in rows)
    confirmed = [r for r in rows if r["verdict"] == "CONFIRMED"]
    print(f"== confirm_quotes: {batch} ({len(rows)} facts) ==")
    for r in rows:
        print(f"  [{r['verdict']:<14}] {r['entity_topic_key'][:26]:<26} {r['host']:<26} {r['reason']}")
    print("  verdicts:", dict(counts))
    print(f"  => CONFIRMED {len(confirmed)}/{len(rows)} (promote these); "
          f"{counts.get('REVIEW_BROWSER',0)} need a browser; "
          f"{sum(counts[k] for k in ('HOLD_IMAGE_PDF','HOLD_WRONG_SRC','HOLD_ABSENT'))} hold")

    report = os.path.join(os.path.dirname(os.path.abspath(path)), "confirm_report.json")
    with open(report, "w", encoding="utf-8") as fh:
        json.dump({"batch": batch, "counts": dict(counts), "rows": rows}, fh, indent=2, ensure_ascii=False)
    print("  wrote", report)

    if args.ledger:
        os.makedirs(os.path.dirname(args.ledger), exist_ok=True)
        with open(args.ledger, "a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("  appended", len(rows), "rows to", args.ledger)
    return 0


if __name__ == "__main__":
    sys.exit(main())

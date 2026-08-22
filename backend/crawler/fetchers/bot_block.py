"""Detect an anti-bot interstitial served in place of the page we asked for.

WHY THIS EXISTS — measured in production 2026-08-19.

Six of fifteen rows in `crawled_source_documents` were the bot-management
interstitial at `validate.perfdrive.com`, stored with `http_status = 200`,
`parse_status = 'parsed'` and `page_title = 'Radware Captcha Page'`. The crawler was
blocked, received a challenge page, and filed it as the source document while the
crawl run reported success.

That is worse than failing. A challenge page parses cleanly, hashes stably, and
diffs against itself forever — so the pipeline looks healthy while monitoring
nothing. It is also how the corpus gets poisoned: anything extracting text from
those rows would ingest CAPTCHA copy as immigration guidance.

DETECT ON STRUCTURE, NOT ON VENDOR NAMES.

The evidence in hand is Radware/Perfdrive. The next block will be Cloudflare,
Akamai, or something not yet written. A vendor allowlist fails silently on the
first vendor it does not know, which is the same shape of bug this module exists to
remove — so nothing here matches a product name. The three signals are properties of
*challenge pages in general*:

  1. the title announces a challenge rather than the page's subject;
  2. the body carries a challenge marker AND is far too small to be the document;
  3. the response was redirected off the host we asked for AND is far too small.

Each is independently sufficient. Signals 2 and 3 both require the size floor,
because a legitimate page may quote the word "captcha" or redirect between hosts —
but it will not do so in under a few kilobytes.

We do NOT try to defeat the block. A detected block is reported as a fetch failure so
a human can negotiate access or choose a different authoritative source. Evading
bot-management would be both hostile and fragile.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

#: A challenge page names the challenge; a real source page names its subject.
_CHALLENGE_TITLE_RE = re.compile(
    r"(?i)\b("
    r"captcha|are you (?:a )?human|attention required|just a moment|"
    r"security check|bot detection|access denied|verify(?:ing)? you are|"
    r"checking your browser|one more step|please wait"
    r")\b"
)

#: Markers that appear in challenge bodies across vendors. Generic phrasing and
#: challenge-platform script paths — never a vendor's product name.
_CHALLENGE_BODY_RE = re.compile(
    r"(?i)("
    r"captcha|challenge-platform|challenge_basic|jschl|"
    r"enable javascript and cookies to continue|"
    r"verify(?:ing)? (?:that )?you are (?:a )?human|"
    r"unusual traffic|automated (?:queries|requests)|"
    r"your (?:browser|request) (?:has been )?blocked"
    r")"
)

#: A challenge page is small. Real source pages we crawl are comfortably larger;
#: the six observed interstitials were a fraction of this. Used only in combination
#: with another signal, never alone — a short legitimate page must not be rejected.
SMALL_BODY_BYTES = 4096


def _host(url: str) -> str:
    """Comparable host: lowercased, `www.` stripped, port dropped."""
    try:
        netloc = (urlparse(url or "").netloc or "").lower()
    except ValueError:
        return ""
    netloc = netloc.split("@")[-1].split(":")[0]
    return netloc[4:] if netloc.startswith("www.") else netloc


def detect_bot_block(
    *,
    url: str,
    final_url: str,
    content: str,
    page_title: Optional[str] = None,
) -> Optional[str]:
    """Return a human-readable reason when this response is an interstitial, else None.

    Returning a *reason* rather than a bool is deliberate: it lands in the crawl run's
    error list, so an operator sees which signal fired and can judge a false positive
    without re-running anything.
    """
    body = content or ""
    small = len(body.encode("utf-8", errors="replace")) < SMALL_BODY_BYTES

    title = page_title or ""
    if not title:
        # Fall back to the served <title> when the caller has not parsed one yet.
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
        title = (m.group(1) if m else "").strip()

    if title and _CHALLENGE_TITLE_RE.search(title):
        return f"challenge page title: {title[:80]!r}"

    if small and _CHALLENGE_BODY_RE.search(body):
        return "challenge marker in an implausibly small body"

    requested, landed = _host(url), _host(final_url)
    if requested and landed and requested != landed and small:
        return f"redirected off-host to {landed!r} with an implausibly small body"

    return None

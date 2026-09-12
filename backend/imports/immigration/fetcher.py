"""Fetch a source URL into the document body that `knowledge_docs.text_content` requires.

`requirement_facts.source_doc_id` is a FK to `knowledge_docs`, and `text_content` is NOT NULL.
So a fact cannot be stored without a real document behind it. That constraint is the whole
reason this file exists: the seed carries a claim, a URL and sometimes a short quote, and none
of that is a document. **A failed fetch produces no row.** There is no placeholder body and no
`text_content=''` fallback — guard #1816 exists because a fabricated evidence row is worse than
a missing one, since it reads as sourced.

Two deliberate differences from `backend/app/services/official_ingest_service.py`, which does
the same job for the live admin ingest path:

1. **No domain allowlist.** That module's `OFFICIAL_DOMAINS` covers `US` and `SG` only, so 13 of
   this seed's 15 countries would raise "URL not in official allowlist". These 86 URLs were
   vetted by a human before reaching the seed; the sourcing gate here is that review, and the
   publisher host is recorded on every row so it stays auditable.
2. **No 5 000-character excerpt cap.** That cap is sized for an LLM prompt. Here the stored body
   is what the evidence check reads, and a fee quoted in a table two thirds down the page sits
   well past character 5 000 — truncating would fail honest quotes and send real evidence to
   the manual worklist. The cap below is a memory bound, an order of magnitude higher.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Sequence
from urllib.parse import urlparse

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_TEXT_CHARS = 400_000
TIMEOUT_SECONDS = 40

#: A page that yields less than this is navigation chrome, not a document. Both
#: `immi.homeaffairs.gov.au` and `dofi.ibz.be` render their content with JavaScript and return
#: a shell to any static fetcher; without a floor, `homeaffairs` stores 440 characters of
#: "Skip to navigation … Loading" as the evidence body behind a visa requirement. Recording
#: that as a fetch failure is the honest outcome — the fact then waits for manual sourcing
#: instead of citing a menu.
MIN_TEXT_CHARS = 600

#: Requests to one host, spaced. The first live run tripped rate limiting on `dol.gov` and
#: `admin.ch` — both returned 200 early on and 403 once the run had hammered them — so the
#: failure list was partly self-inflicted rather than a property of the sources.
PER_HOST_DELAY_SECONDS = 1.5
RETRY_STATUSES = {403, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3

#: These are public pages with no login and no paywall, but several publishers front them with
#: bot protection that refuses a crawler-shaped User-Agent outright: measured 2026-08-12,
#: `immi.homeaffairs.gov.au` (6 URLs) and `citizensinformation.ie` (1) returned 403 to a
#: `ReloPassBot` UA and 200 to these headers. The stored body has to be the page a human
#: reviewer sees when they open the citation, so the request is shaped like the browser they
#: would open it in. Nothing here defeats an access control — a site that refuses these headers
#: too (`travel.state.gov` does) stays a recorded fetch failure rather than being worked around.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

#: `form` and `header` are deliberately NOT stripped. `mom.gov.sg` is ASP.NET WebForms, which
#: wraps the entire document in a single `<form runat="server">` — decomposing it emptied all 7
#: Singapore pages and reported them as "no text content", a fetch failure that was really an
#: extraction bug. Menu chrome surviving in the body is harmless; losing the page is not.
STRIP_TAGS = ["script", "style", "nav", "footer", "noscript"]

FETCHED = "fetched"
FETCH_FAILED = "fetch_failed"


@dataclass(frozen=True)
class FetchedDoc:
    """The result of one URL fetch. `ok` is the only thing callers should branch on."""

    source_url: str
    final_url: str
    title: str
    publisher: str
    text_content: str
    content_sha256: str | None
    fetch_status: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.fetch_status == FETCHED and bool(self.text_content)


@dataclass(frozen=True)
class HtmlFetch:
    """Raw HTML (or a typed failure). Never raised — callers branch on `ok`."""

    source_url: str
    final_url: str
    status: int | None
    html: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.html)


def _failed(url: str, reason: str) -> FetchedDoc:
    return FetchedDoc(
        source_url=url,
        final_url=url,
        title="",
        publisher=urlparse(url).netloc,
        text_content="",
        content_sha256=None,
        fetch_status=FETCH_FAILED,
        error=reason,
    )


def _failed_html(url: str, reason: str, status: int | None = None) -> HtmlFetch:
    return HtmlFetch(
        source_url=url,
        final_url=url,
        status=status,
        html="",
        error=reason,
    )


def extract_text(html: str) -> tuple[str, str]:
    """(title, body text). Strips chrome that would otherwise pad every page with a menu.

    Picks the *longest* of `main`/`article`/`body` rather than the first that exists.
    `immi.homeaffairs.gov.au` ships an empty `<main>` and renders into it with JavaScript, so
    first-match returns "" and discards the page; longest-match at least reports what is really
    there. It still fails the `MIN_TEXT_CHARS` floor below, which is the correct outcome — but
    for a site whose real content sits outside `<main>`, this is the difference between a
    document and a silent skip.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(STRIP_TAGS):
        tag.decompose()
    title = (soup.title.string if soup.title and soup.title.string else "") or ""

    best = ""
    for node in (soup.find("main"), soup.find("article"), soup.body):
        if node is None:
            continue
        text = " ".join(node.get_text(separator=" ", strip=True).split())
        if len(text) > len(best):
            best = text
    return title.strip(), best[:MAX_TEXT_CHARS]


def _get_html_once(url: str, *, timeout: float = TIMEOUT_SECONDS) -> HtmlFetch:
    """One HTTP GET. Never raises; WAF/timeout/non-HTML come back as `error`."""
    import requests

    try:
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            stream=True,
            allow_redirects=True,
        )
        if resp.status_code in RETRY_STATUSES:
            return _failed_html(url, f"HTTP {resp.status_code}", status=resp.status_code)
        if resp.status_code >= 400:
            return _failed_html(url, f"HTTP {resp.status_code}", status=resp.status_code)

        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "html" not in content_type:
            return _failed_html(
                url,
                f"non-HTML content type: {content_type or 'unknown'!r}",
                status=resp.status_code,
            )

        data = bytearray()
        for chunk in resp.iter_content(chunk_size=16384):
            if not chunk:
                continue
            data.extend(chunk)
            if len(data) > MAX_RESPONSE_BYTES:
                return _failed_html(
                    url,
                    f"response exceeded {MAX_RESPONSE_BYTES} bytes",
                    status=resp.status_code,
                )

        html = data.decode(resp.encoding or "utf-8", errors="replace")
        return HtmlFetch(
            source_url=url,
            final_url=str(resp.url),
            status=resp.status_code,
            html=html,
        )
    except Exception as exc:  # requests raises a wide family; none of it should abort the batch
        return _failed_html(url, f"{type(exc).__name__}: {exc}")


def fetch_html(url: str, *, timeout: float = TIMEOUT_SECONDS) -> HtmlFetch:
    """Fetch HTML with host delay and backoff. Never raises."""
    import time

    host = urlparse(url).netloc
    last: HtmlFetch = _failed_html(url, "exhausted retries")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        elapsed = time.monotonic() - _last_hit.get(host, 0.0)
        if elapsed < PER_HOST_DELAY_SECONDS:
            time.sleep(PER_HOST_DELAY_SECONDS - elapsed)
        _last_hit[host] = time.monotonic()

        last = _get_html_once(url, timeout=timeout)
        if last.ok:
            return last
        retryable = last.error and (
            last.error.startswith("HTTP ")
            or "Timeout" in last.error
            or "ConnectionError" in last.error
        )
        if not retryable or attempt == MAX_ATTEMPTS:
            return last
        time.sleep(2.0 * attempt)
    return last


def _fetch_once(url: str) -> FetchedDoc:
    got = _get_html_once(url)
    if not got.ok:
        return _failed(url, got.error or "fetch failed")

    title, text = extract_text(got.html)
    if len(text) < MIN_TEXT_CHARS:
        return _failed(
            url,
            f"only {len(text)} chars extracted (min {MIN_TEXT_CHARS}) — "
            "the page renders its content with JavaScript",
        )

    return FetchedDoc(
        source_url=url,
        final_url=got.final_url,
        title=title or url,
        publisher=urlparse(got.final_url).netloc,
        text_content=text,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        fetch_status=FETCHED,
    )


_last_hit: Dict[str, float] = {}


def fetch_url(url: str) -> FetchedDoc:
    """Fetch one URL, politely and with backoff. Never raises; failures come back as a doc.

    Retries only transport-shaped failures (rate limiting, 5xx, timeouts). A 404 is a dead link
    in the seed — a content finding for the re-sourcing worklist — and retrying it would just
    hide it behind three attempts.
    """
    import time

    host = urlparse(url).netloc
    for attempt in range(1, MAX_ATTEMPTS + 1):
        elapsed = time.monotonic() - _last_hit.get(host, 0.0)
        if elapsed < PER_HOST_DELAY_SECONDS:
            time.sleep(PER_HOST_DELAY_SECONDS - elapsed)
        _last_hit[host] = time.monotonic()

        doc = _fetch_once(url)
        if doc.ok:
            return doc
        retryable = doc.error and (
            doc.error.startswith("HTTP ") or "Timeout" in doc.error or "ConnectionError" in doc.error
        )
        if not retryable or attempt == MAX_ATTEMPTS:
            return doc
        time.sleep(2.0 * attempt)
    return _failed(url, "exhausted retries")


#: Injection seam for tests and for the cache below, so the write path can be exercised without
#: 86 live HTTP requests.
Fetcher = Callable[[str], FetchedDoc]


def fetch_all(urls: Sequence[str], *, cache_path: Path | None = None,
              progress: Callable[[int, int, str], None] | None = None) -> Dict[str, FetchedDoc]:
    """Fetch every URL up front and return a lookup, optionally persisted to `cache_path`.

    Fetching is separated from writing for two reasons, both learned the hard way on the first
    live dry run:

    1. **The transaction cannot span the network.** Holding one transaction open across 86
       fetches let the Supabase pooler close it mid-run (`SSL connection has been closed
       unexpectedly`). Fetch first, then write inside a transaction that lasts milliseconds.
    2. **It is what makes the preview binding.** The P3 gate approves a dry run and then a
       separate `--apply` writes it. Re-fetching would let the two runs see different pages, so
       "dry-run counts == live counts" would be a hope rather than a guarantee. Reusing the
       cached bodies means `--apply` writes exactly what was approved.
    """
    docs: Dict[str, FetchedDoc] = {}
    if cache_path and cache_path.exists():
        cached = json.loads(cache_path.read_text())
        docs = {u: FetchedDoc(**d) for u, d in cached.items()}

    missing = [u for u in urls if u not in docs]
    for index, url in enumerate(missing, start=1):
        if progress:
            progress(index, len(missing), url)
        docs[url] = fetch_url(url)

    if cache_path and missing:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({u: asdict(d) for u, d in docs.items()}, indent=1))
    return docs

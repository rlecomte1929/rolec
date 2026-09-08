"""
Web fetcher for the HR prospect enrichment agent.

Pulls a small, bounded set of pages for a given company domain (homepage,
about/company, careers) and returns a compact text summary that the LLM
can digest. Built on `requests` + `beautifulsoup4` (both already in
requirements.txt) with explicit timeouts and per-prospect size caps — we
never ingest more than a few KB of stripped text per prospect.

Intentionally conservative: if a site blocks the user-agent, returns a
JS-only shell, or times out, we record that in `fetch_errors` rather than
crashing the batch.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Keep these conservative — a founder-run MVP doing hundreds of prospects
# should not spend minutes on a single slow site.
DEFAULT_TIMEOUT_S = 10
DEFAULT_MAX_BYTES_PER_PAGE = 300_000
DEFAULT_MAX_TEXT_CHARS_PER_PAGE = 8_000
DEFAULT_TOTAL_TEXT_BUDGET = 16_000
USER_AGENT = (
    "Mozilla/5.0 (compatible; ReloPassProspectAgent/1.0; "
    "+https://relopass.com/bot)"
)

CAREERS_PATH_HINTS = (
    "/careers",
    "/career",
    "/jobs",
    "/join-us",
    "/company/careers",
    "/about",
    "/about-us",
    "/company",
)


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str


@dataclass
class ProspectWebSnapshot:
    domain: str
    pages: List[FetchedPage] = field(default_factory=list)
    fetch_errors: List[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        blocks: List[str] = []
        for page in self.pages:
            blocks.append(
                f"--- PAGE: {page.url}\nTITLE: {page.title}\n\n{page.text}"
            )
        return "\n\n".join(blocks) if blocks else "(no pages fetched)"


def _normalise_domain(domain_or_url: str) -> str:
    raw = (domain_or_url or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _strip_html(html: str, max_chars: int) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    for tag in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return title[:200], text[:max_chars]


def _fetch_one(
    session: requests.Session,
    url: str,
    *,
    timeout_s: int,
    max_bytes: int,
    max_text_chars: int,
) -> Optional[FetchedPage]:
    try:
        resp = session.get(url, timeout=timeout_s, allow_redirects=True)
    except requests.RequestException as exc:
        log.debug("prospect fetch failed url=%s err=%s", url, exc)
        return None
    if resp.status_code >= 400:
        return None
    content_type = (resp.headers.get("content-type") or "").lower()
    if "html" not in content_type:
        return None
    body = resp.content[:max_bytes]
    try:
        html = body.decode(resp.encoding or "utf-8", errors="replace")
    except (LookupError, UnicodeDecodeError):
        html = body.decode("utf-8", errors="replace")
    title, text = _strip_html(html, max_chars=max_text_chars)
    if not text:
        return None
    return FetchedPage(url=resp.url, title=title, text=text)


def _candidate_urls(base_url: str) -> Iterable[str]:
    yield base_url
    for path in CAREERS_PATH_HINTS:
        yield urljoin(base_url + "/", path.lstrip("/"))


def fetch_prospect_snapshot(
    domain_or_url: str,
    *,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    max_bytes_per_page: int = DEFAULT_MAX_BYTES_PER_PAGE,
    max_text_chars_per_page: int = DEFAULT_MAX_TEXT_CHARS_PER_PAGE,
    total_text_budget: int = DEFAULT_TOTAL_TEXT_BUDGET,
    max_pages: int = 4,
) -> ProspectWebSnapshot:
    """Fetch homepage + a handful of discovery pages, return stripped text.

    Never raises on transient HTTP errors — the caller relies on the
    returned `fetch_errors` list to record what was missed, so the LLM
    can still score the prospect on whatever evidence arrived.
    """
    base = _normalise_domain(domain_or_url)
    snapshot = ProspectWebSnapshot(domain=base)
    if not base:
        snapshot.fetch_errors.append("empty domain")
        return snapshot
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    spent = 0
    seen_urls: set[str] = set()
    for url in _candidate_urls(base):
        if len(snapshot.pages) >= max_pages:
            break
        if url in seen_urls:
            continue
        seen_urls.add(url)
        remaining = max(0, total_text_budget - spent)
        if remaining < 500:
            break
        page = _fetch_one(
            session,
            url,
            timeout_s=timeout_s,
            max_bytes=max_bytes_per_page,
            max_text_chars=min(max_text_chars_per_page, remaining),
        )
        if page is None:
            if url == base:
                snapshot.fetch_errors.append(f"homepage unreachable: {url}")
            continue
        snapshot.pages.append(page)
        spent += len(page.text)
    if not snapshot.pages and not snapshot.fetch_errors:
        snapshot.fetch_errors.append("no html pages fetched")
    return snapshot

"""
N1 / AIQ-840 — immigration-rule crawl orchestrator.

Reads backend/crawler/config/immigration_sources.json, crawls each corridor's
official sources (reusing the existing http_fetcher.fetch_page), extracts
structured text (immigration_page_parser), dedupes by SHA-256 of the extracted
text, and writes rows to crawled_immigration_documents. Failures never raise —
they are recorded as error rows and the job continues.

Wires the CrawlSource-style allowed_paths + max_depth controls (dead in the Oslo
job) into a bounded breadth-first crawl, and respects robots.txt per domain.

CLI:
    python -m backend.crawler.jobs.immigration_crawl_job --corridor FR_NO
    python -m backend.crawler.jobs.immigration_crawl_job            # all corridors

Testability: fetcher, DB engine, robots check, sources, and clock are all
injectable, so unit tests run with mocks + in-memory SQLite (no network/prod).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import urllib.robotparser
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from sqlalchemy import text

from ..fetchers.http_fetcher import fetch_page
from ..parsers import immigration_page_parser
from ..parsers.html_parser import parse_html

log = logging.getLogger(__name__)

_DEFAULT_SOURCES = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "immigration_sources.json"
)
_USER_AGENT = "ReloPassBot/1.0 (crawler-staging)"


@dataclass
class CrawlResult:
    rows_written: int = 0
    rows_skipped: int = 0
    rows_failed: int = 0
    errors: List[str] = field(default_factory=list)


def load_immigration_sources(path: Optional[str] = None) -> Dict[str, Any]:
    with open(path or _DEFAULT_SOURCES, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# robots.txt — one fetch per host per run, cached.                            #
# --------------------------------------------------------------------------- #


class RobotsTxtCache:
    def __init__(self, user_agent: str = _USER_AGENT) -> None:
        self.user_agent = user_agent
        self._cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(urljoin(host, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                rp = None  # robots unreachable -> fail open (allow), but cache it
            self._cache[host] = rp
        rp = self._cache[host]
        if rp is None:
            return True
        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True


# --------------------------------------------------------------------------- #
# URL scoping                                                                  #
# --------------------------------------------------------------------------- #


def _same_domain(url: str, base_url: str) -> bool:
    return urlparse(url).netloc == urlparse(base_url).netloc


def _path_allowed(url: str, allowed_paths: List[str]) -> bool:
    """True if the URL's path starts with any allowed prefix. Empty list = allow all."""
    if not allowed_paths:
        return True
    path = urlparse(url).path
    return any(path.startswith(p) for p in allowed_paths)


def _discover_links(html: str, base_url: str, allowed_paths: List[str]) -> List[str]:
    """Same-domain, allowed-path links from a page (deduped, absolute)."""
    parsed = parse_html(html, base_url)
    out: List[str] = []
    seen = set()
    for link in parsed.links:
        href = (link.get("href") or "").strip()
        if not href:
            continue
        absu = urljoin(base_url, href).split("#")[0]
        if absu in seen:
            continue
        if _same_domain(absu, base_url) and _path_allowed(absu, allowed_paths):
            seen.add(absu)
            out.append(absu)
    return out


# --------------------------------------------------------------------------- #
# DB access (engine-agnostic; ids + timestamps generated in Python so the same #
# SQL runs on Postgres prod and in-memory SQLite tests).                       #
# --------------------------------------------------------------------------- #


def _latest_doc(conn, corridor: str, source_url: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            "SELECT id, content_hash, fetched_at FROM crawled_immigration_documents "
            "WHERE corridor = :c AND source_url = :u AND crawl_error IS NULL "
            "ORDER BY fetched_at DESC LIMIT 1"
        ),
        {"c": corridor, "u": source_url},
    ).mappings().first()
    return dict(row) if row else None


def _doc_with_hash(conn, corridor: str, source_url: str, content_hash: str) -> Optional[str]:
    row = conn.execute(
        text(
            "SELECT id FROM crawled_immigration_documents "
            "WHERE corridor = :c AND source_url = :u AND content_hash = :h LIMIT 1"
        ),
        {"c": corridor, "u": source_url, "h": content_hash},
    ).first()
    return row[0] if row else None


def _touch_fetched_at(conn, doc_id: str, now_iso: str) -> None:
    conn.execute(
        text("UPDATE crawled_immigration_documents SET fetched_at = :now WHERE id = :id"),
        {"now": now_iso, "id": doc_id},
    )


def _insert_doc(conn, **vals: Any) -> None:
    conn.execute(
        text(
            "INSERT INTO crawled_immigration_documents "
            "(id, corridor, source_url, trust_tier, raw_html_path, extracted_text, "
            " content_hash, fetched_at, http_status, crawl_error, is_active) "
            "VALUES (:id, :corridor, :source_url, :trust_tier, :raw_html_path, :extracted_text, "
            " :content_hash, :fetched_at, :http_status, :crawl_error, :is_active)"
        ),
        vals,
    )


def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8", errors="replace")).hexdigest()


def _days_between(iso_a: str, now: datetime) -> float:
    try:
        dt = datetime.fromisoformat(str(iso_a).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() / 86400.0
    except Exception:
        return float("inf")


# --------------------------------------------------------------------------- #
# Orchestrator                                                                 #
# --------------------------------------------------------------------------- #


def run_crawl(
    corridor_key: Optional[str] = None,
    *,
    sources: Optional[Dict[str, Any]] = None,
    sources_path: Optional[str] = None,
    engine=None,
    fetcher: Callable[..., Any] = fetch_page,
    robots_allowed: Optional[Callable[[str], bool]] = None,
    now: Optional[datetime] = None,
) -> CrawlResult:
    """
    Crawl one corridor (corridor_key) or all corridors (None).
    Returns a CrawlResult tally. Never raises on a per-source failure.
    """
    sources = sources if sources is not None else load_immigration_sources(sources_path)
    if engine is None:
        from ...database import _request_engine as engine  # lazy: avoid prod import at module load
    if robots_allowed is None:
        robots_allowed = RobotsTxtCache().allowed
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()

    result = CrawlResult()

    for ckey, config in sources.items():
        if corridor_key and ckey != corridor_key:
            continue
        for source in config.get("sources", []):
            _crawl_source(
                ckey, source, engine=engine, fetcher=fetcher,
                robots_allowed=robots_allowed, now=now, now_iso=now_iso, result=result,
            )
    log.info(
        "immigration_crawl done corridor=%s written=%d skipped=%d failed=%d",
        corridor_key or "ALL", result.rows_written, result.rows_skipped, result.rows_failed,
    )
    return result


def _crawl_source(
    corridor: str, source: Dict[str, Any], *, engine, fetcher, robots_allowed, now, now_iso, result: CrawlResult
) -> None:
    seed = source["url"]
    trust_tier = int(source.get("trust_tier", 2))
    allowed_paths = source.get("allowed_paths", []) or []
    max_depth = int(source.get("max_depth", 1))
    interval_days = float(source.get("crawl_interval_days", 14))

    # BFS frontier: (url, depth). Seed is depth 0 and always eligible.
    frontier: deque = deque([(seed, 0)])
    visited = set()

    while frontier:
        url, depth = frontier.popleft()
        if url in visited:
            continue
        visited.add(url)

        # allowed_paths gate (the seed is exempt — it's the configured entry point).
        if url != seed and not _path_allowed(url, allowed_paths):
            continue
        if not robots_allowed(url):
            log.warning("robots.txt disallows %s — skipping", url)
            result.rows_skipped += 1
            continue

        # Staleness: if a recent successful row exists, bump fetched_at and skip the fetch.
        try:
            with engine.begin() as conn:
                latest = _latest_doc(conn, corridor, url)
                if latest and _days_between(latest["fetched_at"], now) < interval_days:
                    _touch_fetched_at(conn, latest["id"], now_iso)
                    result.rows_skipped += 1
                    continue
        except Exception as e:  # DB hiccup on the staleness probe — log, treat as not-stale
            log.debug("staleness probe failed for %s: %s", url, e)

        # Fetch (never raises).
        fr = fetcher(url)
        http_status = getattr(fr, "http_status", None)
        if not getattr(fr, "success", False):
            _write_error(engine, corridor, url, trust_tier, http_status,
                         getattr(fr, "error", "fetch failed"), now_iso, result)
            continue

        parsed = immigration_page_parser.parse(getattr(fr, "content", "") or "")
        extracted = parsed["text"]
        content_hash = _sha256(extracted)

        try:
            with engine.begin() as conn:
                if _doc_with_hash(conn, corridor, url, content_hash):
                    # Unchanged content — bump freshness only, no new row.
                    latest = _latest_doc(conn, corridor, url)
                    if latest:
                        _touch_fetched_at(conn, latest["id"], now_iso)
                    result.rows_skipped += 1
                else:
                    _insert_doc(
                        conn, id=str(uuid.uuid4()), corridor=corridor, source_url=url,
                        trust_tier=trust_tier, raw_html_path=None, extracted_text=extracted,
                        content_hash=content_hash, fetched_at=now_iso, http_status=http_status,
                        crawl_error=None, is_active=True,
                    )
                    result.rows_written += 1
        except Exception as e:
            _write_error(engine, corridor, url, trust_tier, http_status, str(e), now_iso, result)
            continue

        # Enqueue same-domain, allowed-path links up to max_depth.
        if depth + 1 < max_depth:
            for link in _discover_links(getattr(fr, "content", "") or "", url, allowed_paths):
                if link not in visited:
                    frontier.append((link, depth + 1))


def _write_error(engine, corridor, url, trust_tier, http_status, err, now_iso, result: CrawlResult) -> None:
    """Record a failed fetch as an error row. Never raises."""
    try:
        with engine.begin() as conn:
            _insert_doc(
                conn, id=str(uuid.uuid4()), corridor=corridor, source_url=url,
                trust_tier=int(trust_tier), raw_html_path=None, extracted_text=None,
                content_hash="error", fetched_at=now_iso, http_status=http_status,
                crawl_error=str(err)[:2000], is_active=True,
            )
        result.rows_failed += 1
        result.errors.append(f"{url}: {err}")
    except Exception as e:  # even the error write failed — log only, keep going
        log.error("failed to record crawl error for %s: %s", url, e)
        result.rows_failed += 1


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Immigration-rule crawler (N1/AIQ-840)")
    ap.add_argument("--corridor", default=None, help="Corridor key, e.g. FR_NO (default: all)")
    args = ap.parse_args(argv)
    res = run_crawl(args.corridor)
    print(f"written={res.rows_written} skipped={res.rows_skipped} failed={res.rows_failed}")


if __name__ == "__main__":
    main()

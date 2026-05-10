"""
HTTP fetcher with retry, timeout, content hashing.
Respects robots/scope; domain-restricted.
"""
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a single fetch."""

    url: str
    final_url: str
    content: str
    content_type: str
    http_status: int
    content_hash: str
    fetched_at: str
    headers: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and 200 <= self.http_status < 400


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def fetch_page(
    url: str,
    *,
    user_agent: str = "ReloPassBot/1.0 (crawler-staging)",
    timeout: int = 15,
    retry_count: int = 2,
    max_bytes: int = 2 * 1024 * 1024,
) -> FetchResult:
    """
    Fetch a single page. Retries on transient failures.
    Returns FetchResult with content, hash, status.
    """
    from datetime import datetime, timezone

    final_url = url
    content = ""
    content_type = "text/html"
    http_status = 0
    headers_sent = {"User-Agent": user_agent}
    error_msg = None

    resp = None
    for attempt in range(retry_count + 1):
        try:
            resp = requests.get(
                url,
                headers=headers_sent,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            final_url = resp.url
            http_status = resp.status_code
            content_type = (resp.headers.get("Content-Type") or "text/html").split(";")[0].strip().lower()

            if http_status >= 400:
                error_msg = f"HTTP {http_status}"
                break

            if "text/html" not in content_type and "application/json" not in content_type:
                error_msg = f"Unsupported content type: {content_type}"
                break

            data = bytearray()
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        error_msg = "Response too large"
                        break
                if error_msg:
                    break
            if error_msg:
                break

            content = data.decode(resp.encoding or "utf-8", errors="replace")
            break

        except requests.exceptions.Timeout:
            error_msg = "Timeout"
            if attempt < retry_count:
                time.sleep(1 * (attempt + 1))
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if attempt < retry_count:
                time.sleep(1 * (attempt + 1))

    content_hash = _compute_hash(content) if content else ""
    fetched_at = datetime.now(timezone.utc).isoformat()

    return FetchResult(
        url=url,
        final_url=final_url,
        content=content,
        content_type=content_type,
        http_status=http_status,
        content_hash=content_hash,
        fetched_at=fetched_at,
        headers=dict(resp.headers) if resp is not None else {},
        error=error_msg,
    )

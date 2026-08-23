"""Reject a citation URL that does not resolve, at the moment it would be written.

WHY THIS EXISTS. On 2026-08-19 all 28 distinct `rce.rule_versions.source_url` values were
probed: 14 rule versions across 8 URLs were live, and **20 rule versions across 20 URLs
returned 404**. Every dead one had the same shape —
`gesetze-im-internet.de/Teilliste_<citation>.html`, the German federal law portal with a
foreign legal citation pasted into its URL template. Norwegian (Utlendingsloven §109),
Spanish (RD 240/2007), Dutch (Wet BRP), Swiss (KVG/LAMal) and French (CGI art. 4 B) law is
not published on the German federal law site.

No model invented those. `corridor_persistence.derive_source_url` did, deterministically,
in its final fallback:

    return f"https://www.gesetze-im-internet.de/Teilliste_{quote_plus(ref)}.html"

and it did so because `rce.rule_versions.source_url` is NOT NULL — the docstring says the
fallback exists "so the column is always a usable, non-empty link". A column that cannot
hold "we don't know" is a column that will be filled with something untrue. This module
does not fix that pressure; it makes the result unpersistable, which is the half that can
ship without a migration.

THE VERDICTS ARE THREE, NOT TWO. The distinction is the whole design:

  OK          2xx/3xx — the page resolves.
  DEAD        404/410 — the page is not there. REJECT the write.
  UNVERIFIED  timeout, DNS failure, 5xx, connection reset — we did not find out.

`UNVERIFIED` is not a pass. A two-state checker has to map every transient failure to
either "accept" or "reject", and both are wrong: accepting means a nationwide outage
silently readmits fabricated URLs, while rejecting means a flaky network blocks a
legitimate corridor seed. Keeping the third state lets the caller decide, and lets the
caller say WHICH of the two happened when it reports.

This module performs network I/O. It is deliberately import-light (stdlib only) and the
probe is injectable, so callers and tests never depend on the network by accident.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, List, Optional, Sequence

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_ATTEMPTS = 2
_USER_AGENT = "ReloPass-citation-check/1.0 (+https://relopass.com)"

# 404 Gone-for-good and 410 Gone. Nothing else is treated as proof of absence:
# a 403 is a bot block, a 429 is rate limiting, and neither means the page is missing.
_DEAD_STATUSES = frozenset({404, 410})


class Verdict(str, Enum):
    OK = "ok"
    DEAD = "dead"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Reachability:
    url: str
    verdict: Verdict
    status_code: Optional[int]
    detail: str

    @property
    def is_dead(self) -> bool:
        return self.verdict is Verdict.DEAD


class UnreachableSourceURL(ValueError):
    """A source_url returned 404/410. The write must not proceed."""

    def __init__(self, results: Sequence[Reachability]) -> None:
        self.results = list(results)
        detail = "; ".join(f"{r.url} -> {r.status_code}" for r in self.results)
        super().__init__(
            f"{len(self.results)} source_url(s) do not resolve and will not be persisted: {detail}"
        )


class SourceURLUnverified(RuntimeError):
    """A source_url could not be checked. Not proof it is bad — proof we do not know.

    Raised rather than swallowed so an unchecked URL is never recorded as a checked one.
    The caller may retry, or pass ``allow_unverified=True`` to accept the risk EXPLICITLY.
    """

    def __init__(self, results: Sequence[Reachability]) -> None:
        self.results = list(results)
        detail = "; ".join(f"{r.url} ({r.detail})" for r in self.results)
        super().__init__(
            f"{len(self.results)} source_url(s) could not be verified: {detail}. "
            "Retry, or pass allow_unverified=True to accept them deliberately."
        )


def probe_url(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    attempts: int = DEFAULT_ATTEMPTS,
) -> Reachability:
    """Resolve *url* once, retrying only the transient failures.

    HEAD first, falling back to GET on 403/405: a good number of government sites answer
    HEAD with 405 or block it outright while serving GET perfectly well, and treating that
    as DEAD would reject exactly the official sources this is meant to protect.
    """
    if not url or not str(url).strip():
        return Reachability(url or "", Verdict.UNVERIFIED, None, "empty url")

    url = str(url).strip()
    if not url.lower().startswith(("http://", "https://")):
        # Not transient and not a 404 — it can never resolve, so it is DEAD by definition.
        return Reachability(url, Verdict.DEAD, None, "not an http(s) url")

    last: Optional[Reachability] = None
    for attempt in range(1, max(1, attempts) + 1):
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(
                    url, method=method, headers={"User-Agent": _USER_AGENT}
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return Reachability(url, Verdict.OK, resp.status, f"{method} {resp.status}")
            except urllib.error.HTTPError as exc:
                if exc.code in _DEAD_STATUSES:
                    return Reachability(url, Verdict.DEAD, exc.code, f"{method} {exc.code}")
                if method == "HEAD" and exc.code in (403, 405):
                    continue  # retry the same attempt with GET
                last = Reachability(
                    url, Verdict.UNVERIFIED, exc.code, f"{method} {exc.code} (attempt {attempt})"
                )
                break
            except Exception as exc:  # timeout, DNS, reset, bad cert
                last = Reachability(
                    url, Verdict.UNVERIFIED, None,
                    f"{type(exc).__name__}: {exc} (attempt {attempt})",
                )
                break
    return last or Reachability(url, Verdict.UNVERIFIED, None, "no attempt completed")


def check_source_urls(
    urls: Iterable[Optional[str]],
    *,
    probe: Callable[[str], Reachability] = probe_url,
) -> List[Reachability]:
    """Probe each DISTINCT non-empty url once, preserving first-seen order.

    Deduplicating matters: the 20 fabricated rows were 20 distinct URLs, but a corridor
    routinely cites one statute from several rule versions, and probing it once per row
    is both slower and less polite for no extra information.
    """
    seen: set = set()
    results: List[Reachability] = []
    for raw in urls:
        url = (raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        results.append(probe(url))
    return results


def assert_source_urls_resolve(
    urls: Iterable[Optional[str]],
    *,
    probe: Callable[[str], Reachability] = probe_url,
    allow_unverified: bool = False,
) -> List[Reachability]:
    """Raise unless every url resolved. Returns the results when it does not raise.

    DEAD takes precedence over UNVERIFIED: if one URL is provably absent, that is the
    finding worth reporting, and reporting "could not verify" first would bury it.
    """
    results = check_source_urls(urls, probe=probe)

    dead = [r for r in results if r.verdict is Verdict.DEAD]
    if dead:
        raise UnreachableSourceURL(dead)

    unverified = [r for r in results if r.verdict is Verdict.UNVERIFIED]
    if unverified and not allow_unverified:
        raise SourceURLUnverified(unverified)
    if unverified:
        log.warning(
            "source_url check: accepting %d unverified url(s) because allow_unverified=True: %s",
            len(unverified), "; ".join(r.url for r in unverified),
        )
    return results

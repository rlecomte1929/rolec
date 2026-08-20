"""[AIQ-1887] The fetch layer around the evidence checker must not manufacture verdicts.

`fact_evidence.check_evidence` is already careful: it is tri-state, and `verified` returns None
for NO_SOURCE so "we could not look" never becomes "the quote is not there". The bug is one layer
out, in the fetcher that feeds it.

Measured on 2026-08-20 against the 112 sources behind the approved facts: 16 of them returned
HTTP 403 and 11 returned a JS shell. A dry run reported 122 `no_source` verdicts. But
`citizensinformation.ie` and `immi.homeaffairs.gov.au` both serve those pages fine — they were
refusing `ReloPassBot/1.0`, and eight of the sixteen 403s were Citizens Information alone, which
is why Ireland sat at 6.8% evidenced against pages that are alive.

Recording "no source" against a live government page is the same class of error the ticket
exists to remove, so these tests pin the fetch layer's obligations:

  * identify as a browser, because that is what these publishers serve;
  * ask robots.txt first, and skip what it disallows;
  * do not hammer a host;
  * when a fetch fails, say the fetch failed — never let it read as "never fetched".
"""
from __future__ import annotations

import backend.scripts.backfill_fact_evidence as bf


def test_the_fetcher_identifies_as_a_browser_because_publishers_refuse_the_bot():
    """`citizensinformation.ie` and `immi.homeaffairs.gov.au` 403 a bot token and 200 a browser.

    A self-identifying `Mozilla/5.0 (compatible; ReloPassBot/1.0; +url)` was measured and is
    ALSO refused, so a real browser token is the only thing that reaches the page.
    """
    ua = bf.USER_AGENT
    assert "Mozilla/5.0" in ua
    assert "AppleWebKit" in ua or "Gecko" in ua
    # The bare bot token is what was being refused; it must not be the default any more.
    assert ua != "ReloPassBot/1.0 (evidence-backfill)"


def test_a_disallowed_url_is_skipped_rather_than_fetched():
    """Sending a browser token is not licence to ignore robots.txt."""
    calls = []

    class _DenyAll:
        def allowed(self, url):
            calls.append(url)
            return False

    res = bf.fetch_and_parse("https://example.gov/secret", robots=_DenyAll())

    assert res["ok"] is False
    assert res["reason"] == "robots_disallowed"
    assert res["text"] == ""
    assert calls == ["https://example.gov/secret"]


def test_a_403_is_recorded_as_a_block_not_as_a_missing_source(monkeypatch):
    """The distinction the whole ticket turns on.

    A publisher refusing us says nothing about whether the quote is in the page. It must not be
    collapsed into the same bucket as "there is no archived text".
    """
    class _Resp:
        status_code = 403
        text = ""

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return _Resp()

    monkeypatch.setattr(bf.httpx, "Client", _Client)
    res = bf.fetch_and_parse("https://travel.state.gov/x")

    assert res["ok"] is False
    assert res["reason"] == "http_403"
    assert res["blocked"] is True, "a 403 is the publisher blocking us, not an absent source"


def test_a_failed_fetch_writes_fetch_failed_not_not_fetched():
    """`not_fetched` means nobody ever tried. A failure must not be able to read as that.

    This is the same bug shape as the 140 docs that were wrongly relabelled `not_fetched` on
    2026-08-20 while holding a real archived excerpt.
    """
    assert bf.fetch_status_for({"ok": True, "reason": "fetched"}) == "fetched"
    assert bf.fetch_status_for({"ok": False, "reason": "http_403"}) == "fetch_failed"
    assert bf.fetch_status_for({"ok": False, "reason": "js_shell_or_empty"}) == "fetch_failed"
    assert bf.fetch_status_for({"ok": False, "reason": "robots_disallowed"}) == "not_fetched"


def test_the_fetcher_waits_between_requests_to_the_same_host(monkeypatch):
    """One request per second per host. Politeness is the other half of using a browser token."""
    slept = []
    monkeypatch.setattr(bf.time, "sleep", lambda s: slept.append(s))

    limiter = bf.HostRateLimiter(delay_s=1.0)
    now = [1000.0]
    monkeypatch.setattr(bf.time, "monotonic", lambda: now[0])

    limiter.wait("https://example.gov/a")   # first hit, no wait
    assert slept == []

    limiter.wait("https://example.gov/b")   # same host, immediately after -> waits
    assert slept and slept[0] > 0

    slept.clear()
    limiter.wait("https://other.gov/a")     # different host -> no wait
    assert slept == []

"""[AIQ-1887] The fetch layer around the evidence checker must not manufacture verdicts.

`fact_evidence.check_evidence` is already careful: it is tri-state, and `verified` returns None
for NO_SOURCE so "we could not look" never becomes "the quote is not there". The bug is one layer
out, in the fetcher that feeds it.

Measured 2026-08-20 over the sources behind the approved facts, and the reason this is a chain
rather than a constant — no single identity works everywhere:

    citizensinformation.ie   bot UA -> 403          browser UA -> 200
    immi.homeaffairs.gov.au  bot UA -> 403          browser UA -> 200
    canada.ca                bot UA -> 200          browser UA -> connection reset in 0.15s
    travel.state.gov         403 to everything (Cloudflare)

Two passes got this wrong before it got it right. The first ran as `ReloPassBot/1.0` and wanted
to write 122 `no_source` verdicts, eight of the sixteen 403s being Citizens Information alone.
The second led with a browser token, fixed Ireland's 403s — and took Canada from 13.6% evidenced
to 0%, while a robots check fetched through urllib's own UA got 403 and disallowed every Irish
URL outright, dropping Ireland to 0% too.

Recording "no source" against a live government page is the same class of error the ticket exists
to remove, so these tests pin the fetch layer's obligations:

  * identify as ourselves first, and fall back only where a publisher has actually refused;
  * fetch robots.txt through that same chain, and respect what it really says;
  * do not hammer a host;
  * when a fetch fails, say the fetch failed — never let it read as "never fetched".
"""
from __future__ import annotations

import backend.scripts.backfill_fact_evidence as bf


def test_we_identify_as_ourselves_first_and_only_fall_back_when_refused():
    """No single UA works everywhere, and the ORDER is the ethical point.

    Measured: citizensinformation.ie and immi.homeaffairs.gov.au 403 the bot token and 200 a
    browser one; canada.ca does the opposite, resetting the browser token in 0.15s while
    serving the page with no UA header at all. A first pass that led with the browser token
    took Canada from 13.6% evidenced to 0%.

    So we announce our own name first, and only present as a browser to a publisher that has
    actually refused it.
    """
    assert bf.USER_AGENTS[0] == bf.UA_HONEST
    assert "ReloPassBot" in bf.UA_HONEST
    assert "Mozilla/5.0" in bf.UA_BROWSER
    assert bf.USER_AGENTS.index(bf.UA_BROWSER) > 0
    assert None in bf.USER_AGENTS, "some anti-bot front ends only accept no UA header at all"


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


def _client_returning(statuses, body=""):
    """httpx.Client stub yielding one status per successive call."""
    seq = list(statuses)

    class _Resp:
        def __init__(self, code): self.status_code, self.text = code, body

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return _Resp(seq.pop(0))

    return _Client


def test_a_403_to_every_identity_is_recorded_as_a_block_not_a_missing_source(monkeypatch):
    """The distinction the whole ticket turns on.

    A publisher refusing us says nothing about whether the quote is in the page. It must not be
    collapsed into the same bucket as "there is no archived text". travel.state.gov 403s every
    identity we have.
    """
    monkeypatch.setattr(bf.httpx, "Client", _client_returning([403, 403, 403]))
    res = bf.fetch_and_parse("https://travel.state.gov/x")

    assert res["ok"] is False
    assert res["reason"] == "http_403"
    assert res["blocked"] is True, "a 403 is the publisher blocking us, not an absent source"


def test_a_refusal_of_the_honest_ua_retries_with_the_browser_one(monkeypatch):
    """citizensinformation.ie: 403 to ReloPassBot, 200 to a browser token."""
    monkeypatch.setattr(bf.httpx, "Client",
                        _client_returning([403, 200], body="<p>" + "x " * 300 + "</p>"))
    monkeypatch.setattr(bf.immigration_page_parser, "parse", lambda html: {"text": "y " * 300})

    res = bf.fetch_and_parse("https://www.citizensinformation.ie/en/x")

    assert res["ok"] is True
    assert res["ua"] == bf.UA_BROWSER, "must have fallen back after the refusal"


def test_a_404_is_not_retried_against_every_identity(monkeypatch):
    """A missing page says the same thing to everyone; retrying it is just noise on the host."""
    monkeypatch.setattr(bf.httpx, "Client", _client_returning([404]))
    res = bf.fetch_and_parse("https://example.gov/gone")

    assert res["reason"] == "http_404"
    assert res["blocked"] is False


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


def test_robots_is_fetched_through_the_same_ua_chain_not_urllibs_own(monkeypatch):
    """The bug that took Ireland from 6.8% to 0%.

    `RobotFileParser.read()` fetches robots.txt with urllib's `Python-urllib/3.x` UA and treats
    a 403 on it as *disallow everything*. Measured: citizensinformation.ie, travel.state.gov and
    france-visas.gouv.fr all 403 urllib, so every URL on them was skipped — the robots check
    defeated the UA fallback it was paired with.

    A 4xx means no policy was published, which allows. Only a 5xx disallows: the server has a
    policy and cannot currently tell us what it is.
    """
    monkeypatch.setattr(bf.httpx, "Client", _client_returning([404, 404, 404]))
    assert bf.RobotsPolicy().allowed("https://www.citizensinformation.ie/en/x") is True

    monkeypatch.setattr(bf.httpx, "Client", _client_returning([503, 503, 503]))
    assert bf.RobotsPolicy().allowed("https://flaky.gov/x") is False


def test_a_real_disallow_is_still_respected(monkeypatch):
    """Falling back to a browser token is not licence to ignore a published policy."""
    monkeypatch.setattr(
        bf.httpx, "Client",
        _client_returning([200], body="User-agent: *\nDisallow: /private/\n"))
    policy = bf.RobotsPolicy()

    assert policy.allowed("https://example.gov/private/thing") is False
    assert policy.allowed("https://example.gov/public/thing") is True

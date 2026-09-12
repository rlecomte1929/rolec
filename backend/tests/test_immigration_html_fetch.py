"""HtmlFetch never raises — a WAF 403 is a typed gap, not an aborted batch."""
from __future__ import annotations

import requests

import backend.imports.immigration.fetcher as fetcher


class _Resp:
    def __init__(self, status: int, body: bytes = b"<html><body>ok</body></html>", ctype="text/html"):
        self.status_code = status
        self.headers = {"Content-Type": ctype}
        self.encoding = "utf-8"
        self.url = "https://gov.example/page"
        self._body = body

    def iter_content(self, chunk_size=16384):
        yield self._body


def test_fetch_html_403_returns_error_and_does_not_raise(monkeypatch):
    monkeypatch.setattr(fetcher, "MAX_ATTEMPTS", 1)
    monkeypatch.setattr(fetcher, "PER_HOST_DELAY_SECONDS", 0)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(403))

    got = fetcher.fetch_html("https://gov.example/waf")
    assert got.ok is False
    assert got.status == 403
    assert got.error == "HTTP 403"
    assert got.html == ""


def test_fetch_html_timeout_returns_error_and_does_not_raise(monkeypatch):
    monkeypatch.setattr(fetcher, "MAX_ATTEMPTS", 1)
    monkeypatch.setattr(fetcher, "PER_HOST_DELAY_SECONDS", 0)

    def _timeout(*a, **k):
        raise requests.exceptions.Timeout("read timed out")

    monkeypatch.setattr(requests, "get", _timeout)

    got = fetcher.fetch_html("https://gov.example/slow")
    assert got.ok is False
    assert "Timeout" in (got.error or "")

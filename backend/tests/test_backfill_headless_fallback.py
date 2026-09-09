"""[AIQ-1887 D3] The --headless fallback renders a client-side shell — and only a shell.

mom.gov.sg returns HTTP 200 with an Angular shell and no server-rendered article text, so httpx
plus the parser see nothing and every Singapore work-pass fact is uncheckable. `fetch_and_parse`
now falls back to a headless-Chromium render on exactly that case, when --headless is passed.

These tests pin the fallback WIRING without launching a browser: httpx is stubbed to return the
shell, and `render_headless` is stubbed. They assert the fallback fires only on an empty parse,
only with the flag, uses the rendered text, and degrades to the old result when the render yields
nothing. The real browser render is proven separately (a headless Chromium executing JS on a
local data: URL) and cannot run in CI, which has no browser — hence the stub here.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.scripts.backfill_fact_evidence as bf  # noqa: E402

# A client-rendered shell: parses to empty text (verified against immigration_page_parser).
SHELL_HTML = ("<!doctype html><html><head><title>MOM</title></head>"
              "<body><app-root></app-root><script src='/main.js'></script></body></html>")
# What the browser yields once the page's JS has run.
RENDERED_HTML = ("<!doctype html><html><head><title>Employment Pass</title></head>"
                 "<body><main><h1>Employment Pass eligibility</h1>"
                 "<p>Minimum fixed monthly salary of $5,600, increasing with age.</p>"
                 "</main></body></html>")
RENDERED_PHRASE = "Minimum fixed monthly salary of $5,600"
URL = "https://www.mom.gov.sg/passes-and-permits/employment-pass/eligibility"


class _Resp:
    def __init__(self, status: int, text: str) -> None:
        self.status_code = status
        self.text = text


def _stub_httpx_client(monkeypatch, html: str, status: int = 200) -> None:
    """Replace httpx.Client so every GET returns `html` with `status` — no network."""
    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, _url): return _Resp(status, html)
    monkeypatch.setattr(bf.httpx, "Client", _Client)


def test_headless_renders_a_client_side_shell(monkeypatch):
    _stub_httpx_client(monkeypatch, SHELL_HTML)
    monkeypatch.setattr(bf, "render_headless", lambda url, timeout_s=bf.FETCH_TIMEOUT_S: RENDERED_HTML)
    res = bf.fetch_and_parse(URL, headless=True)
    assert res["ok"] is True
    assert res["reason"] == "fetched_headless"
    assert RENDERED_PHRASE in res["text"]


def test_a_shell_stays_unrendered_without_the_flag(monkeypatch):
    """Default behaviour is unchanged: no flag, no browser, the shell is recorded as a shell."""
    _stub_httpx_client(monkeypatch, SHELL_HTML)
    called = {"n": 0}
    def _boom(url, timeout_s=bf.FETCH_TIMEOUT_S):
        called["n"] += 1
        raise AssertionError("render_headless must not run without --headless")
    monkeypatch.setattr(bf, "render_headless", _boom)
    res = bf.fetch_and_parse(URL)  # headless defaults to False
    assert res["ok"] is False
    assert res["reason"] == "js_shell_or_empty"
    assert called["n"] == 0


def test_headless_degrades_when_the_render_yields_nothing(monkeypatch):
    """Playwright missing, no browser binary, or a navigation error -> render_headless returns
    None, and fetch_and_parse must fall back to the same js_shell_or_empty result, never raise."""
    _stub_httpx_client(monkeypatch, SHELL_HTML)
    monkeypatch.setattr(bf, "render_headless", lambda url, timeout_s=bf.FETCH_TIMEOUT_S: None)
    res = bf.fetch_and_parse(URL, headless=True)
    assert res["ok"] is False
    assert res["reason"] == "js_shell_or_empty"


def test_a_server_rendered_page_never_triggers_headless(monkeypatch):
    """The fallback is scoped to the empty-parse case: a page with real text is fetched the
    normal way and the browser is never launched, even with --headless on."""
    _stub_httpx_client(monkeypatch, RENDERED_HTML)
    def _boom(url, timeout_s=bf.FETCH_TIMEOUT_S):
        raise AssertionError("render_headless must not run when httpx already yields text")
    monkeypatch.setattr(bf, "render_headless", _boom)
    res = bf.fetch_and_parse(URL, headless=True)
    assert res["ok"] is True
    assert res["reason"] == "fetched"
    assert RENDERED_PHRASE in res["text"]

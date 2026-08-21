"""[AIQ-1845] A page wrapped in <form> is a page, not a widget.

`_NOISE_TAGS` lists "form", and every noise tag is `decompose()`d before the content root is
chosen. That is right for a search box or a newsletter signup. It is catastrophic for ASP.NET
WebForms, which wraps the ENTIRE document in a single `<form runat="server">` — decomposing it
deletes the whole page and leaves only whatever sits outside, which on a government site is the
cookie banner.

Measured 2026-08-21 against
https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/fees/ :
32,292 chars of HTML containing `€1,000` eight times and `€1,500` five times, and the parser
returned **308 characters — the cookie notice**. Every employment-permit fee and salary
threshold in the Irish catalog lives on pages of that shape.

The damage is not merely "no evidence". 308 clears `fact_evidence.MIN_USABLE_SOURCE_CHARS`
(200), so `check_evidence` treats the cookie banner as a usable source and returns UNVERIFIED —
"we have the source and the quote is not in it" — instead of NO_SOURCE. A correct fee reads as a
disproved claim. 41 rows in production carry a verdict produced this way.

So the rule these tests pin: a `<form>` is noise only when it carries no document content.
"""
from __future__ import annotations

from backend.crawler.parsers import immigration_page_parser as p

# The real shape: ASP.NET wraps everything, the cookie notice sits outside it.
_ASPNET_PAGE = """
<html><head><title>Fees - Employment Permits</title></head>
<body>
  <div class="cookie-notice">
    Our website uses cookies to enhance your browsing experience and to collect information
    about how you use this site to improve our service to you. By not accepting cookies some
    elements of the site, such as video, will not work. Please visit our Cookie Policy page.
  </div>
  <form method="post" action="./fees" id="aspnetForm">
    <article>
      <h1>Employment Permit Fees</h1>
      <p>The following fees apply to employment permit applications.</p>
      <table>
        <tr><th>Permit category</th><th>First application fee</th></tr>
        <tr><td>General Employment Permit</td><td>&euro;1,000 up to 24 months</td></tr>
        <tr><td>Critical Skills Employment Permit</td><td>&euro;1,000</td></tr>
      </table>
      <p>If an application is refused, 90% of the fee is refunded.</p>
    </article>
  </form>
</body></html>
"""

# A form that really is a widget: a site search box with no document content.
_SEARCH_WIDGET_PAGE = """
<html><head><title>Immigration permission</title></head>
<body>
  <form id="site-search" action="/search">
    <label>Search this site</label>
    <input type="text" name="q"/>
    <button>Search</button>
  </form>
  <article>
    <h1>Registering your immigration permission</h1>
    <p>You must register within 90 days of arrival.</p>
  </article>
</body></html>
"""


def test_the_fees_survive_a_form_that_wraps_the_whole_page():
    """The regression that started this: every euro figure was being deleted."""
    text = p.parse(_ASPNET_PAGE)["text"]

    assert "€1,000" in text, "the fee table was destroyed with the wrapping <form>"
    assert "90%" in text
    assert "Employment Permit Fees" in text


def test_the_parse_is_not_just_the_cookie_banner():
    """308 chars of cookie notice cleared the usable-source floor and produced false verdicts."""
    text = p.parse(_ASPNET_PAGE)["text"]

    assert len(text) > 200, "must not fall back to a sub-threshold stub"
    assert not text.lower().startswith("our website uses cookies")
    # The banner may appear, but it cannot be the whole document.
    assert "Employment Permit Fees" in text


def test_the_table_is_still_rendered_as_pipe_rows():
    """Structure is the point of this parser — the fee has to stay attached to its category."""
    text = p.parse(_ASPNET_PAGE)["text"]

    assert any("General Employment Permit" in line and "€1,000" in line
               for line in text.splitlines()), "fee row lost its category"


def test_a_search_widget_form_is_still_dropped():
    """The original rule was not wrong, only too broad. A real widget stays out."""
    text = p.parse(_SEARCH_WIDGET_PAGE)["text"]

    assert "Search this site" not in text
    assert "90 days" in text, "the real content must survive"


def test_an_empty_document_is_still_handled():
    assert p.parse("")["text"] == ""
    assert p.parse("<html><body></body></html>")["word_count"] == 0

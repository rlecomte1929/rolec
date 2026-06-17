"""
[CRAWL-QUALITY-1 / AIQ-1145] Quality gates on the rule-based resource extractor,
driven by the real failure classes from the 2026-06-17 review of the first 19
staged candidates (0 publishable, 19 rejected): bot-walls, page-<title> chunk
spam, and nav/boilerplate dumps.
"""
from backend.crawler.chunkers.chunker import Chunk
from backend.crawler.config.models import CrawlSource
from backend.crawler.extractors.resource_extractor import extract_resource_candidates


def _src(domain="housing", tier="T0"):
    return CrawlSource(
        source_name="Handbook Germany",
        base_url="https://handbookgermany.de",
        country_code="DE",
        country_name="Germany",
        trust_tier=tier,
        content_domain=domain,
    )


def _chunk(text, heading="", idx=0):
    return Chunk(chunk_index=idx, heading_path=heading, chunk_text=text, chunk_hash=f"h{idx}")


GOOD_BODY = (
    "After you move into a flat you must register your address at the local "
    "Buergeramt within two weeks. Bring your passport and a landlord confirmation. "
    "The certificate you receive is required for almost everything else, such as a "
    "bank account or a mobile contract."
)


def test_bot_wall_by_text_marker_is_skipped():
    chunks = [_chunk("We apologize for the inconvenience. Verify you are human to continue. " * 3)]
    out = extract_resource_candidates(
        chunks, _src(), "https://www.make-it-in-germany.com/en/health-insurance",
        "We apologize for the inconvenience...",
    )
    assert out == []


def test_bot_wall_by_url_marker_is_skipped():
    # Even with plausible body text, a Radware/perfdrive interstitial URL is a bot wall.
    chunks = [_chunk(GOOD_BODY, heading="Health insurance")]
    out = extract_resource_candidates(
        chunks, _src(), "https://validate.perfdrive.com/?ssa=abc&ssc=make-it-in-germany.com",
        "Health insurance",
    )
    assert out == []


def test_real_page_title_chunk_spam_all_rejected():
    # The actual failure: 12 chunks all titled with the page <title>.
    chunks = [
        _chunk(GOOD_BODY + f" Variant {i}.", heading="Renting a flat | Handbook Germany : Together", idx=i)
        for i in range(12)
    ]
    out = extract_resource_candidates(
        chunks, _src(), "https://handbookgermany.de/en/renting-an-apartment",
        "Renting a flat | Handbook Germany : Together",
    )
    assert out == []  # title == page branding → all rejected, never staged


def test_untitled_dense_chunk_not_staged_with_page_title():
    # No heading + a too-long first line → no real title → skip (don't fall back to
    # the raw page <title>); the page goes to the LLM fallback instead.
    text = (
        "This is a very long opening paragraph that exceeds the title length limit and "
        "is therefore body prose, not a heading, about renting a flat in Germany and the "
        "costs involved and what to consider when you move into a new home."
    )
    out = extract_resource_candidates(
        chunks=[_chunk(text, heading="")],
        source=_src(),
        source_url="https://handbookgermany.de/en/renting-an-apartment",
        page_title="Renting a flat | Handbook Germany : Together",
    )
    assert out == []


def test_nav_menu_dump_is_rejected():
    nav = "\n".join([
        "Welcome to Oslo", "Find housing", "Find a job", "Start a business",
        "Health care", "Language courses", "Street and parking", "Kindergarten",
    ])
    out = extract_resource_candidates(
        [_chunk(nav, heading="Schools and education")], _src(domain="schools"),
        "https://www.oslo.kommune.no/english", "Oslo",
    )
    assert out == []  # homepage nav menu, not guidance


def test_good_content_is_staged_with_its_heading_as_title():
    out = extract_resource_candidates(
        [_chunk(GOOD_BODY, heading="Register your address (Anmeldung)")],
        _src(domain="admin_essentials"),
        "https://handbookgermany.de/en/city-registration",
        "City registration | Handbook Germany",
    )
    assert len(out) == 1
    assert out[0].title == "Register your address (Anmeldung)"
    assert out[0].extraction_method == "rule_based"
    assert out[0].source_url == "https://handbookgermany.de/en/city-registration"


def test_same_heading_chunks_collapse_to_one():
    chunks = [
        _chunk(GOOD_BODY + f" Detail {i}.", heading="How the rental market works", idx=i)
        for i in range(12)
    ]
    out = extract_resource_candidates(
        chunks, _src(), "https://handbookgermany.de/en/renting-an-apartment",
        "Renting a flat | Handbook Germany : Together",
    )
    assert len(out) == 1  # 12 same-title chunks → one candidate
    assert out[0].title == "How the rental market works"


def test_per_page_candidate_cap():
    # Many distinct headings on one page are capped (guards against flooding).
    chunks = [
        _chunk(GOOD_BODY + f" Section {i}.", heading=f"Distinct heading number {i}", idx=i)
        for i in range(15)
    ]
    out = extract_resource_candidates(
        chunks, _src(), "https://handbookgermany.de/en/big-page", "Big page | Handbook Germany",
    )
    assert 0 < len(out) <= 6  # MAX_CANDIDATES_PER_PAGE

"""official_ingest_service — allowlist, baseline-rule creation, and (AIQ-1821) the
LLM fact-extraction path that feeds `requirement_facts`.

Imports canonically as `backend.app.services` (per backend/CLAUDE.md). The old
`from app.services import ...` form only resolved with backend/ on sys.path, which is
why this module sat in conftest's collect_ignore and never ran in CI.
"""
import hashlib
import logging

from backend.app.services import official_ingest_service as ingest

# Parsed main text must clear fetcher.MIN_TEXT_CHARS (600). Repeat a sentence so
# the success fixture stays a real document, not a JS-shell.
_LONG_BODY = (
    "You must file Form I-129 before the requested start date. "
    * 20
).strip()
assert len(_LONG_BODY) >= ingest.MIN_TEXT_CHARS
_SUCCESS_HTML = (
    f"<html><title>USCIS Working in the United States</title>"
    f"<body><main>{_LONG_BODY}</main></body></html>"
)


def test_allowlist_rejects_non_official():
    try:
        ingest.ingest_url_to_knowledge_doc("https://example.com", "US", "immigration")
        assert False, "Expected ValueError for non-official domain"
    except ValueError:
        assert True


def _capture_upserts(monkeypatch):
    """Record upsert kwargs. Failure must not call this (no empty evidence row)."""
    upserts = []

    def fake_upsert(*args, **kwargs):
        upserts.append(kwargs)
        return {"id": "doc1", "title": kwargs.get("title")}

    monkeypatch.setattr(ingest.db, "ensure_knowledge_pack", lambda *a, **k: {"id": "pack1"})
    monkeypatch.setattr(ingest.db, "upsert_knowledge_doc_by_url", fake_upsert)
    return upserts


def test_failed_http_fetch_does_not_upsert_empty_text_content(monkeypatch, caplog):
    """RP-MEM-007: a 403 is NULL — do not persist excerpt-or-empty as evidence."""

    def boom(url, destination_country):
        raise ingest.requests.HTTPError("403 Client Error: Forbidden")

    upserts = _capture_upserts(monkeypatch)
    monkeypatch.setattr(ingest, "_fetch_html", boom)
    caplog.set_level(logging.WARNING, logger=ingest.log.name)

    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/working-in-the-united-states", "US", "immigration",
    )
    assert res["fetch_status"] == "fetch_failed"
    assert res["doc_id"] is None
    assert upserts == [], (
        "failed fetch must not upsert; got text_content=%r fetch_status=%r"
        % (
            upserts[0].get("text_content") if upserts else None,
            upserts[0].get("fetch_status") if upserts else None,
        )
    )
    assert "source_host=www.uscis.gov" in caplog.text
    assert "failure_reason=" in caplog.text
    assert "403" in caplog.text


def test_empty_extraction_does_not_upsert(monkeypatch):
    upserts = _capture_upserts(monkeypatch)
    monkeypatch.setattr(
        ingest,
        "_fetch_html",
        lambda url, destination_country: (url, "<html><title></title><body></body></html>"),
    )
    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/empty", "US", "immigration",
    )
    assert res["fetch_status"] == "fetch_failed"
    assert "Empty content" in (res["error"] or "")
    assert upserts == []


def test_below_min_text_does_not_upsert(monkeypatch):
    upserts = _capture_upserts(monkeypatch)
    monkeypatch.setattr(
        ingest,
        "_fetch_html",
        lambda url, destination_country: (
            url,
            "<html><title>Shell</title><body><main>Skip to navigation Loading</main></body></html>",
        ),
    )
    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/shell", "US", "immigration",
    )
    assert res["fetch_status"] == "fetch_failed"
    assert "min" in (res["error"] or "").lower()
    assert upserts == []


def test_login_page_redirect_does_not_upsert(monkeypatch):
    upserts = _capture_upserts(monkeypatch)

    def fake_fetch(url, destination_country):
        return "https://www.uscis.gov/login", _SUCCESS_HTML

    monkeypatch.setattr(ingest, "_fetch_html", fake_fetch)
    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/working-in-the-united-states", "US", "immigration",
    )
    assert res["fetch_status"] == "fetch_failed"
    assert "Login-page" in (res["error"] or "")
    assert upserts == []


def test_server_error_does_not_upsert(monkeypatch):
    upserts = _capture_upserts(monkeypatch)

    def boom(url, destination_country):
        raise ingest.requests.HTTPError("500 Server Error: Internal Server Error")

    monkeypatch.setattr(ingest, "_fetch_html", boom)
    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/working-in-the-united-states", "US", "immigration",
    )
    assert res["fetch_status"] == "fetch_failed"
    assert upserts == []


def test_successful_fetch_stores_excerpt_and_sha256(monkeypatch):
    upserts = _capture_upserts(monkeypatch)
    monkeypatch.setattr(
        ingest, "_fetch_html", lambda url, dest: (url, _SUCCESS_HTML),
    )
    monkeypatch.setattr(ingest.db, "create_baseline_rule_for_doc", lambda *a, **k: "rule1")
    monkeypatch.setattr(ingest, "_llm_facts_for_doc", lambda *a, **k: [])
    monkeypatch.setattr(
        ingest,
        "extract_requirements_from_doc",
        lambda *a, **k: {"entity": None, "facts": []},
    )

    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/working-in-the-united-states", "US", "immigration",
    )
    assert res["fetch_status"] == "fetched"
    assert res["doc_id"] == "doc1"
    assert len(upserts) == 1
    stored = upserts[0]["text_content"]
    assert stored
    assert len(stored) >= ingest.MIN_TEXT_CHARS
    assert upserts[0]["fetch_status"] == "fetched"
    assert upserts[0]["content_sha256"] == hashlib.sha256(stored.encode("utf-8")).hexdigest()
    assert upserts[0]["content_excerpt"] == stored


def test_ingest_creates_baseline_rule(monkeypatch):
    def fake_fetch_html(url, destination_country):
        return url, _SUCCESS_HTML

    def fake_upsert(*args, **kwargs):
        return {"id": "doc1", "title": kwargs.get("title")}

    def fake_pack(*args, **kwargs):
        return {"id": "pack1"}

    created_rules = []

    def fake_rule(pack_id, doc_id, doc_title, domain_area):
        created_rules.append((pack_id, doc_id, domain_area))
        return "rule1"

    monkeypatch.setattr(ingest, "_fetch_html", fake_fetch_html)
    monkeypatch.setattr(ingest.db, "ensure_knowledge_pack", fake_pack)
    monkeypatch.setattr(ingest.db, "upsert_knowledge_doc_by_url", fake_upsert)
    monkeypatch.setattr(ingest.db, "create_baseline_rule_for_doc", fake_rule)
    # [AIQ-1821] Ingest now tries the LLM extractor first. Stub it so this test stays
    # offline and deterministic rather than relying on OPENAI_API_KEY being absent.
    monkeypatch.setattr(ingest, "_llm_facts_for_doc", lambda *a, **k: [])
    monkeypatch.setattr(
        ingest,
        "extract_requirements_from_doc",
        lambda *a, **k: {"entity": None, "facts": []},
    )

    res = ingest.ingest_url_to_knowledge_doc("https://www.uscis.gov/working-in-the-united-states", "US", "immigration")
    assert res["fetch_status"] == "fetched"
    assert res["rule_id"] == "rule1"
    assert created_rules


# ── [AIQ-1821] LLM extraction path ───────────────────────────────────────────

# Mirrors the requirement_facts.fact_type / confidence CHECK constraints, so a
# mapping that would violate the DB fails here instead of at INSERT time.
_FACT_TYPE_CHECK = {
    "eligibility", "document", "step", "deadline", "fee", "where_to_apply", "account", "other",
}
_CONFIDENCE_CHECK = {"low", "medium", "high"}


def _fact(**kw):
    from backend.app.services.requirement_fact_extractor import RequirementFact

    base = dict(
        text="You must order a tax deduction card before your first salary payment.",
        requirement_type="document",
        corridor="NO",
        confidence_score=0.9,
        source_quote="Order a tax deduction card.",
        source_url="https://www.skatteetaten.no/x/",
    )
    base.update(kw)
    return RequirementFact(**base)


def test_every_requirement_type_maps_into_the_db_check():
    """All five extractor types must land on a value the fact_type CHECK accepts."""
    for rtype in ("document", "fee", "timeline", "eligibility", "other"):
        mapped = ingest._map_llm_fact(_fact(requirement_type=rtype))
        assert mapped["fact_type"] in _FACT_TYPE_CHECK, rtype
    # 'timeline' has no counterpart in the legacy enum — it must become 'deadline'.
    assert ingest._map_llm_fact(_fact(requirement_type="timeline"))["fact_type"] == "deadline"
    # An unknown type degrades rather than writing an invalid value.
    assert ingest._map_llm_fact(_fact(requirement_type="nonsense"))["fact_type"] == "other"


def test_confidence_score_bands_into_the_db_check():
    for score, expected in ((0.01, "low"), (0.49, "low"), (0.5, "medium"),
                            (0.79, "medium"), (0.8, "high"), (1.0, "high")):
        band = ingest._map_llm_fact(_fact(confidence_score=score))["confidence"]
        assert band == expected, (score, band)
        assert band in _CONFIDENCE_CHECK


def test_mapped_fact_carries_evidence_and_a_stable_key():
    mapped = ingest._map_llm_fact(_fact())
    assert mapped["evidence_quote"] == "Order a tax deduction card."
    assert mapped["fact_text"].startswith("You must order a tax deduction card")
    # fact_key is deterministic for identical text, and distinct across facts.
    assert mapped["fact_key"] == ingest._map_llm_fact(_fact())["fact_key"]
    assert mapped["fact_key"] != ingest._map_llm_fact(_fact(text="Something else."))["fact_key"]
    assert mapped["applies_to"] == {}


def test_empty_content_skips_the_model_entirely():
    """No text means no LLM call — guards against burning a request on a dead fetch."""
    called = []
    assert ingest._llm_facts_for_doc("https://x/", "   ", corridor="NO") == []
    assert not called


def test_llm_failure_falls_back_to_rule_based(monkeypatch):
    """A model/network error must degrade to the rule-based facts, not fail the ingest."""
    def boom(*a, **k):
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    monkeypatch.setattr(ingest, "extract_requirement_facts", boom)
    assert ingest._llm_facts_for_doc("https://x/", "Some real content here.", corridor="NO") == []

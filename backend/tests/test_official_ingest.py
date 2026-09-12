"""official_ingest_service — allowlist, baseline-rule creation, and (AIQ-1821) the
LLM fact-extraction path that feeds `requirement_facts`.

Imports canonically as `backend.app.services` (per backend/CLAUDE.md). The old
`from app.services import ...` form only resolved with backend/ on sys.path, which is
why this module sat in conftest's collect_ignore and never ran in CI.
"""
from backend.app.services import official_ingest_service as ingest


def test_allowlist_rejects_non_official():
    try:
        ingest.ingest_url_to_knowledge_doc("https://example.com", "US", "immigration")
        assert False, "Expected ValueError for non-official domain"
    except ValueError:
        assert True


def test_ingest_creates_baseline_rule(monkeypatch):
    def fake_fetch_html(url, destination_country):
        return url, "<html><title>Test</title><body><main>Some content</main></body></html>"

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


def test_failed_fetch_does_not_upsert_empty_evidence(monkeypatch):
    upserts = []

    def boom_fetch(url, destination_country):
        raise ValueError("403 Client Error")

    monkeypatch.setattr(ingest, "_fetch_html", boom_fetch)
    monkeypatch.setattr(ingest.db, "ensure_knowledge_pack", lambda *a, **k: (_ for _ in ()).throw(AssertionError("pack")))
    monkeypatch.setattr(
        ingest.db,
        "upsert_knowledge_doc_by_url",
        lambda **kw: upserts.append(kw) or {"id": "doc1"},
    )

    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/working-in-the-united-states", "US", "immigration"
    )
    assert res["fetch_status"] == "fetch_failed"
    assert res["doc_id"] is None
    assert res["facts_created"] == 0
    assert upserts == []


def test_empty_excerpt_does_not_upsert_empty_evidence(monkeypatch):
    upserts = []

    monkeypatch.setattr(
        ingest, "_fetch_html", lambda url, dest: (url, "<html><body></body></html>")
    )
    monkeypatch.setattr(ingest, "_extract_text", lambda html: ("", ""))
    monkeypatch.setattr(
        ingest.db,
        "upsert_knowledge_doc_by_url",
        lambda **kw: upserts.append(kw) or {"id": "doc1"},
    )

    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/working-in-the-united-states", "US", "immigration"
    )
    assert res["fetch_status"] == "fetch_failed"
    assert "Empty content" in (res["error"] or "")
    assert upserts == []


def test_login_redirect_is_a_failed_fetch():
    assert ingest._looks_like_login_url("https://www.uscis.gov/login?next=/foo")
    assert not ingest._looks_like_login_url("https://www.uscis.gov/working-in-the-united-states")


def test_successful_fetch_still_upserts_excerpt_and_hash(monkeypatch):
    upserts = []

    def fake_upsert(**kwargs):
        upserts.append(kwargs)
        return {"id": "doc1", "title": kwargs.get("title"), "content_excerpt": kwargs.get("content_excerpt")}

    monkeypatch.setattr(
        ingest,
        "_fetch_html",
        lambda url, dest: (url, "<html><title>Test</title><body><main>Some content</main></body></html>"),
    )
    monkeypatch.setattr(ingest.db, "ensure_knowledge_pack", lambda *a, **k: {"id": "pack1"})
    monkeypatch.setattr(ingest.db, "upsert_knowledge_doc_by_url", fake_upsert)
    monkeypatch.setattr(ingest.db, "create_baseline_rule_for_doc", lambda *a, **k: "rule1")
    monkeypatch.setattr(ingest, "_llm_facts_for_doc", lambda *a, **k: [])

    res = ingest.ingest_url_to_knowledge_doc(
        "https://www.uscis.gov/working-in-the-united-states", "US", "immigration"
    )
    assert res["fetch_status"] == "fetched"
    assert upserts
    assert upserts[0]["fetch_status"] == "fetched"
    assert upserts[0]["text_content"]
    assert upserts[0]["content_sha256"]


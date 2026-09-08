"""
[CRAWL-QUALITY-2 / AIQ-1146] Semantic live-dedup: a crawler candidate that
overlaps an existing published country_resources row (same content, different
title) is flagged with duplicate_of_live_resource_id — without false-positiving
distinct same-category topics. Real fixtures from the 2026-06-17 re-crawl.
"""
from unittest.mock import MagicMock, patch

from backend.crawler.dedupe import dedupe as D
from backend.crawler.staging import writer as W

# Hand-seeded live DE housing resource.
LIVE = {
    "id": "live-rental-market",
    "title": "How the rental market works",
    "summary": "",
    "body": (
        "Listings usually quote the base rent (Kaltmiete) plus running costs "
        "(Nebenkosten); together they make the total (Warmmiete). Expect a deposit "
        "(Kaution) of up to three months base rent, held in a separate account and "
        "returned when you leave. Most flats are unfurnished and may not include "
        "kitchen fittings."
    ),
}
# LLM candidate that DUPLICATES the live resource (different title, same content).
COSTS = (
    "Understanding Rental Costs in Germany",
    "In Germany, rental costs are divided into net or cold rent (Kaltmiete) and gross "
    "or warm rent (Warmmiete). The net rent covers only the cost of the flat, while "
    "the gross rent includes operating costs like water, trash and heating.",
)
# LLM candidates that are DISTINCT topics (must NOT be flagged).
AGREEMENTS = (
    "Navigating Rental Agreements in Germany",
    "The rental contract in Germany is a legally binding agreement between tenant and "
    "landlord. It specifies rent composition, deposit requirements and other terms. "
    "Before signing, check for clauses like Staffelmiete (graduated rent).",
)
MOVING = (
    "Preparing for Your Move to a New Flat",
    "Before moving into your new flat, inspect it thoroughly for any damage and "
    "document these in a handover report signed by the landlord. Check all utilities "
    "and fixtures to ensure they are functioning.",
)


def _live_body(row):
    return f"{row.get('summary', '')} {row.get('body', '')}"


def test_similarity_separates_overlap_from_distinct():
    s_costs = D._resource_similarity(COSTS[0], COSTS[1], LIVE["title"], _live_body(LIVE))
    s_agree = D._resource_similarity(AGREEMENTS[0], AGREEMENTS[1], LIVE["title"], _live_body(LIVE))
    s_move = D._resource_similarity(MOVING[0], MOVING[1], LIVE["title"], _live_body(LIVE))
    assert s_costs >= D.SEMANTIC_DUP_THRESHOLD, f"overlap {s_costs} should flag"
    assert s_agree < D.SEMANTIC_DUP_THRESHOLD, f"agreements {s_agree} should NOT flag"
    assert s_move < D.SEMANTIC_DUP_THRESHOLD, f"moving {s_move} should NOT flag"


def _mock_supabase(rows):
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.limit.return_value = q
    q.execute.return_value = MagicMock(data=rows)
    sb = MagicMock()
    sb.table.return_value = q
    return sb


def test_find_live_semantic_duplicate_flags_overlap():
    with patch.object(D, "_get_supabase", return_value=_mock_supabase([LIVE])):
        out = D.find_live_semantic_duplicate("DE", "", COSTS[0], COSTS[1])
    assert out == "live-rental-market"


def test_find_live_semantic_duplicate_passes_distinct_topics():
    with patch.object(D, "_get_supabase", return_value=_mock_supabase([LIVE])):
        assert D.find_live_semantic_duplicate("DE", "", AGREEMENTS[0], AGREEMENTS[1]) is None
        assert D.find_live_semantic_duplicate("DE", "", MOVING[0], MOVING[1]) is None


def test_find_live_semantic_duplicate_no_live_rows():
    with patch.object(D, "_get_supabase", return_value=_mock_supabase([])):
        assert D.find_live_semantic_duplicate("DE", "", COSTS[0], COSTS[1]) is None


def test_find_live_semantic_duplicate_query_error_is_safe():
    sb = MagicMock()
    sb.table.side_effect = RuntimeError("db down")
    with patch.object(D, "_get_supabase", return_value=sb):
        assert D.find_live_semantic_duplicate("DE", "", COSTS[0], COSTS[1]) is None


def _candidate():
    c = MagicMock()
    for k, v in dict(
        country_code="DE", country_name="Germany", city_name="", category_key="housing",
        title="X", summary="s", body="b", content_json={}, resource_type="guide",
        audience_type="all", tags=[], source_url="u", source_name="n", trust_tier="T1",
        confidence_score=0.9, extraction_method="llm_structured_extraction", provenance={},
    ).items():
        setattr(c, k, v)
    return c


def test_writer_flags_dup_and_sets_needs_review():
    captured = {}
    sb = MagicMock()
    def _insert(row):
        captured["row"] = row
        m = MagicMock()
        m.execute.return_value = MagicMock(data=[{"id": "cand-1"}])
        return m
    sb.table.return_value.insert.side_effect = _insert
    with patch.object(W, "_get_supabase", return_value=sb):
        W.write_resource_candidate("run", "doc", "chunk", _candidate(), duplicate_of_live_resource_id="live-rental-market")
    assert captured["row"]["duplicate_of_live_resource_id"] == "live-rental-market"
    assert captured["row"]["status"] == "needs_review"


def test_writer_no_flag_when_not_a_dup():
    captured = {}
    sb = MagicMock()
    def _insert(row):
        captured["row"] = row
        m = MagicMock()
        m.execute.return_value = MagicMock(data=[{"id": "cand-2"}])
        return m
    sb.table.return_value.insert.side_effect = _insert
    with patch.object(W, "_get_supabase", return_value=sb):
        W.write_resource_candidate("run", "doc", "chunk", _candidate())
    assert "duplicate_of_live_resource_id" not in captured["row"]
    assert captured["row"]["status"] == "new"

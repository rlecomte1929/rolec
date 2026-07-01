"""
Mission Control P1 — ingestion. Maps intake rows (feedback bug/idea, support
tickets) into canonical work_item dicts: idempotent on (source, source_id), body
PII-masked, triage applied. Pure (no DB) so it's fully unit-testable.
"""
from backend.app.services.work_item_ingest import build_work_items


def test_feedback_bug_maps_to_a_triaged_work_item():
    rows = [{"id": "f1", "page_url": "/journey", "category": "bug",
             "message": "The save button crashes with a 500 error"}]
    items = build_work_items("feedback", rows)
    assert len(items) == 1
    wi = items[0]
    assert wi["source"] == "feedback" and wi["source_id"] == "f1"
    assert wi["kind"] == "bug"
    assert wi["status"] == "triaged"
    assert wi["source_url"] == "/journey"
    assert wi["dedupe_key"]


def test_feedback_category_other_lets_triage_infer_kind():
    rows = [{"id": "f2", "page_url": "/x", "category": "other",
             "message": "It would be nice to add dark mode"}]
    items = build_work_items("feedback", rows)
    assert items[0]["kind"] == "idea"  # inferred, not from category


def test_idempotent_skips_already_ingested():
    rows = [{"id": "f1", "page_url": "/x", "category": "bug", "message": "broken"}]
    items = build_work_items("feedback", rows, existing_keys={("feedback", "f1")})
    assert items == []


def test_body_is_pii_masked():
    rows = [{"id": "f3", "page_url": "/x", "category": "bug",
             "message": "contact me at jane.doe@example.com about the error"}]
    items = build_work_items("feedback", rows)
    assert "jane.doe@example.com" not in items[0]["body"]


def test_support_ticket_maps_with_company_and_subject_title():
    rows = [{"id": "s1", "subject": "Cannot upload document", "raw_content": "the upload fails every time",
             "company_id": "co-1", "from_email": "hr@acme.com"}]
    items = build_work_items("support", rows)
    wi = items[0]
    assert wi["source"] == "support" and wi["company_id"] == "co-1"
    assert wi["title"] == "Cannot upload document"


def test_unknown_source_returns_empty():
    assert build_work_items("nope", [{"id": "x"}]) == []

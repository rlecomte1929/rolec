import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import types

from app.services import official_ingest_service as ingest


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

    res = ingest.ingest_url_to_knowledge_doc("https://www.uscis.gov/working-in-the-united-states", "US", "immigration")
    assert res["fetch_status"] == "fetched"
    assert res["rule_id"] == "rule1"
    assert created_rules

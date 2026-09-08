"""Regression test for AIQ-930 / E1c.

The policy-document upload pipeline classified a doc and then persisted
`assistant_import_status='classified'` — a value NOT permitted by the
`policy_documents_assistant_import_status_check` CHECK constraint. On Postgres that
raised a CheckViolation which aborted the whole UPDATE, so the doc was marked
`failed` and value-extraction (`_run_policy_value_extraction`) never ran. Result:
the pilot's upload -> AI extraction -> config-matrix chain was broken end-to-end and
`policy_extracted_benefits` never got new rows. SQLite has no CHECK, so the bug was
invisible to the existing suite.

This test mimics the CHECK in a fake `db.update_policy_document` and asserts the
classify persist writes a constraint-valid status AND that the flow reaches
value-extraction.
"""
import importlib

import pytest


@pytest.fixture()
def main_mod():
    return importlib.import_module("backend.main")


def _install_common_mocks(monkeypatch, main_mod, captured):
    """Patch the ingest background function's external collaborators."""
    # process_uploaded_document -> a successful classify with raw text
    import backend.app.services.policy_document_intake as intake

    def fake_process(content, mime, filename, request_id=None):
        return {
            "processing_status": "classified",
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": "global",
            "version_label": "1.0",
            "effective_date": None,
            "raw_text": "Relocation allowance of EUR 8,000 is provided.",
            "extraction_error": None,
            "extracted_metadata": {},
        }

    monkeypatch.setattr(intake, "process_uploaded_document", fake_process)

    # analytics emitters -> no-ops
    import backend.app.services.policy_pipeline_analytics as analytics
    for name in (
        "emit_policy_classify_started",
        "emit_policy_classify_completed",
        "emit_policy_classify_failed",
    ):
        monkeypatch.setattr(analytics, name, lambda *a, **k: None)

    # clause segmentation -> no clauses (skip upsert path deterministically)
    import backend.app.services.policy_document_clauses as clauses_mod
    monkeypatch.setattr(
        clauses_mod, "segment_document_from_raw_text", lambda *a, **k: ([], None)
    )

    # value-extraction -> record that we reached it (the point of the fix)
    def fake_value_extraction(**kwargs):
        captured["value_extraction_called_with"] = kwargs
        return True

    monkeypatch.setattr(main_mod, "_run_policy_value_extraction", fake_value_extraction)

    # db: a fake that enforces the CHECK constraint the same way Postgres does
    class _FakeDB:
        def update_policy_document(self, doc_id, **kwargs):
            ais = kwargs.get("assistant_import_status")
            captured.setdefault("ais_writes", []).append(ais)
            if ais is not None and ais not in main_mod._POLICY_DOC_ASSISTANT_IMPORT_STATUSES:
                # Mirror policy_documents_assistant_import_status_check
                raise Exception(
                    f'CheckViolation: assistant_import_status="{ais}" violates '
                    "policy_documents_assistant_import_status_check"
                )
            return {"id": doc_id}

        def upsert_policy_document_clauses(self, *a, **k):
            return None

        def get_policy_document(self, doc_id, request_id=None):
            return {"id": doc_id, "processing_status": "normalized"}

        def list_policy_document_clauses(self, doc_id, request_id=None):
            return []

    monkeypatch.setattr(main_mod, "db", _FakeDB())


def test_classify_persist_is_constraint_valid_and_reaches_extraction(monkeypatch, main_mod):
    captured = {}
    _install_common_mocks(monkeypatch, main_mod, captured)

    # Should not raise, and must reach value-extraction.
    main_mod._run_policy_document_ingest_background(
        doc_id="doc-1",
        content=b"%PDF-1.4 fake",
        mime="application/pdf",
        filename="policy.pdf",
        request_id="req-1",
        user_id="user-1",
        company_id="company-1",
    )

    # 1. Every assistant_import_status written is constraint-valid.
    ais_writes = [a for a in captured.get("ais_writes", []) if a is not None]
    assert ais_writes, "expected at least one assistant_import_status write"
    for ais in ais_writes:
        assert ais in main_mod._POLICY_DOC_ASSISTANT_IMPORT_STATUSES, ais
    # Specifically, the classify branch must NOT write the invalid 'classified'.
    assert "classified" not in ais_writes

    # 2. The flow reached value-extraction (it never did with the old code, because
    #    the classify UPDATE raised before this call).
    assert "value_extraction_called_with" in captured
    assert captured["value_extraction_called_with"]["doc_id"] == "doc-1"


def test_allowed_status_set_matches_check_constraint(main_mod):
    # Documents the DB CHECK contract and guards against reintroducing 'classified'.
    assert "classified" not in main_mod._POLICY_DOC_ASSISTANT_IMPORT_STATUSES
    assert "text_ready" in main_mod._POLICY_DOC_ASSISTANT_IMPORT_STATUSES
    assert main_mod._POLICY_DOC_ASSISTANT_IMPORT_STATUSES == frozenset(
        {
            "uploaded",
            "extracting_text",
            "text_ready",
            "extracting_facts",
            "ready_for_assistant",
            "failed",
        }
    )

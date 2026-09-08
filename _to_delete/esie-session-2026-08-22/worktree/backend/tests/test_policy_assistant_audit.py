"""
Policy assistant audit harness tests (opt-in).

Run: pytest -m policy_assistant_audit backend/tests/test_policy_assistant_audit.py
Or: RUN_POLICY_ASSISTANT_AUDIT=1 pytest backend/tests/test_policy_assistant_audit.py
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest

pytestmark = pytest.mark.policy_assistant_audit


def test_cross_tenant_leaks_detect_mismatch() -> None:
    from backend.scripts.audit_policy_assistant import cross_tenant_leaks_for_user_company

    leaks = cross_tenant_leaks_for_user_company(
        "company-a",
        ["c1", "c2"],
        {"c1": "company-a", "c2": "company-b"},
    )
    assert len(leaks) == 1
    assert leaks[0]["chunk_id"] == "c2"


def test_cross_tenant_leaks_all_clear() -> None:
    from backend.scripts.audit_policy_assistant import cross_tenant_leaks_for_user_company

    leaks = cross_tenant_leaks_for_user_company(
        "company-a",
        ["c1", "c2"],
        {"c1": "company-a", "c2": "company-a"},
    )
    assert leaks == []


def test_run_policy_assistant_audit_no_leakage_with_fake_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uses the in-memory tenant DB from company-scope tests; patches SQL chunk lookup."""
    from backend.scripts import audit_policy_assistant as audit
    from backend.tests.test_policy_canonical_company_scope import _TenantDb

    fake = _TenantDb()

    def _chunk_ids_no_sql(db: object, chunk_ids: list) -> dict:
        mapping: dict = {}
        for _doc_id, chunks in getattr(db, "chunks", {}).items():
            for ch in chunks:
                mapping[str(ch["id"])] = str(ch.get("company_id"))
        return {cid: mapping.get(cid) for cid in chunk_ids}

    monkeypatch.setattr(audit, "chunk_company_ids", _chunk_ids_no_sql)

    report = audit.run_policy_assistant_audit(
        fake,
        company_acme="company-a",
        company_beta="company-b",
        queries=[
            ("EMPLOYEE", "company-a", "What is my relocation allowance if I have two dependants?"),
            ("EMPLOYEE", "company-b", "What is my relocation allowance if I have two dependants?"),
        ],
        seed_tenants=False,
    )

    assert report["summary"]["cross_company_retrievals"] == 0
    assert report["summary"]["validation_failures"] == 0
    for row in report["queries"]:
        assert row["cross_tenant_leakage"] == []

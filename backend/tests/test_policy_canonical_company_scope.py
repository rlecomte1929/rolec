from __future__ import annotations

import unittest
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import policy_canonical as policy_canonical_router
from backend.app.services.policy_query_answering import answer_company_scoped_policy_query
from backend.app.services.policy_rendering import render_canonical_policy_markdown


class _TenantDb:
    def __init__(self) -> None:
        self.audit_logs: List[Dict[str, Any]] = []
        self.documents = {
            "doc-a": {
                "id": "doc-a",
                "company_id": "company-a",
                "title": "GOPS 12102",
                "version_label": "v1",
                "filename": "GOPS 12102.pdf",
                "extraction_status": "extracted",
            },
            "doc-b": {
                "id": "doc-b",
                "company_id": "company-b",
                "title": "Long Term Assignment Policy Summary",
                "version_label": "v2",
                "filename": "Long Term Assignment Policy Summary.pdf",
                "extraction_status": "extracted",
            },
        }
        self.chunks = {
            "doc-a": [
                {
                    "id": "chunk-a1",
                    "company_id": "company-a",
                    "canonical_policy_document_id": "doc-a",
                    "chunk_index": 0,
                    "section_path": "Pre-assignment > Allowances",
                    "structure_type": "paragraph",
                    "text_content": "Relocation allowance up to USD 2500 for employees with two dependants.",
                },
                {
                    "id": "chunk-a2",
                    "company_id": "company-a",
                    "canonical_policy_document_id": "doc-a",
                    "chunk_index": 1,
                    "section_path": "Assignment > Mobility premium",
                    "structure_type": "paragraph",
                    "text_content": "Mobility premium of 10% applies for STA and LTA assignments.",
                },
            ],
            "doc-b": [
                {
                    "id": "chunk-b1",
                    "company_id": "company-b",
                    "canonical_policy_document_id": "doc-b",
                    "chunk_index": 0,
                    "section_path": "Pre-assignment > Allowances",
                    "structure_type": "paragraph",
                    "text_content": "Relocation allowance up to USD 1500 for employees with two dependants.",
                }
            ],
        }
        self.facts = {
            "doc-a": [
                {
                    "id": "fact-a1",
                    "company_id": "company-a",
                    "canonical_policy_document_id": "doc-a",
                    "canonical_policy_document_chunk_id": "chunk-a1",
                    "phase": "pre_assignment",
                    "benefit_category": "allowance",
                    "title": "Relocation allowance",
                    "description": "Allowance for accompanied move",
                    "amount": 2500,
                    "currency": "USD",
                    "frequency": "one_time",
                    "assignment_types_json": ["long_term"],
                    "eligibility_json": {"family_statuses": ["two dependants"]},
                },
                {
                    "id": "fact-a2",
                    "company_id": "company-a",
                    "canonical_policy_document_id": "doc-a",
                    "canonical_policy_document_chunk_id": "chunk-a2",
                    "phase": "on_assignment",
                    "benefit_category": "mobility_premium",
                    "title": "Mobility premium",
                    "description": "Premium for assignment",
                    "percentage": 10,
                    "assignment_types_json": ["short_term", "long_term"],
                    "eligibility_json": {},
                },
            ],
            "doc-b": [
                {
                    "id": "fact-b1",
                    "company_id": "company-b",
                    "canonical_policy_document_id": "doc-b",
                    "canonical_policy_document_chunk_id": "chunk-b1",
                    "phase": "pre_assignment",
                    "benefit_category": "allowance",
                    "title": "Relocation allowance",
                    "description": "Allowance for accompanied move",
                    "amount": 1500,
                    "currency": "USD",
                    "frequency": "one_time",
                    "assignment_types_json": ["long_term"],
                    "eligibility_json": {"family_statuses": ["two dependants"]},
                }
            ],
        }

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        mapping = {
            "hr-a": {"id": "user-hr-a", "role": "HR", "email": "hr-a@company.test"},
            "emp-a": {"id": "user-emp-a", "role": "EMPLOYEE", "email": "emp-a@company.test"},
            "admin": {"id": "user-admin", "role": "ADMIN", "email": "admin@relopass.com"},
        }
        return mapping.get(token)

    def get_profile_record(self, user_id: str) -> Optional[Dict[str, Any]]:
        mapping = {
            "user-hr-a": {"id": user_id, "role": "HR", "company_id": "company-a"},
            "user-emp-a": {"id": user_id, "role": "EMPLOYEE", "company_id": "company-a"},
            "user-admin": {"id": user_id, "role": "ADMIN", "company_id": None},
        }
        return mapping.get(user_id)

    def is_admin_allowlisted(self, email: str) -> bool:
        return email.endswith("@relopass.com")

    def list_canonical_policy_documents(self, **kwargs: Any) -> List[Dict[str, Any]]:
        company_id = kwargs.get("company_id")
        return [doc for doc in self.documents.values() if not company_id or doc["company_id"] == company_id]

    def get_canonical_policy_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        return self.documents.get(document_id)

    def get_active_canonical_policy_document_for_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        for document in self.documents.values():
            if document["company_id"] == company_id:
                return document
        return None

    def list_canonical_policy_document_chunks(self, document_id: str, *, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self.chunks.get(document_id, [])
        if company_id:
            return [row for row in rows if row["company_id"] == company_id]
        return rows

    def list_canonical_policy_facts(self, document_id: str, *, company_id: Optional[str] = None, **kwargs: Any) -> List[Dict[str, Any]]:
        _ = kwargs
        rows = self.facts.get(document_id, [])
        if company_id:
            return [row for row in rows if row["company_id"] == company_id]
        return rows

    def insert_canonical_policy_query_audit_log(self, **kwargs: Any) -> str:
        self.audit_logs.append(kwargs)
        return f"audit-{len(self.audit_logs)}"

    def list_canonical_policy_query_audit_logs(self, **kwargs: Any) -> List[Dict[str, Any]]:
        company_id = kwargs.get("company_id")
        logs = self.audit_logs
        if company_id:
            logs = [row for row in logs if row["company_id"] == company_id]
        return [
            {
                "id": f"audit-{idx + 1}",
                **row,
                "retrieved_chunk_ids_json": row["retrieved_chunk_ids"],
            }
            for idx, row in enumerate(logs)
        ]

    def update_canonical_policy_document(self, document_id: str, **kwargs: Any) -> None:
        self.documents[document_id].update(kwargs)

    def get_canonical_policy_audit_summary(self, document_id: str, *, company_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "document_id": document_id,
            "company_id": company_id,
            "chunks_count": len(self.list_canonical_policy_document_chunks(document_id, company_id=company_id)),
            "facts_count": len(self.list_canonical_policy_facts(document_id, company_id=company_id)),
            "validation_error_count": 0,
            "validation_pass_rate": 1.0,
            "counts_by_category": {},
            "counts_by_phase": {},
        }

    def canonical_policy_tables_available(self) -> bool:
        return True


class PolicyCanonicalCompanyScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _TenantDb()

    def test_retrieval_is_company_scoped(self) -> None:
        result = answer_company_scoped_policy_query(
            self.db,
            company_id="company-a",
            user_id="user-emp-a",
            user_role="EMPLOYEE",
            query="What is my relocation allowance if I have two dependants?",
        )
        self.assertIn("2500", result["answer"])
        self.assertNotIn("1500", result["answer"])
        self.assertEqual(result["canonical_policy_document_id"], "doc-a")
        self.assertTrue(all(chunk_id.startswith("chunk-a") for chunk_id in result["retrieved_chunk_ids"]))
        result_b = answer_company_scoped_policy_query(
            self.db,
            company_id="company-b",
            user_id="user-emp-b",
            user_role="EMPLOYEE",
            query="What is my relocation allowance if I have two dependants?",
        )
        self.assertIn("1500", result_b["answer"])
        self.assertNotIn("2500", result_b["answer"])

    def test_rendering_contains_expected_sections(self) -> None:
        markdown = render_canonical_policy_markdown(
            self.db.documents["doc-a"],
            self.db.facts["doc-a"],
        )
        self.assertIn("## Pre-Assignment", markdown)
        self.assertIn("## Assignment", markdown)
        self.assertIn("### Allowance", markdown)
        self.assertIn("### Mobility Premium", markdown)

    def test_audit_logging_records_retrieved_chunks(self) -> None:
        answer_company_scoped_policy_query(
            self.db,
            company_id="company-a",
            user_id="user-emp-a",
            user_role="EMPLOYEE",
            query="What is the mobility premium?",
        )
        self.assertEqual(len(self.db.audit_logs), 1)
        log = self.db.audit_logs[0]
        self.assertEqual(log["company_id"], "company-a")
        self.assertEqual(log["user_role"], "EMPLOYEE")
        self.assertTrue(log["retrieved_chunk_ids"])

    def test_employee_cannot_use_admin_mutation_route(self) -> None:
        originals = (
            policy_canonical_router.db.get_user_by_token,
            policy_canonical_router.db.get_profile_record,
            policy_canonical_router.db.is_admin_allowlisted,
            policy_canonical_router.db.list_canonical_policy_documents,
        )
        try:
            policy_canonical_router.db.get_user_by_token = self.db.get_user_by_token
            policy_canonical_router.db.get_profile_record = self.db.get_profile_record
            policy_canonical_router.db.is_admin_allowlisted = self.db.is_admin_allowlisted
            policy_canonical_router.db.list_canonical_policy_documents = self.db.list_canonical_policy_documents
            app = FastAPI()
            app.include_router(policy_canonical_router.admin_router, prefix="/api/admin")
            client = TestClient(app)
            response = client.get(
                "/api/admin/policy-canonical/documents",
                headers={"Authorization": "Bearer emp-a"},
            )
            self.assertEqual(response.status_code, 403)
        finally:
            (
                policy_canonical_router.db.get_user_by_token,
                policy_canonical_router.db.get_profile_record,
                policy_canonical_router.db.is_admin_allowlisted,
                policy_canonical_router.db.list_canonical_policy_documents,
            ) = originals

    def test_employee_can_render_and_query_current_company_policy(self) -> None:
        originals = (
            policy_canonical_router.db.get_user_by_token,
            policy_canonical_router.db.get_profile_record,
            policy_canonical_router.db.is_admin_allowlisted,
            policy_canonical_router.db.get_active_canonical_policy_document_for_company,
            policy_canonical_router.db.list_canonical_policy_facts,
            policy_canonical_router.db.get_canonical_policy_document,
            policy_canonical_router.db.list_canonical_policy_document_chunks,
            policy_canonical_router.db.insert_canonical_policy_query_audit_log,
            policy_canonical_router.db.list_canonical_policy_query_audit_logs,
        )
        try:
            policy_canonical_router.db.get_user_by_token = self.db.get_user_by_token
            policy_canonical_router.db.get_profile_record = self.db.get_profile_record
            policy_canonical_router.db.is_admin_allowlisted = self.db.is_admin_allowlisted
            policy_canonical_router.db.get_active_canonical_policy_document_for_company = self.db.get_active_canonical_policy_document_for_company
            policy_canonical_router.db.list_canonical_policy_facts = self.db.list_canonical_policy_facts
            policy_canonical_router.db.get_canonical_policy_document = self.db.get_canonical_policy_document
            policy_canonical_router.db.list_canonical_policy_document_chunks = self.db.list_canonical_policy_document_chunks
            policy_canonical_router.db.insert_canonical_policy_query_audit_log = self.db.insert_canonical_policy_query_audit_log
            policy_canonical_router.db.list_canonical_policy_query_audit_logs = self.db.list_canonical_policy_query_audit_logs
            app = FastAPI()
            app.include_router(policy_canonical_router.read_router, prefix="/api")
            client = TestClient(app)

            render_response = client.get(
                "/api/policy-canonical/render/current",
                headers={"Authorization": "Bearer emp-a"},
            )
            self.assertEqual(render_response.status_code, 200)
            self.assertIn("Pre-Assignment", render_response.json()["markdown"])

            query_response = client.post(
                "/api/policy-canonical/query",
                json={"message": "What is my relocation allowance if I have two dependants?"},
                headers={"Authorization": "Bearer emp-a"},
            )
            self.assertEqual(query_response.status_code, 200)
            body = query_response.json()
            self.assertIn("2500", body["answer"])
            self.assertTrue(body["citations"])
        finally:
            (
                policy_canonical_router.db.get_user_by_token,
                policy_canonical_router.db.get_profile_record,
                policy_canonical_router.db.is_admin_allowlisted,
                policy_canonical_router.db.get_active_canonical_policy_document_for_company,
                policy_canonical_router.db.list_canonical_policy_facts,
                policy_canonical_router.db.get_canonical_policy_document,
                policy_canonical_router.db.list_canonical_policy_document_chunks,
                policy_canonical_router.db.insert_canonical_policy_query_audit_log,
                policy_canonical_router.db.list_canonical_policy_query_audit_logs,
            ) = originals


if __name__ == "__main__":
    unittest.main()

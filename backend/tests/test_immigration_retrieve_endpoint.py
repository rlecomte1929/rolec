"""
W1 / AIQ-835 — contract test for POST /api/immigration/retrieve.

Proves the immigration retriever is wired into a live, authenticated endpoint
(dual-registered in the prod app), returns the documented shape, handles an
empty corpus cleanly (corpus_empty=true, HTTP 200, no raise), and that the
underlying _build_query produces the exact structured string.

The retriever is mocked so this isolates the HTTP contract + wiring from the DB.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("POLICY_ASSISTANT_EMBEDDER", "hash")
os.environ.setdefault("POLICY_ASSISTANT_LLM", "mock")

import unittest
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import get_current_user
from backend.app.services.immigration_retriever import (
    PathClassification,
    UserProfile,
    _build_query,
    corridor_key,
)

_USER: Dict[str, Any] = {"id": "u1", "role": "hr", "email": "hr@company-a.test"}
_RETRIEVER = "backend.app.services.immigration_retriever.retrieve_for_profile"
_BODY = {
    "corridor_from": "FR",
    "corridor_to": "NO",
    "nationality": "French",
    "permit_type": "work_permit",
    "is_eea": True,
}


class TestImmigrationRetrieveEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: _USER
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)

    def test_route_registered_in_prod_app(self):
        # CLAUDE.md hard rule: must be reachable on the prod app instance.
        paths = {getattr(r, "path", None) for r in app.routes}
        self.assertIn("/api/immigration/retrieve", paths)

    def test_empty_corpus_returns_200_and_flag(self):
        with patch(_RETRIEVER, return_value=[]):
            resp = self.client.post("/api/immigration/retrieve", json=_BODY)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(set(body), {"chunks", "corridor", "query_string", "corpus_empty"})
        self.assertEqual(body["corridor"], "FR→NO")
        self.assertEqual(body["chunks"], [])
        self.assertTrue(body["corpus_empty"])

    def test_nonempty_corpus_shape(self):
        fake = [{"id": "c1", "chunk_text": "...", "score": 0.9, "chunk_metadata": {"corridor": "FR→NO"}}]
        with patch(_RETRIEVER, return_value=fake):
            resp = self.client.post("/api/immigration/retrieve", json=_BODY)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["corpus_empty"])
        self.assertEqual(len(body["chunks"]), 1)
        self.assertEqual(body["chunks"][0]["id"], "c1")

    def test_requires_authentication(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            resp = self.client.post("/api/immigration/retrieve", json=_BODY)
            self.assertIn(resp.status_code, (401, 403))
        finally:
            app.dependency_overrides[get_current_user] = lambda: _USER

    def test_build_query_exact_string(self):
        # W1 validation criterion #3 — exact structured query string.
        profile = UserProfile(
            nationality="Indian", origin_country="FR", destination_country="DE", is_eea=False
        )
        classification = PathClassification(pathway_type="work", corridor=corridor_key("FR", "DE"))
        self.assertEqual(
            _build_query(profile, classification, "FR→DE"),
            "work immigration requirements for a non-EEA Indian national relocating FR→DE",
        )


if __name__ == "__main__":
    unittest.main()

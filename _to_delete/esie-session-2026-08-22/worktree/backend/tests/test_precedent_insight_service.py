"""
Tests for backend/app/services/precedent_insight_service.py (AI-005).

In-memory SQLite engine with a minimal policy_cap_requests schema. The
service uses a Postgres-only INTERVAL literal in its WHERE clause, so the
tests rewrite the SQL on the fly via a before_cursor_execute listener
(same trick as test_ai_decisions_router.py).
"""
from __future__ import annotations

import os
import re
import sys
import unittest
import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.precedent_insight_service import (  # noqa: E402
    compute_precedent_insight,
    insight_recommendation_id,
    SOURCE_VERSION,
)


SCHEMA = """
CREATE TABLE policy_cap_requests (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  category TEXT NOT NULL,
  benefit_key TEXT,
  status TEXT NOT NULL,
  resolved_at TEXT,
  created_at TEXT NOT NULL
);
"""

# The service uses `resolved_at > NOW() - INTERVAL '24 months'` — Postgres-only.
# Rewrite for SQLite to a simple "last 24 months as ISO date" comparison.
_INTERVAL_RE = re.compile(
    r"resolved_at\s*>\s*NOW\(\)\s*-\s*INTERVAL\s*'(\d+)\s*months?'",
    re.IGNORECASE,
)


class PrecedentInsightServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )

        # Compute a stable "24 months ago" ISO date once for the rewriter so
        # the test isn't sensitive to the exact second the SQL fires.
        cutoff = (datetime.utcnow() - timedelta(days=730)).isoformat()
        self._cutoff = cutoff

        @event.listens_for(self.engine, "before_cursor_execute", retval=True)
        def _rewrite_interval(conn, cursor, statement, parameters, context, executemany):
            new = _INTERVAL_RE.sub(f"resolved_at > '{cutoff}'", statement)
            return new, parameters

        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

    def _seed(
        self,
        *,
        organization_id: str,
        category: str,
        benefit_key: str | None,
        status: str,
        resolved_days_ago: int = 30,
    ) -> str:
        row_id = str(uuid.uuid4())
        resolved = (datetime.utcnow() - timedelta(days=resolved_days_ago)).isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO policy_cap_requests "
                    "(id, organization_id, category, benefit_key, status, resolved_at, created_at) "
                    "VALUES (:id, :org, :cat, :bk, :status, :resolved, :created)"
                ),
                {
                    "id": row_id,
                    "org": organization_id,
                    "cat": category,
                    "bk": benefit_key,
                    "status": status,
                    "resolved": resolved,
                    "created": resolved,
                },
            )
        return row_id

    # ------------------------------------------------------------------
    def test_no_history_returns_zero_confidence_insight(self) -> None:
        with self.engine.begin() as conn:
            insight = compute_precedent_insight(
                conn,
                category="cap_override",
                benefit_key="international_school",
                organization_id="company-a",
            )
        self.assertEqual(insight["confidence"], 0.0)
        self.assertEqual(insight["sample_size"], 0)
        self.assertEqual(insight["historical_approval_rate"], 0.0)
        self.assertIn("No precedent yet", insight["rationale"])
        self.assertEqual(insight["source_version"], SOURCE_VERSION)
        self.assertEqual(insight["similar_case_ids"], [])

    def test_below_min_samples_still_returns_no_precedent(self) -> None:
        # Two approved rows — below the 3-sample floor.
        for _ in range(2):
            self._seed(
                organization_id="company-a",
                category="cap_override",
                benefit_key="international_school",
                status="approved",
            )
        with self.engine.begin() as conn:
            insight = compute_precedent_insight(
                conn,
                category="cap_override",
                benefit_key="international_school",
                organization_id="company-a",
            )
        self.assertEqual(insight["confidence"], 0.0)
        self.assertEqual(insight["sample_size"], 2)
        self.assertIn("No precedent yet", insight["rationale"])

    def test_above_min_samples_computes_approval_rate(self) -> None:
        for _ in range(3):
            self._seed(
                organization_id="company-a",
                category="cap_override",
                benefit_key="international_school",
                status="approved",
            )
        self._seed(
            organization_id="company-a",
            category="cap_override",
            benefit_key="international_school",
            status="rejected",
        )
        with self.engine.begin() as conn:
            insight = compute_precedent_insight(
                conn,
                category="cap_override",
                benefit_key="international_school",
                organization_id="company-a",
            )
        # 3 of 4 approved == 75% rate
        self.assertEqual(insight["sample_size"], 4)
        self.assertEqual(insight["historical_approval_rate"], 0.75)
        self.assertGreater(insight["confidence"], 0.0)
        self.assertIn("75%", insight["rationale"])

    def test_excludes_self_from_sample(self) -> None:
        # Three other approved rows + the request we're computing insight FOR
        for _ in range(3):
            self._seed(
                organization_id="company-a",
                category="cap_override",
                benefit_key="international_school",
                status="approved",
            )
        self_id = self._seed(
            organization_id="company-a",
            category="cap_override",
            benefit_key="international_school",
            status="approved",
        )
        with self.engine.begin() as conn:
            insight = compute_precedent_insight(
                conn,
                category="cap_override",
                benefit_key="international_school",
                organization_id="company-a",
                exclude_request_id=self_id,
            )
        # Should see 3, not 4
        self.assertEqual(insight["sample_size"], 3)
        self.assertNotIn(self_id, insight["similar_case_ids"])

    def test_scoped_by_organization(self) -> None:
        # Company A: 3 approved
        for _ in range(3):
            self._seed(
                organization_id="company-a",
                category="cap_override",
                benefit_key=None,
                status="approved",
            )
        # Company B: 3 rejected — should not leak into A's insight
        for _ in range(3):
            self._seed(
                organization_id="company-b",
                category="cap_override",
                benefit_key=None,
                status="rejected",
            )
        with self.engine.begin() as conn:
            a_insight = compute_precedent_insight(
                conn,
                category="cap_override",
                benefit_key=None,
                organization_id="company-a",
            )
            b_insight = compute_precedent_insight(
                conn,
                category="cap_override",
                benefit_key=None,
                organization_id="company-b",
            )
        self.assertEqual(a_insight["historical_approval_rate"], 1.0)
        self.assertEqual(b_insight["historical_approval_rate"], 0.0)

    def test_ignores_pending_rows(self) -> None:
        # Pending rows should not count toward precedent (no decision yet).
        for _ in range(5):
            self._seed(
                organization_id="company-a",
                category="cap_override",
                benefit_key=None,
                status="pending",
            )
        with self.engine.begin() as conn:
            insight = compute_precedent_insight(
                conn,
                category="cap_override",
                benefit_key=None,
                organization_id="company-a",
            )
        self.assertEqual(insight["sample_size"], 0)

    def test_recommendation_id_is_deterministic(self) -> None:
        a = insight_recommendation_id("exc-1041")
        b = insight_recommendation_id("exc-1041")
        self.assertEqual(a, b)
        self.assertEqual(a, "precedent_v1:exc-1041")


if __name__ == "__main__":
    unittest.main()

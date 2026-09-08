"""
[P3-5 / AIQ-240] Integration test — policy update propagation to downstream views.

Strategic objective (from the Notion brief): guarantee that when HR publishes a
new policy version, every downstream surface that reads the published policy
immediately reflects the new values and **no stale data is served** — without
any manual cache-busting.

What this test exercises
────────────────────────
The *real, mounted* FastAPI app (`backend.main:app`) over a TestClient, backed
by an in-memory SQLite engine patched into the shared `backend.database.db`
singleton. Every assertion goes through an HTTP endpoint, mirroring the brief's
"verified by querying API endpoints directly after publish".

Propagation chain under test (the one a single `/api/policy/publish` event
actually drives):

    POST /api/policy/publish              ← HR publishes a version
      → GET  /api/policy/summary          ← Benefits Summary tab (P1-5)
      → GET  /api/policy/active/{company} ← currently-active version
      → GET  /api/policy/versions/{company} ← version history / archive flag

Scenario
  1. Seed company + HR + policy + 14 categories + a "Manager" tier.
  2. Publish v1 with housing (CAT-01) cap = EUR 3,000.
  3. Assert summary + active endpoints show cap 3,000, banner "active".
  4. Publish v2 with housing cap = EUR 3,500.
  5. Assert summary + active now show 3,500 and NOT the stale 3,000.
  6. Assert version history shows v1 archived, v2 published.
  7. In a second company, publish a version with a past expiry_date and assert
     the summary returns the amber "expired" banner.

Each step is recorded; a pass/fail report is written to
`<RELOPASS_PROPAGATION_REPORT_DIR or repo_root/results>/integration_test_report_YYYYMMDD.json`.
Any failing check records the endpoint and the stale value found.

Architectural note (documented divergence from "Dev Plan v1.0")
───────────────────────────────────────────────────────────────
The brief also names an "employee comparison" surface. In the current codebase
the cap-comparison endpoint (`/api/hr/policy-config/caps/compare`) is fed by a
*separate* subsystem (`policy_config_matrix_svc`, its own draft→published
lifecycle) and is NOT driven by `POST /api/policy/publish`. Driving it from the
publish flow would test a premise that no longer holds, so it is intentionally
out of scope here and flagged as a follow-up. The summary + banner chain below
is the propagation that the publish event genuinely owns.

Self-contained: in-memory SQLite, no external services, deterministic, runs in
well under a second. Lives in `backend/tests/` (not `tests/integration/`, which
is reserved for the live-service RLS suite that CI skips) so it can be wired
into the deterministic CI job.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Must be set before backend.main is imported (rate limits + query-counter
# event listener that errors against a patched engine).
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

import backend.database as bdb  # noqa: E402
from backend.main import app  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402
from backend.app.routers.policy_publish import EXPECTED_CATEGORY_CODES  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Schema — superset of every column the publish + summary + history endpoints
# read or write. Mirrors test_policy_publish.py and the policy_summary router.
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE companies (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE profiles (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    full_name   TEXT,
    company_id  TEXT,
    role        TEXT NOT NULL DEFAULT 'employee'
);
CREATE TABLE company_policies (
    id         TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    title      TEXT NOT NULL
);
CREATE TABLE policy_versions (
    id             TEXT PRIMARY KEY,
    policy_id      TEXT NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    status         TEXT NOT NULL DEFAULT 'draft',
    effective_date TEXT,
    expiry_date    TEXT,
    published_by   TEXT,
    published_at   TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE policy_categories (
    id           TEXT PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    sort_order   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE policy_tiers (
    id         TEXT PRIMARY KEY,
    company_id TEXT,
    name       TEXT NOT NULL
);
CREATE TABLE policy_values (
    id            TEXT PRIMARY KEY,
    version_id    TEXT NOT NULL,
    category_id   TEXT NOT NULL,
    company_id    TEXT NOT NULL,
    policy_tier_id TEXT,
    cap_value     REAL,
    cap_unit      TEXT,
    cap_currency  TEXT NOT NULL DEFAULT 'EUR',
    value_notes   TEXT,
    validated_by  TEXT,
    validated_at  TEXT
);
CREATE TABLE audit_log (
    id            TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    target_type   TEXT NOT NULL,
    target_id     TEXT,
    reason        TEXT,
    metadata_json TEXT,
    created_at    TEXT NOT NULL
);
"""

HOUSING_CODE = "CAT-01"  # Housing & Accommodation — the cap we mutate across versions


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────────────────────────────────────

class PolicyUpdatePropagationTest(unittest.TestCase):
    """End-to-end propagation of a policy publish to downstream read endpoints."""

    def setUp(self) -> None:
        # StaticPool + a single shared connection so the in-memory DB is visible
        # across threads — the TestClient dispatches sync endpoints on a worker
        # thread, which would otherwise see its own empty :memory: database.
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        # Point the shared db singleton (used by every policy router) at our
        # in-memory engine for the duration of the test.
        self._engine_patcher = mock.patch.object(bdb.db, "engine", self.engine)
        self._engine_patcher.start()

        # 14 canonical categories are global (not company-scoped) — seed once.
        with self.engine.begin() as conn:
            self.cat_ids: Dict[str, str] = {}
            for i, code in enumerate(EXPECTED_CATEGORY_CODES, start=1):
                cid = _uuid()
                conn.execute(
                    text(
                        "INSERT INTO policy_categories "
                        "(id, code, display_name, sort_order) "
                        "VALUES (:id, :c, :n, :s)"
                    ),
                    {"id": cid, "c": code, "n": f"Category {i}", "s": i},
                )
                self.cat_ids[code] = cid

        # Auth: the routers depend on backend.app.auth_deps.get_current_user.
        # We swap the resolved user per scenario phase via a mutable holder so
        # HR-company scoping is exercised faithfully.
        self.current_user: Dict[str, Any] = {}
        app.dependency_overrides[get_current_user] = lambda: self.current_user

        self.client = TestClient(app, raise_server_exceptions=False)
        self.checks: List[Dict[str, Any]] = []

    def tearDown(self) -> None:
        # Always emit the report — even on failure it captures the stale value.
        self._write_report()
        app.dependency_overrides.pop(get_current_user, None)
        self._engine_patcher.stop()
        self.engine.dispose()

    # ── report helpers ───────────────────────────────────────────────────────

    def _record(
        self,
        *,
        step: int,
        description: str,
        endpoint: str,
        expected: Any,
        actual: Any,
        stale_value: Any = None,
    ) -> bool:
        passed = expected == actual
        self.checks.append({
            "step": step,
            "description": description,
            "endpoint": endpoint,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            # Only meaningful for "no stale data" checks: the old value that
            # leaked through after a republish.
            "stale_value_found": stale_value if not passed else None,
        })
        return passed

    def _write_report(self) -> None:
        report_dir = Path(
            os.environ.get("RELOPASS_PROPAGATION_REPORT_DIR")
            or os.path.join(_REPO_ROOT, "results")
        )
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = report_dir / f"integration_test_report_{stamp}.json"

        passed = sum(1 for c in self.checks if c["passed"])
        report = {
            "task": "P3-5 / AIQ-240 — policy update propagation to downstream views",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total": len(self.checks),
                "passed": passed,
                "failed": len(self.checks) - passed,
                "all_passed": passed == len(self.checks) and bool(self.checks),
            },
            "checks": self.checks,
        }
        path.write_text(json.dumps(report, indent=2))
        # Visible in pytest -s / CI logs so the reviewer knows where to look.
        print(f"\n[P3-5] propagation report written → {path}")

    # ── seed helpers ─────────────────────────────────────────────────────────

    def _seed_company(self, *, name: str) -> Dict[str, Any]:
        company_id = _uuid()
        hr_id = _uuid()
        policy_id = _uuid()
        tier_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO companies (id, name) VALUES (:id, :n)"),
                {"id": company_id, "n": name},
            )
            conn.execute(
                text(
                    "INSERT INTO profiles (id, email, full_name, company_id, role) "
                    "VALUES (:id, :e, :f, :c, 'hr')"
                ),
                {"id": hr_id, "e": f"hr@{name}.test", "f": "HR Admin", "c": company_id},
            )
            conn.execute(
                text(
                    "INSERT INTO company_policies (id, company_id, title) "
                    "VALUES (:id, :c, :t)"
                ),
                {"id": policy_id, "c": company_id, "t": f"{name} Relocation Policy"},
            )
            conn.execute(
                text(
                    "INSERT INTO policy_tiers (id, company_id, name) "
                    "VALUES (:id, :c, 'Manager')"
                ),
                {"id": tier_id, "c": company_id},
            )
        return {
            "company_id": company_id,
            "hr_id": hr_id,
            "policy_id": policy_id,
            "tier_id": tier_id,
        }

    def _seed_draft_version(
        self,
        ctx: Dict[str, Any],
        *,
        housing_cap: float,
    ) -> str:
        """Create a draft version with a policy_values row for all 14 categories
        (so it passes the publish completeness check). The housing cap (CAT-01)
        is tagged to the Manager tier and set to `housing_cap`."""
        vid = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO policy_versions (id, policy_id, status) "
                    "VALUES (:id, :pid, 'draft')"
                ),
                {"id": vid, "pid": ctx["policy_id"]},
            )
            for code, cat_id in self.cat_ids.items():
                is_housing = code == HOUSING_CODE
                conn.execute(
                    text(
                        "INSERT INTO policy_values "
                        "(id, version_id, category_id, company_id, policy_tier_id, "
                        " cap_value, cap_unit, cap_currency) "
                        "VALUES (:id, :v, :c, :co, :tier, :amt, 'month', 'EUR')"
                    ),
                    {
                        "id": _uuid(),
                        "v": vid,
                        "c": cat_id,
                        "co": ctx["company_id"],
                        "tier": ctx["tier_id"] if is_housing else None,
                        "amt": housing_cap if is_housing else 1000.0,
                    },
                )
        return vid

    def _hr_user(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": ctx["hr_id"], "role": "hr", "company_id": ctx["company_id"]}

    def _housing_cap_from_summary(self, summary: Dict[str, Any]) -> Optional[float]:
        cat = next(
            (c for c in summary["categories"] if c["code"] == HOUSING_CODE), None
        )
        if not cat or not cat["rows"]:
            return None
        return cat["rows"][0]["cap_value"]

    # ── the scenario ─────────────────────────────────────────────────────────

    def test_policy_update_propagates_with_no_stale_data(self) -> None:
        ctx = self._seed_company(name="acme")
        self.current_user = self._hr_user(ctx)
        company_id = ctx["company_id"]

        # ── Step 1: publish v1 with housing cap 3000 ─────────────────────────
        v1 = self._seed_draft_version(ctx, housing_cap=3000.0)
        r = self.client.post(
            "/api/policy/publish",
            json={"version_id": v1, "effective_date": "2026-06-01",
                  "expiry_date": "2027-05-31", "notes": "Initial publish"},
        )
        body = r.json()
        self._record(step=1, description="publish v1 returns 200",
                     endpoint="POST /api/policy/publish",
                     expected=200, actual=r.status_code)
        self._record(step=1, description="v1 published as version_number 1",
                     endpoint="POST /api/policy/publish",
                     expected=1, actual=body.get("version", {}).get("version_number"))

        # ── Step 2: summary reflects cap 3000, banner active ─────────────────
        r = self.client.get(f"/api/policy/summary?company_id={company_id}")
        summary = r.json()
        self._record(step=2, description="summary status_banner active for v1",
                     endpoint="GET /api/policy/summary",
                     expected="active", actual=summary.get("status_banner"))
        self._record(step=2, description="summary housing cap == 3000 after v1",
                     endpoint="GET /api/policy/summary",
                     expected=3000.0, actual=self._housing_cap_from_summary(summary))

        # ── Step 3: active endpoint points at v1 ─────────────────────────────
        r = self.client.get(f"/api/policy/active/{company_id}")
        active = r.json()
        self._record(step=3, description="active version is v1",
                     endpoint="GET /api/policy/active/{company_id}",
                     expected=v1, actual=(active or {}).get("id"))

        # ── Step 4: publish v2 with housing cap 3500 ─────────────────────────
        v2 = self._seed_draft_version(ctx, housing_cap=3500.0)
        r = self.client.post(
            "/api/policy/publish",
            json={"version_id": v2, "effective_date": "2026-07-01",
                  "notes": "Raise housing cap"},
        )
        body = r.json()
        self._record(step=4, description="publish v2 returns 200",
                     endpoint="POST /api/policy/publish",
                     expected=200, actual=r.status_code)
        self._record(step=4, description="v2 published as version_number 2",
                     endpoint="POST /api/policy/publish",
                     expected=2, actual=body.get("version", {}).get("version_number"))
        self._record(step=4, description="publishing v2 archived v1",
                     endpoint="POST /api/policy/publish",
                     expected=v1, actual=body.get("archived_version_id"))

        # ── Step 5: summary now shows 3500 — NO stale 3000 ───────────────────
        r = self.client.get(f"/api/policy/summary?company_id={company_id}")
        summary = r.json()
        new_cap = self._housing_cap_from_summary(summary)
        self._record(step=5, description="summary version_number is now 2",
                     endpoint="GET /api/policy/summary",
                     expected=2, actual=(summary.get("version") or {}).get("version_number"))
        self._record(
            step=5,
            description="summary housing cap == 3500 (no stale data)",
            endpoint="GET /api/policy/summary",
            expected=3500.0,
            actual=new_cap,
            # If the old cap leaked through, surface it explicitly.
            stale_value=3000.0 if new_cap == 3000.0 else new_cap,
        )

        # ── Step 6: active + history reflect the new state ───────────────────
        r = self.client.get(f"/api/policy/active/{company_id}")
        active = r.json()
        self._record(step=6, description="active version is now v2 (no stale)",
                     endpoint="GET /api/policy/active/{company_id}",
                     expected=v2, actual=(active or {}).get("id"),
                     stale_value=v1 if (active or {}).get("id") == v1 else None)

        r = self.client.get(f"/api/policy/versions/{company_id}")
        versions = {v["id"]: v["status"] for v in r.json()}
        self._record(step=6, description="version history: v1 archived",
                     endpoint="GET /api/policy/versions/{company_id}",
                     expected="archived", actual=versions.get(v1))
        self._record(step=6, description="version history: v2 published",
                     endpoint="GET /api/policy/versions/{company_id}",
                     expected="published", actual=versions.get(v2))

        # ── Step 7: expired-policy amber banner (separate company) ───────────
        ctx_b = self._seed_company(name="beta")
        self.current_user = self._hr_user(ctx_b)
        v_expired = self._seed_draft_version(ctx_b, housing_cap=2000.0)
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        self.client.post(
            "/api/policy/publish",
            json={"version_id": v_expired, "effective_date": "2026-01-01",
                  "expiry_date": yesterday, "notes": "Past-expiry policy"},
        )
        r = self.client.get(f"/api/policy/summary?company_id={ctx_b['company_id']}")
        self._record(step=7, description="expired policy surfaces amber 'expired' banner",
                     endpoint="GET /api/policy/summary",
                     expected="expired", actual=r.json().get("status_banner"))

        # ── Final assertion: every propagation check passed ──────────────────
        failures = [c for c in self.checks if not c["passed"]]
        self.assertEqual(
            failures, [],
            msg="Propagation checks failed:\n" + json.dumps(failures, indent=2),
        )


if __name__ == "__main__":
    unittest.main()

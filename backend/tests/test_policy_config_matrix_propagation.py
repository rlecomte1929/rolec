"""
[P3-5b / AIQ-811] Integration test — policy-config *matrix* publish propagation
to the caps/compare + published surfaces.

Sibling of P3-5/AIQ-240. That task proved the legacy publish→summary chain
(``POST /api/policy/publish`` → ``policy_versions`` / ``policy_values``) serves
no stale data. This task adds the equivalent no-stale-data guarantee for the
*second, independent* policy subsystem: the compensation-&-allowance matrix
(``policy_config_matrix_service``, its own draft→published lifecycle, benefit
rows with ``cap_rule_json``) which feeds the cap-comparison endpoint and is NOT
driven by ``POST /api/policy/publish``.

Propagation chain under test
────────────────────────────
    PolicyConfigMatrixService.publish_draft   ← HR publishes a matrix version
      → POST /api/hr/policy-config/caps/compare   ← provider-estimate cap check
      → GET  /api/hr/policy-config/published       ← published matrix surface

Publish goes through the *real* service publish entrypoint
(``publish_draft`` → ``publish_policy_config_version_atomic``); every assertion
goes through an HTTP endpoint, mirroring the P3-5 harness
(``backend/tests/test_policy_propagation.py``).

Scenario
  1. Seed company + HR (profiles + hr_users) + a policy_config.
  2. Publish matrix v1 with ``temporary_living`` cap = EUR 3000.
  3. Assert caps/compare and published both report 3000.
  4. Clone → raise the cap → publish v2 = EUR 3500.
  5. Assert caps/compare and published now report 3500 and NOT the stale 3000;
     published version_number is 2.

A pass/fail report is written to
``<RELOPASS_PROPAGATION_REPORT_DIR or repo_root/results>/matrix_propagation_report_YYYYMMDD.json``.

Self-contained: in-memory SQLite (StaticPool) patched into ``backend.database.db``,
no external services. Runs in well under a second. Belongs in the deterministic
CI job (DATABASE_URL=sqlite there → the matrix DB methods take their SQLite path).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Must be set before backend.main is imported (rate limits + query-counter
# event listener that errors against a patched engine).
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from unittest import mock  # noqa: E402

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

import importlib  # noqa: E402

# backend/conftest.py installs a MagicMock at sys.modules["backend.database"] so
# *unit* tests don't need a DB. The matrix subsystem accesses the DB through
# Database *methods* (not just db.engine), so an engine-patch over a mock isn't
# enough — we need the real Database. Force-load the real module before importing
# backend.main so the routers bind to it; setUp additionally repoints the matrix
# router's db in case it was already imported under the mock (full-suite order).
sys.modules.pop("backend.database", None)
import backend.database as bdb  # noqa: E402  (real module)
sys.modules["backend.database"] = bdb
from backend.main import app  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402
import backend.app.routers.policy_config as _policy_config_router  # noqa: E402

CONFIG_KEY = "compensation_allowance"
BENEFIT_KEY = "temporary_living"  # the matrix cap we mutate across versions


# ─────────────────────────────────────────────────────────────────────────────
# Schema — superset of every column the matrix publish + caps/compare +
# published endpoints read or write. SQLite-typed mirror of the Postgres DDL in
# backend/database.py (_maybe_ensure_compensation_allowance_policy_config) plus
# the company / profiles / hr_users rows the HR company resolver needs.
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE companies (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE profiles (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    full_name  TEXT,
    company_id TEXT,
    role       TEXT NOT NULL DEFAULT 'employee'
);
CREATE TABLE hr_users (
    profile_id TEXT PRIMARY KEY,
    company_id TEXT
);
CREATE TABLE policy_configs (
    id         TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    name       TEXT NOT NULL DEFAULT 'Compensation & Allowance',
    config_key TEXT NOT NULL DEFAULT 'compensation_allowance',
    description TEXT,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, config_key)
);
CREATE TABLE policy_config_versions (
    id               TEXT PRIMARY KEY,
    policy_config_id TEXT NOT NULL,
    version_number   INTEGER NOT NULL,
    status           TEXT NOT NULL DEFAULT 'draft',
    effective_date   TEXT NOT NULL,
    published_at     TEXT,
    created_by       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (policy_config_id, version_number)
);
CREATE TABLE policy_config_benefits (
    id                       TEXT PRIMARY KEY,
    policy_config_version_id TEXT NOT NULL,
    benefit_key       TEXT NOT NULL,
    benefit_label     TEXT NOT NULL,
    category          TEXT NOT NULL,
    covered           INTEGER NOT NULL DEFAULT 0,
    value_type        TEXT NOT NULL DEFAULT 'none',
    amount_value      REAL,
    currency_code     TEXT,
    percentage_value  REAL,
    unit_frequency    TEXT NOT NULL DEFAULT 'one_time',
    cap_rule_json     TEXT NOT NULL DEFAULT '{}',
    notes             TEXT,
    conditions_json   TEXT NOT NULL DEFAULT '{}',
    assignment_types  TEXT NOT NULL DEFAULT '[]',
    family_statuses   TEXT NOT NULL DEFAULT '[]',
    employee_levels   TEXT NOT NULL DEFAULT '[]',
    targeting_signature TEXT NOT NULL DEFAULT 'global',
    is_active         INTEGER NOT NULL DEFAULT 1,
    display_order     INTEGER NOT NULL DEFAULT 0,
    source            TEXT DEFAULT 'seeded',
    auto_generated    INTEGER NOT NULL DEFAULT 1,
    field_confidence  REAL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (policy_config_version_id, benefit_key, targeting_signature)
);
CREATE TABLE policy_config_benefits_audit (
    id                       TEXT PRIMARY KEY,
    benefit_id               TEXT,
    policy_config_version_id TEXT,
    benefit_key              TEXT,
    action                   TEXT NOT NULL,
    old_value                TEXT,
    new_value                TEXT,
    source                   TEXT,
    changed_by               TEXT,
    changed_at               TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE policy_benefit_jurisdiction_overrides (
    id                    TEXT PRIMARY KEY,
    benefit_row_id        TEXT NOT NULL,
    jurisdiction_countries TEXT,
    employee_level        TEXT,
    assignment_type       TEXT,
    amount_value          REAL,
    currency_code         TEXT,
    cap_rule_json         TEXT,
    reimbursement_md      TEXT,
    repayment_md          TEXT,
    display_order         INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


class MatrixPublishPropagationTest(unittest.TestCase):
    """Publish a matrix version → downstream caps/compare + published reflect it, no stale data."""

    def setUp(self) -> None:
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

        self._patchers = [mock.patch.object(bdb.db, "engine", self.engine)]
        # Repoint the matrix router (and its module-level service) at the real,
        # engine-patched db — robust even if the router was imported under the
        # conftest unit-test mock earlier in a full-suite run.
        self._patchers.append(mock.patch.object(_policy_config_router, "db", bdb.db))
        self._patchers.append(
            mock.patch.object(_policy_config_router.policy_config_matrix_svc, "_db", bdb.db)
        )
        for p in self._patchers:
            p.start()

        self.current_user: Dict[str, Any] = {}
        app.dependency_overrides[get_current_user] = lambda: self.current_user

        self.client = TestClient(app, raise_server_exceptions=False)
        self.checks: List[Dict[str, Any]] = []

    def tearDown(self) -> None:
        self._write_report()
        app.dependency_overrides.pop(get_current_user, None)
        for p in reversed(self._patchers):
            p.stop()
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
        path = report_dir / f"matrix_propagation_report_{stamp}.json"
        passed = sum(1 for c in self.checks if c["passed"])
        report = {
            "task": "P3-5b / AIQ-811 — policy-config matrix publish propagation to caps/compare",
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
        print(f"\n[P3-5b] matrix propagation report written → {path}")

    # ── seed helpers ─────────────────────────────────────────────────────────

    def _seed_company_and_hr(self) -> Dict[str, str]:
        company_id = _uuid()
        # Non-UUID HR id on purpose: db.get_profile_record binds a uuid.UUID object
        # (SQLite-incompatible) for uuid-shaped ids but returns None for non-uuid
        # ids, so the HR company resolver falls back to the hr_users lookup below.
        hr_id = "hr-" + uuid.uuid4().hex[:12]
        config_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO companies (id, name) VALUES (:id, :n)"),
                {"id": company_id, "n": "Acme Matrix Co"},
            )
            conn.execute(
                text(
                    "INSERT INTO profiles (id, email, full_name, company_id, role) "
                    "VALUES (:id, :e, :f, :c, 'hr')"
                ),
                {"id": hr_id, "e": "hr@acme-matrix.test", "f": "HR Admin", "c": company_id},
            )
            conn.execute(
                text("INSERT INTO hr_users (profile_id, company_id) VALUES (:p, :c)"),
                {"p": hr_id, "c": company_id},
            )
            conn.execute(
                text(
                    "INSERT INTO policy_configs (id, company_id, name, config_key) "
                    "VALUES (:id, :c, 'Compensation & Allowance', :ck)"
                ),
                {"id": config_id, "c": company_id, "ck": CONFIG_KEY},
            )
        return {"company_id": company_id, "hr_id": hr_id, "config_id": config_id}

    def _seed_draft_with_cap(self, *, config_id: str, version_number: int, cap: float) -> str:
        """Insert a draft matrix version with a single covered, EUR-denominated
        ``temporary_living`` benefit at ``cap`` (global targeting)."""
        vid = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO policy_config_versions "
                    "(id, policy_config_id, version_number, status, effective_date) "
                    "VALUES (:id, :pid, :n, 'draft', '2026-06-01')"
                ),
                {"id": vid, "pid": config_id, "n": version_number},
            )
            conn.execute(
                text(
                    "INSERT INTO policy_config_benefits "
                    "(id, policy_config_version_id, benefit_key, benefit_label, category, "
                    " covered, value_type, amount_value, currency_code, unit_frequency, "
                    " targeting_signature) "
                    "VALUES (:id, :v, :bk, 'Temporary living', 'relocation_assistance', "
                    " 1, 'currency', :amt, 'EUR', 'monthly', 'global')"
                ),
                {"id": _uuid(), "v": vid, "bk": BENEFIT_KEY, "amt": cap},
            )
        return vid

    def _hr_user(self, ctx: Dict[str, str]) -> Dict[str, Any]:
        # UserRole.HR.value is "HR" (backend/schemas.py) — require_role + the HR
        # company resolver both compare against the exact (uppercase) value.
        return {"id": ctx["hr_id"], "role": "HR", "company_id": ctx["company_id"], "is_admin": False}

    # ── response extractors ──────────────────────────────────────────────────

    def _published_cap(self, published: Dict[str, Any]) -> Optional[float]:
        for cat in published.get("categories") or []:
            for b in cat.get("benefits") or []:
                if b.get("benefit_key") == BENEFIT_KEY:
                    av = b.get("amount_value")
                    return float(av) if av is not None else None
        return None

    def _compare_cap(self, compare: Dict[str, Any]) -> Optional[float]:
        for r in compare.get("results") or []:
            if r.get("benefit_key") == BENEFIT_KEY:
                ca = r.get("cap_amount")
                return float(ca) if ca is not None else None
        return None

    def _caps_compare(self) -> Dict[str, Any]:
        return self.client.post(
            "/api/hr/policy-config/caps/compare",
            json={"estimates": [{"benefit_key": BENEFIT_KEY, "amount": 2500, "currency": "EUR"}]},
        ).json()

    # ── the scenario ─────────────────────────────────────────────────────────

    def test_matrix_publish_propagates_with_no_stale_data(self) -> None:
        ctx = self._seed_company_and_hr()
        self.current_user = self._hr_user(ctx)
        config_id = ctx["config_id"]

        # ── Step 1: publish matrix v1 with temporary_living cap 3000 ──────────
        self._seed_draft_with_cap(config_id=config_id, version_number=1, cap=3000.0)
        r = self.client.post("/api/hr/policy-config/publish", json={})
        self._record(step=1, description="publish v1 returns 200",
                     endpoint="POST /api/hr/policy-config/publish",
                     expected=200, actual=r.status_code)

        # ── Step 2: caps/compare reflects 3000 ───────────────────────────────
        compare = self._caps_compare()
        self._record(step=2, description="caps/compare cap_amount == 3000 after v1",
                     endpoint="POST /api/hr/policy-config/caps/compare",
                     expected=3000.0, actual=self._compare_cap(compare))

        # ── Step 3: published surface reflects 3000, version 1 ────────────────
        published = self.client.get("/api/hr/policy-config/published").json()
        self._record(step=3, description="published cap == 3000 after v1",
                     endpoint="GET /api/hr/policy-config/published",
                     expected=3000.0, actual=self._published_cap(published))
        self._record(step=3, description="published version_number == 1",
                     endpoint="GET /api/hr/policy-config/published",
                     expected=1, actual=(published.get("version_number")))

        # ── Step 4: seed v2 draft at 3500 → publish ──────────────────────────
        # v1 is now 'published'; the only remaining draft is v2, so publish (no
        # explicit id) resolves to it.
        self._seed_draft_with_cap(config_id=config_id, version_number=2, cap=3500.0)
        r = self.client.post("/api/hr/policy-config/publish", json={})
        self._record(step=4, description="publish v2 returns 200",
                     endpoint="POST /api/hr/policy-config/publish",
                     expected=200, actual=r.status_code)

        # ── Step 5: caps/compare now 3500 — NO stale 3000 ────────────────────
        compare = self._caps_compare()
        new_cap = self._compare_cap(compare)
        self._record(
            step=5,
            description="caps/compare cap_amount == 3500 (no stale data)",
            endpoint="POST /api/hr/policy-config/caps/compare",
            expected=3500.0,
            actual=new_cap,
            stale_value=3000.0 if new_cap == 3000.0 else new_cap,
        )

        # ── Step 6: published now 3500, version 2 — NO stale 3000 ─────────────
        published = self.client.get("/api/hr/policy-config/published").json()
        pub_cap = self._published_cap(published)
        self._record(
            step=6,
            description="published cap == 3500 (no stale data)",
            endpoint="GET /api/hr/policy-config/published",
            expected=3500.0,
            actual=pub_cap,
            stale_value=3000.0 if pub_cap == 3000.0 else pub_cap,
        )
        self._record(step=6, description="published version_number == 2",
                     endpoint="GET /api/hr/policy-config/published",
                     expected=2, actual=(published.get("version_number")))

        failures = [c for c in self.checks if not c["passed"]]
        self.assertEqual(
            failures, [],
            msg="Matrix propagation checks failed:\n" + json.dumps(failures, indent=2),
        )


if __name__ == "__main__":
    unittest.main()

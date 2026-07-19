"""[P0-1] Eager policy resolution + zero-silent-failure contract.

Pins the stage-P0-1 fixes for the test-drive over-cap flow (RUN 001–003 root cause:
`resolved_assignment_policies` stayed EMPTY for test-drive cases because resolution
was lazy and the config-matrix path never persisted):

  1. `create_assignment_with_contact_and_invites` produces a persisted resolved
     policy row IMMEDIATELY, with NO intervening read — resolution is now the 6th
     assignment post-creation hook and the matrix branch persists its snapshot.
  2. The eager hook is idempotent (existing row → no re-resolution).
  3. A resolution EXCEPTION emits ONE structured `policy_resolution_error` ERROR
     (never a silent warning) and never raises into assignment creation.
  4. The test-drive default-policy seed emits a structured
     `test_drive_policy_seed_failed` ERROR on failure — including the silent
     publish-no-op class (no published version after publish) — instead of
     passing silently.
  5. Degraded-state copy: "Policy comparison unavailable" (resolution failed —
     policy UNKNOWN) is distinct from "No policy rule for this category" (a
     business fact asserted only after a SUCCESSFUL resolution).

No live DB: the db layer is a configured MagicMock, mirroring
test_test_drive_provision.py / test_unified_assignment_creation.py.
"""
from __future__ import annotations

import logging
import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import policy_resolution as pr  # noqa: E402
from backend.app.services import unified_assignment_creation as uac  # noqa: E402
from backend.app.services.employee_services_policy_context import (  # noqa: E402
    POLICY_UNAVAILABLE_LABEL,
    build_employee_services_policy_context,
)

ASSIGNMENT_ID = "asg-p01"
CASE_ID = "case-p01"
COMPANY_ID = "company-p01"
CONFIG_VERSION_ID = "cfgv-p01"


def _seeded_matrix_benefit_row() -> dict:
    """One covered currency-cap row, shaped like list_policy_config_benefits output
    (mirrors the host_housing_cap row the test-drive seed publishes)."""
    return {
        "id": "bnf-p01",
        "policy_config_version_id": CONFIG_VERSION_ID,
        "benefit_key": "host_housing_cap",
        "benefit_label": "Host housing cap",
        "category": "compensation_allowances",
        "covered": True,
        "value_type": "currency",
        "amount_value": 3000.0,
        "currency_code": "EUR",
        "percentage_value": None,
        "unit_frequency": "monthly",
        "cap_rule_json": {},
        "notes": None,
        "conditions_json": {},
        "assignment_types": [],
        "family_statuses": [],
        "employee_levels": [],
        "is_active": True,
    }


def _matrix_company_db() -> MagicMock:
    """A db whose only published policy for COMPANY_ID is a config-matrix version
    (the test-drive shape: no legacy company_policies/policy_versions row)."""
    db = MagicMock()
    # -- assignment-creation path --------------------------------------------
    db.resolve_or_create_employee_contact.return_value = "contact-p01"
    db.ensure_pending_assignment_invites.return_value = "invite-token-p01"
    # _link_contact_post_create: no row → early return.
    conn = db.engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = None
    # welcome-message hook: thread already exists → no-op.
    db.list_messages_by_assignment.return_value = [{"id": "msg-1"}]
    # -- eager resolution path -----------------------------------------------
    db.get_resolved_assignment_policy.return_value = None  # no prior row
    db.get_assignment_by_id.return_value = {
        "id": ASSIGNMENT_ID,
        "case_id": CASE_ID,
        "canonical_case_id": None,
        "hr_user_id": "hr-p01",
        "employee_user_id": None,
        "employee_identifier": "emp@probe.test",
    }
    db.get_relocation_case.return_value = {
        "id": CASE_ID,
        "company_id": COMPANY_ID,
        "profile_json": None,
    }
    db.get_employee_profile.return_value = {}
    db.get_hr_company_id.return_value = COMPANY_ID
    db.get_company_policy_with_published_version.return_value = None  # no legacy policy
    db.get_latest_published_policy_config_version.return_value = {
        "id": CONFIG_VERSION_ID,
        "version_number": 1,
        "status": "published",
        "effective_date": "2026-01-01",
        "published_at": "2026-01-01T00:00:00Z",
    }
    db.list_policy_config_benefits.return_value = [_seeded_matrix_benefit_row()]
    db.upsert_resolved_assignment_policy.return_value = "resolved-p01"
    return db


def _noop_side_hooks():
    """Patch the pre-existing (non-policy) post-creation hooks to no-ops so this
    test pins ONLY the eager-resolution behavior."""
    return (
        patch.object(uac, "ensure_mobility_case_link_for_assignment"),
        patch.object(uac, "ensure_employee_case_person_for_assignment"),
        patch.object(uac, "ensure_passport_case_document_for_assignment"),
    )


# ---------------------------------------------------------------------------
# 1. Eager resolution at creation — NO intervening read
# ---------------------------------------------------------------------------

def test_resolved_row_exists_immediately_after_assignment_creation():
    db = _matrix_company_db()
    p1, p2, p3 = _noop_side_hooks()
    with p1, p2, p3:
        result = uac.create_assignment_with_contact_and_invites(
            db,
            company_id=COMPANY_ID,
            hr_user_id="hr-p01",
            case_id=CASE_ID,
            employee_identifier_raw="emp@probe.test",
            employee_first_name="Pat",
            employee_last_name="Tester",
            employee_user_id=None,
            assignment_status="active",
            request_id="req-p01",
            assignment_id=ASSIGNMENT_ID,
        )

    assert result.assignment_id == ASSIGNMENT_ID
    # The resolved snapshot was PERSISTED during creation itself — the only calls in
    # this test are the creation call; no read endpoint / lazy path ever ran.
    db.upsert_resolved_assignment_policy.assert_called_once()
    kwargs = db.upsert_resolved_assignment_policy.call_args.kwargs
    assert kwargs["assignment_id"] == ASSIGNMENT_ID
    assert kwargs["company_id"] == COMPANY_ID
    # Matrix-sourced rows are discriminated by the policy_id prefix + context source.
    assert str(kwargs["policy_id"]).startswith("policy_config_matrix:")
    assert kwargs["policy_version_id"] == CONFIG_VERSION_ID
    assert kwargs["resolution_context"].get("source") == "policy_config_matrix"
    benefit_keys = {b.get("benefit_key") for b in kwargs["benefits"]}
    assert "host_housing_cap" in benefit_keys


def test_eager_hook_is_idempotent_when_row_already_exists():
    db = _matrix_company_db()
    db.get_resolved_assignment_policy.return_value = {"id": "resolved-existing"}
    out = pr.ensure_resolved_policy_for_assignment(db, ASSIGNMENT_ID, request_id="req-p01")
    assert out == {"id": "resolved-existing"}
    db.upsert_resolved_assignment_policy.assert_not_called()


def test_no_policy_is_not_an_error(caplog):
    db = _matrix_company_db()
    db.get_latest_published_policy_config_version.return_value = None  # no matrix either
    with caplog.at_level(logging.INFO, logger=pr.__name__):
        out = pr.ensure_resolved_policy_for_assignment(db, ASSIGNMENT_ID)
    assert out is None
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == [], "a company without a policy is a business state, not an error"


# ---------------------------------------------------------------------------
# 2. Zero silent failures — structured errors
# ---------------------------------------------------------------------------

def test_resolution_exception_emits_structured_error_and_never_raises(caplog):
    db = _matrix_company_db()
    with patch.object(pr, "resolve_policy_for_assignment", side_effect=RuntimeError("boom")):
        with caplog.at_level(logging.ERROR, logger=pr.__name__):
            out = pr.ensure_resolved_policy_for_assignment(db, ASSIGNMENT_ID, request_id="req-p01")
    assert out is None  # never raises into the creation hooks
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    msg = errors[0].getMessage()
    assert pr.POLICY_RESOLUTION_ERROR_EVENT in msg
    assert ASSIGNMENT_ID in msg
    assert "RuntimeError" in msg


def test_matrix_persistence_failure_is_structured_not_silent(caplog):
    db = _matrix_company_db()
    db.upsert_resolved_assignment_policy.side_effect = RuntimeError("fk violation")
    with caplog.at_level(logging.ERROR, logger=pr.__name__):
        resolved = pr.ensure_resolved_policy_for_assignment(db, ASSIGNMENT_ID)
    # The in-memory resolution still succeeds (persistence is a cache write) …
    assert resolved is not None and resolved.get("has_policy") is True
    # … but the failed write emitted a structured ERROR, not a swallowed warning.
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any(pr.POLICY_PERSISTENCE_ERROR_EVENT in m for m in errors)


def test_seed_failure_emits_structured_error(caplog):
    from backend.app.routers import test_drive as td

    with patch.object(td, "db", MagicMock()), \
            patch(
                "backend.app.services.policy_config_matrix_service.PolicyConfigMatrixService",
                side_effect=RuntimeError("publish exploded"),
            ):
        with caplog.at_level(logging.ERROR, logger=td.__name__):
            ok = td._seed_default_published_policy("company-1", "hr-1")
    assert ok is False  # never raises (provisioning must survive) …
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any(td.TEST_DRIVE_POLICY_SEED_FAILED_EVENT in m for m in errors)
    assert any("RuntimeError" in m for m in errors)


def test_seed_publish_noop_fails_postcondition_with_structured_error(caplog):
    """The silent-failure class: ensure_draft/publish_draft 'succeed' but no
    published version exists afterwards. The post-condition must catch it."""
    from backend.app.routers import test_drive as td

    db = MagicMock()
    db.get_latest_published_policy_config_version.return_value = None
    with patch.object(td, "db", db), \
            patch("backend.app.services.policy_config_matrix_service.PolicyConfigMatrixService"):
        with caplog.at_level(logging.ERROR, logger=td.__name__):
            ok = td._seed_default_published_policy("company-1", "hr-1")
    assert ok is False
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any(
        td.TEST_DRIVE_POLICY_SEED_FAILED_EVENT in m and "no_published_version_after_publish" in m
        for m in errors
    )


def test_seed_success_returns_true(caplog):
    from backend.app.routers import test_drive as td

    with patch.object(td, "db", MagicMock()), \
            patch("backend.app.services.policy_config_matrix_service.PolicyConfigMatrixService"):
        with caplog.at_level(logging.ERROR, logger=td.__name__):
            ok = td._seed_default_published_policy("company-1", "hr-1")
    assert ok is True
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


# ---------------------------------------------------------------------------
# 3. Degraded state is distinct copy from "No policy rule for this category"
# ---------------------------------------------------------------------------

def test_policy_unavailable_copy_is_distinct_from_no_benefit_rule():
    degraded = build_employee_services_policy_context(
        {"has_policy": False, "policy_unavailable": True, "comparison_available": False}
    )
    entry = degraded["categories"]["living_areas"]
    assert degraded["policy_unavailable"] is True
    assert entry["determination"] == "policy_unavailable"
    assert entry["primary_label"] == POLICY_UNAVAILABLE_LABEL
    assert entry["primary_label"] != "No policy rule for this category"

    # A SUCCESSFUL resolution with a genuinely missing rule keeps asserting the
    # business fact — the two states must never share copy.
    resolved_without_rule = build_employee_services_policy_context(
        {"has_policy": True, "comparison_available": True, "benefits": []}
    )
    no_rule_entry = resolved_without_rule["categories"]["living_areas"]
    assert no_rule_entry["determination"] == "no_benefit_rule"
    assert no_rule_entry["primary_label"] == "No policy rule for this category"


def test_electricity_stays_out_of_scope_in_degraded_state():
    degraded = build_employee_services_policy_context(
        {"has_policy": False, "policy_unavailable": True}
    )
    assert degraded["categories"]["electricity"]["determination"] == "out_of_scope"


# ---------------------------------------------------------------------------
# 4. Persisted matrix rows keep the comparison path working (cache-hit branch)
# ---------------------------------------------------------------------------

def test_comparison_uses_persisted_matrix_row_without_readiness_regression():
    from backend.app.services.policy_service_comparison import compute_policy_service_comparison

    db = _matrix_company_db()
    # Cache hit: the eager hook already persisted this matrix-sourced row.
    db.get_resolved_assignment_policy.return_value = {
        "id": "resolved-p01",
        "assignment_id": ASSIGNMENT_ID,
        "policy_id": f"policy_config_matrix:{CONFIG_VERSION_ID}",
        "policy_version_id": CONFIG_VERSION_ID,
        "resolution_context_json": {"source": "policy_config_matrix"},
        "resolved_at": "2026-01-01T00:00:00Z",
    }
    db.list_resolved_policy_benefits.return_value = [
        {
            "benefit_key": "host_housing_cap",
            "included": True,
            "min_value": None,
            "standard_value": 3000.0,
            "max_value": 3000.0,
            "currency": "EUR",
            "amount_unit": None,
            "frequency": "monthly",
            "approval_required": False,
            "evidence_required_json": [],
            "exclusions_json": [],
            "condition_summary": None,
        }
    ]
    # Employee selected housing above the 3000 EUR cap.
    db.list_case_services.return_value = [
        {"category": "living_areas", "service_key": "housing", "selected": True, "estimated_cost": 4000.0, "currency": "EUR"}
    ]
    db.list_case_service_answers.return_value = []
    db.coalesce_case_lookup_id.return_value = CASE_ID

    out = compute_policy_service_comparison(
        db,
        ASSIGNMENT_ID,
        assignment={"id": ASSIGNMENT_ID, "case_id": CASE_ID, "canonical_case_id": None},
        employee_gate=True,
    )
    # The persisted matrix row must NOT be pushed through the policy_version-based
    # readiness evaluator (which would suppress the comparison): a numeric cap on
    # file ⇒ comparison stays available and the over-cap status surfaces.
    assert out["comparison_available"] is True
    by_cat = {c["service_category"]: c for c in out["comparisons"]}
    housing = by_cat.get("living_areas")
    assert housing is not None
    assert housing["policy_status"] in ("capped", "approval_required")
    assert housing["variance_json"].get("over_by") == 1000.0

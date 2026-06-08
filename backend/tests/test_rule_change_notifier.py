"""AIQ-797 / P1-08d-FU — unit-test notify_superseded_rules' real logic.

Closes the coverage gap where the notifier was only exercised via a MOCKED
endpoint test (test_roadmap_audit.TestNotifierTrigger). Here the REAL
notify_superseded_rules orchestration runs — idempotency branching, recipient
resolution (real _recipients_for_case), per-recipient notification + counts +
metadata. Only the Postgres-specific I/O is stubbed via the _fetch_affected_pairs
seam (the affected query) + the mocked db.* methods (conftest mocks backend.database).

Coverage boundary (documented per the task's seam allowance): the raw _AFFECTED_SQL
string is Postgres-specific (rce.* schema, ANY(), CURRENT_DATE, JSON ->>), so it
cannot execute on the SQLite/mocked test DB. Its *structure* is guarded by
test_affected_sql_shape; executing it (assertion "non-citing case gets none" at the
SQL level) requires a Postgres harness — out of scope for this hermetic unit test.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.app.services.rule_change_notifier as rcn


def _pair(case_id="c1", old="V1", new="V2", rule_id="R1", label="v1.0"):
    return {
        "case_id": case_id,
        "old_rule_version_id": old,
        "new_rule_version_id": new,
        "rule_id": rule_id,
        "version_label": label,
    }


def test_since_defaults_to_24h_window():
    captured = {}

    def fake_fetch(since):
        captured["since"] = since
        return []

    with patch.object(rcn, "_fetch_affected_pairs", side_effect=fake_fetch):
        rcn.notify_superseded_rules()  # since=None
    delta = datetime.utcnow() - captured["since"]
    assert timedelta(hours=23, minutes=55) < delta < timedelta(hours=24, minutes=5)


def test_affected_case_notifies_each_recipient_with_metadata():
    with patch.object(rcn, "_fetch_affected_pairs", return_value=[_pair()]), \
        patch.object(rcn, "_already_notified", return_value=False), \
        patch.object(rcn.db, "get_relocation_case",
                     return_value={"hr_user_id": "hr1", "employee_id": "emp1"}), \
        patch.object(rcn.db, "create_notification_with_preferences") as create:
        out = rcn.notify_superseded_rules(since=datetime.utcnow() - timedelta(hours=1))

    assert out["affected_pairs"] == 1
    assert out["notifications_created"] == 2  # hr + employee
    assert create.call_count == 2
    kw = create.call_args_list[0].kwargs
    assert kw["type_"] == "rule_updated"
    assert kw["case_id"] == "c1"
    md = kw["metadata"]
    assert md["old_rule_version_id"] == "V1"
    assert md["new_rule_version_id"] == "V2"
    assert md["rule_id"] == "R1"


def test_idempotent_rerun_creates_no_duplicate():
    with patch.object(rcn, "_fetch_affected_pairs", return_value=[_pair()]), \
        patch.object(rcn, "_already_notified", return_value=True), \
        patch.object(rcn.db, "create_notification_with_preferences") as create:
        out = rcn.notify_superseded_rules(since=datetime.utcnow() - timedelta(hours=1))

    assert out["skipped_idempotent"] == 1
    assert out["notifications_created"] == 0
    create.assert_not_called()


def test_case_with_no_recipients_is_skipped():
    with patch.object(rcn, "_fetch_affected_pairs", return_value=[_pair()]), \
        patch.object(rcn, "_already_notified", return_value=False), \
        patch.object(rcn.db, "get_relocation_case", return_value=None), \
        patch.object(rcn.db, "create_notification_with_preferences") as create:
        out = rcn.notify_superseded_rules(since=datetime.utcnow() - timedelta(hours=1))

    assert out["skipped_no_recipient"] == 1
    assert out["notifications_created"] == 0
    create.assert_not_called()


def test_recipients_deduped_when_hr_equals_employee():
    # Drives the REAL _recipients_for_case dedup/falsy-drop logic.
    with patch.object(rcn, "_fetch_affected_pairs", return_value=[_pair()]), \
        patch.object(rcn, "_already_notified", return_value=False), \
        patch.object(rcn.db, "get_relocation_case",
                     return_value={"hr_user_id": "same", "employee_id": "same"}), \
        patch.object(rcn.db, "create_notification_with_preferences") as create:
        out = rcn.notify_superseded_rules(since=datetime.utcnow() - timedelta(hours=1))

    assert out["notifications_created"] == 1  # deduped to a single recipient


def test_one_bad_recipient_does_not_abort_the_run():
    # create raises for the first recipient; the run must continue + count the rest.
    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("notify backend down")

    with patch.object(rcn, "_fetch_affected_pairs", return_value=[_pair()]), \
        patch.object(rcn, "_already_notified", return_value=False), \
        patch.object(rcn.db, "get_relocation_case",
                     return_value={"hr_user_id": "hr1", "employee_id": "emp1"}), \
        patch.object(rcn.db, "create_notification_with_preferences", side_effect=flaky):
        out = rcn.notify_superseded_rules(since=datetime.utcnow() - timedelta(hours=1))

    assert out["notifications_created"] == 1  # second recipient still notified


def test_affected_sql_shape_regression_guard():
    # The raw query can't run on SQLite; guard its structure so a dropped filter
    # (the regression the task flags) fails CI.
    sql = rcn._AFFECTED_SQL
    for token in ("rce.rule_versions", "rce.roadmap_audit_log", "rce.cases",
                  "superseded_by", "effective_to", "updated_at >= :since", "c.status"):
        assert token in sql, f"missing filter/join: {token}"

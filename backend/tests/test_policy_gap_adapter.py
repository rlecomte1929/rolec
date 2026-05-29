"""Tests for the policy-gap detector I/O layer (C2-06-FOLLOWUP).

Two modes (mirrors test_relopass_case_engine_schema.py):

  * Unit mode (always runs): exercises the reconciliation + projection logic
    with a recording fake Connection — no DB. Covers the dedup-key diff,
    insert/clear, idempotency, and the event-dispatch wiring.
  * Live mode (skipped unless RELOPASS_TEST_DB_URL is set): seeds a Priya
    Sharma fixture into rce.* and runs the full detect_and_persist → endpoint
    query loop, asserting gaps appear then clear as artefacts are added.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.relopass.policy_evidence import Gap, Subject  # noqa: E402
from backend.app.services import policy_gap_detector_adapter as adapter  # noqa: E402
from backend.app.services import policy_gap_events as events  # noqa: E402


def _gap(case_id, clause_id, gap_type="MISSING_BENEFIT_DELIVERY", fm_id=None, kind="CASE"):
    return Gap(
        case_id=case_id,
        policy_clause_id=clause_id,
        clause_type="HOUSING_BENEFIT",
        subject=Subject(kind=kind, family_member_id=fm_id),
        gap_type=gap_type,
        suggested_action="do the thing",
        evidence_payload=None,
        citation={"source_page": 2, "bbox": [1, 2, 3, 4]},
    )


class _RecordingConn:
    """Minimal SQLAlchemy-Connection stand-in: records executed statements."""

    def __init__(self):
        self.executed = []

    def execute(self, clause, params=None):
        self.executed.append((str(clause), params or {}))
        return self

    # INSERT/UPDATE in _persist_diff don't read results.
    def mappings(self):
        return self

    def all(self):
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


class HelperTests(unittest.TestCase):
    def test_norm_key_case_subject(self):
        cid, clause = uuid.uuid4(), uuid.uuid4()
        self.assertEqual(
            adapter._norm_key(cid, clause, "MISSING_BENEFIT_DELIVERY", None),
            f"{cid}|{clause}|MISSING_BENEFIT_DELIVERY|CASE",
        )

    def test_norm_key_family_subject(self):
        cid, clause, fm = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.assertEqual(
            adapter._norm_key(cid, clause, "BELOW_ENTITLEMENT", fm),
            f"{cid}|{clause}|BELOW_ENTITLEMENT|{fm}",
        )

    def test_display_name_prefers_display_name(self):
        self.assertEqual(adapter._display_name({"display_name": "Priya Sharma"}), "Priya Sharma")

    def test_display_name_builds_from_parts(self):
        self.assertEqual(
            adapter._display_name({"given_names": ["Priya"], "normalized_surname": "SHARMA"}),
            "Priya SHARMA",
        )

    def test_display_name_none(self):
        self.assertIsNone(adapter._display_name(None))

    def test_as_float(self):
        self.assertEqual(adapter._as_float(2500), 2500.0)
        self.assertIsNone(adapter._as_float(None))


# ─────────────────────────────────────────────────────────────────────────────
# Reconciliation diff
# ─────────────────────────────────────────────────────────────────────────────


class PersistDiffTests(unittest.TestCase):
    def test_inserts_all_when_no_existing(self):
        cid = uuid.uuid4()
        detected = (_gap(cid, uuid.uuid4()), _gap(cid, uuid.uuid4()))
        conn = _RecordingConn()
        diff = adapter._persist_diff(cid, detected, {}, conn)
        self.assertEqual(len(diff.inserted), 2)
        self.assertEqual(diff.unchanged, 0)
        self.assertTrue(all("INSERT INTO rce.policy_gaps" in s for s, _ in conn.executed))

    def test_clears_resolved(self):
        cid = uuid.uuid4()
        clause = uuid.uuid4()
        existing = {
            adapter._norm_key(cid, clause, "MISSING_BENEFIT_DELIVERY", None): {
                "gap_id": uuid.uuid4(),
                "policy_clause_id": clause,
                "gap_type": "MISSING_BENEFIT_DELIVERY",
                "family_member_id": None,
            }
        }
        conn = _RecordingConn()
        diff = adapter._persist_diff(cid, (), existing, conn)
        self.assertEqual(len(diff.cleared_gap_ids), 1)
        self.assertEqual(len(diff.inserted), 0)
        self.assertTrue(any("UPDATE rce.policy_gaps" in s for s, _ in conn.executed))

    def test_idempotent_no_writes_when_unchanged(self):
        cid = uuid.uuid4()
        clause = uuid.uuid4()
        detected = (_gap(cid, clause),)
        existing = {
            adapter._norm_key(cid, clause, "MISSING_BENEFIT_DELIVERY", None): {
                "gap_id": uuid.uuid4(),
                "policy_clause_id": clause,
                "gap_type": "MISSING_BENEFIT_DELIVERY",
                "family_member_id": None,
            }
        }
        conn = _RecordingConn()
        diff = adapter._persist_diff(cid, detected, existing, conn)
        self.assertEqual(diff.unchanged, 1)
        self.assertEqual(len(diff.inserted), 0)
        self.assertEqual(len(diff.cleared_gap_ids), 0)
        self.assertEqual(conn.executed, [])  # zero schema writes

    def test_insert_then_clear_mixed(self):
        cid = uuid.uuid4()
        kept_clause = uuid.uuid4()
        new_clause = uuid.uuid4()
        detected = (_gap(cid, kept_clause), _gap(cid, new_clause))
        existing = {
            adapter._norm_key(cid, kept_clause, "MISSING_BENEFIT_DELIVERY", None): {
                "gap_id": uuid.uuid4(),
                "policy_clause_id": kept_clause,
                "gap_type": "MISSING_BENEFIT_DELIVERY",
                "family_member_id": None,
            },
            adapter._norm_key(cid, uuid.uuid4(), "MISSING_BENEFIT_DELIVERY", None): {
                "gap_id": uuid.uuid4(),
                "policy_clause_id": uuid.uuid4(),
                "gap_type": "MISSING_BENEFIT_DELIVERY",
                "family_member_id": None,
            },
        }
        conn = _RecordingConn()
        diff = adapter._persist_diff(cid, detected, existing, conn)
        self.assertEqual(len(diff.inserted), 1)      # new_clause
        self.assertEqual(diff.unchanged, 1)          # kept_clause
        self.assertEqual(len(diff.cleared_gap_ids), 1)  # the stale existing


# ─────────────────────────────────────────────────────────────────────────────
# Event dispatch
# ─────────────────────────────────────────────────────────────────────────────


class EventDispatchTests(unittest.TestCase):
    def setUp(self):
        events.enable_event_log()

    def tearDown(self):
        events.reset_subscribers()

    def test_four_events_registered(self):
        for ev in events.GAP_REDETECTION_EVENTS:
            self.assertIn(ev, events._subscribers)
            self.assertTrue(events._subscribers[ev])

    def test_emit_invokes_handler_and_logs(self):
        events.reset_subscribers()
        events.enable_event_log()
        seen = []
        events.subscribe(events.EVENT_DOCUMENT_PARSED, lambda cid: seen.append(cid))
        cid = uuid.uuid4()
        events.emit(events.EVENT_DOCUMENT_PARSED, cid)
        self.assertEqual(seen, [cid])
        self.assertIn((events.EVENT_DOCUMENT_PARSED, str(cid)), events.drain_event_log())

    def test_handler_error_isolated(self):
        events.reset_subscribers()
        ok = []
        events.subscribe(events.EVENT_FAMILY_MEMBER_ADDED, lambda cid: (_ for _ in ()).throw(RuntimeError("boom")))
        events.subscribe(events.EVENT_FAMILY_MEMBER_ADDED, lambda cid: ok.append(cid))
        cid = uuid.uuid4()
        events.emit(events.EVENT_FAMILY_MEMBER_ADDED, cid)  # must not raise
        self.assertEqual(ok, [cid])


# ─────────────────────────────────────────────────────────────────────────────
# Live mode — full loop on a seeded Priya Sharma fixture
# ─────────────────────────────────────────────────────────────────────────────


@unittest.skipUnless(
    os.environ.get("RELOPASS_TEST_DB_URL"),
    "Live DB test: set RELOPASS_TEST_DB_URL to a Postgres with the rce schema.",
)
class LivePriyaSharmaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine, text

        cls.text = staticmethod(text)
        cls.engine = create_engine(os.environ["RELOPASS_TEST_DB_URL"])
        cls.case_id = uuid.uuid4()
        cls.employer_id = uuid.uuid4()
        cls.employee_id = uuid.uuid4()
        cls.canonical_id = uuid.uuid4()
        cls.hr_policy_id = uuid.uuid4()
        cls._seed()

    @classmethod
    def _seed(cls):
        t = cls.text
        with cls.engine.begin() as c:
            c.execute(t("INSERT INTO rce.employers (employer_id, legal_name) VALUES (:e, 'Acme GmbH') ON CONFLICT DO NOTHING"), {"e": str(cls.employer_id)})
            c.execute(t("INSERT INTO rce.canonical_entities (canonical_entity_id, entity_type, canonical_form) VALUES (:id, 'PERSON', CAST(:f AS jsonb))"), {"id": str(cls.canonical_id), "f": '{"display_name": "Priya Sharma"}'})
            c.execute(t("INSERT INTO rce.employees (employee_id, canonical_entity_id) VALUES (:id, :ce)"), {"id": str(cls.employee_id), "ce": str(cls.canonical_id)})
            c.execute(t("INSERT INTO rce.cases (case_id, employer_id, primary_employee_id, status) VALUES (:c, :e, :emp, 'ACTIVE')"), {"c": str(cls.case_id), "e": str(cls.employer_id), "emp": str(cls.employee_id)})
            c.execute(t("INSERT INTO rce.hr_policies (hr_policy_id, employer_id, version_label, source, effective_from) VALUES (:p, :e, 'v1', 'GUIDED_EDITOR', now() - interval '1 day')"), {"p": str(cls.hr_policy_id), "e": str(cls.employer_id)})
            for ctype, params in (
                ("LANGUAGE_TRAINING", '{"for_employee_bool": true, "hours": 60, "target_cefr_level": "B1"}'),
                ("HOUSING_BENEFIT", '{"temporary_or_permanent": "TEMPORARY"}'),
                ("IMMIGRATION_SUPPORT", '{}'),
            ):
                c.execute(t("INSERT INTO rce.policy_clauses (policy_clause_id, hr_policy_id, clause_type, parameters_json) VALUES (:id, :p, :ct, CAST(:pj AS jsonb))"), {"id": str(uuid.uuid4()), "p": str(cls.hr_policy_id), "ct": ctype, "pj": params})

    @classmethod
    def tearDownClass(cls):
        t = cls.text
        with cls.engine.begin() as c:
            c.execute(t("DELETE FROM rce.policy_gaps WHERE case_id = :c"), {"c": str(cls.case_id)})
            c.execute(t("DELETE FROM rce.case_artefacts WHERE case_id = :c"), {"c": str(cls.case_id)})
            c.execute(t("DELETE FROM rce.policy_clauses WHERE hr_policy_id = :p"), {"p": str(cls.hr_policy_id)})
            c.execute(t("DELETE FROM rce.hr_policies WHERE hr_policy_id = :p"), {"p": str(cls.hr_policy_id)})
            c.execute(t("DELETE FROM rce.cases WHERE case_id = :c"), {"c": str(cls.case_id)})
            c.execute(t("DELETE FROM rce.employees WHERE employee_id = :e"), {"e": str(cls.employee_id)})
            c.execute(t("DELETE FROM rce.canonical_entities WHERE canonical_entity_id = :id"), {"id": str(cls.canonical_id)})
            c.execute(t("DELETE FROM rce.employers WHERE employer_id = :e"), {"e": str(cls.employer_id)})

    def _open_gap_count(self):
        with self.engine.begin() as c:
            return c.execute(
                self.text("SELECT count(*) FROM rce.policy_gaps WHERE case_id = :c AND cleared_at IS NULL"),
                {"c": str(self.case_id)},
            ).scalar_one()

    def test_full_loop(self):
        with self.engine.begin() as conn:
            diff = adapter.detect_and_persist(self.case_id, conn)
        self.assertEqual(len(diff.inserted), 3)
        self.assertEqual(self._open_gap_count(), 3)

        # Idempotent second run — zero writes.
        with self.engine.begin() as conn:
            diff2 = adapter.detect_and_persist(self.case_id, conn)
        self.assertFalse(diff2.wrote_anything)
        self.assertEqual(self._open_gap_count(), 3)

        # Add a sufficient language_training_booking → that gap clears.
        with self.engine.begin() as c:
            c.execute(
                self.text(
                    "INSERT INTO rce.case_artefacts (case_id, kind, subject_kind, magnitude, unit) "
                    "VALUES (:c, 'language_training_booking', 'EMPLOYEE', 60, 'hours')"
                ),
                {"c": str(self.case_id)},
            )
        with self.engine.begin() as conn:
            diff3 = adapter.detect_and_persist(self.case_id, conn)
        self.assertEqual(len(diff3.cleared_gap_ids), 1)
        self.assertEqual(self._open_gap_count(), 2)


if __name__ == "__main__":
    unittest.main()

"""AIQ-685 / P1-07b — unit tests for the outcome_extractor service.

Self-contained: builds an in-memory SQLite session and creates only the two
tables the service touches (wizard_cases + case_outcomes), so it does not depend
on PG-specific columns elsewhere in app/models.py.
"""

import json
import os
import re
import unittest
from dataclasses import fields as dataclass_fields
from datetime import datetime

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.services import outcome_extractor as oe  # noqa: E402

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ISO2_RE = re.compile(r"^[A-Z]{2}$")
_VALID_OUTCOMES = {"APPROVED", "REJECTED", "WITHDRAWN", "PENDING"}


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    # Only the tables the service reads/writes — avoids PG-only columns elsewhere.
    models.Case.__table__.create(bind=engine)
    models.CaseOutcome.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


def _add_case(db, case_id="case-1", *, status="approved", origin="FRA", dest="NOR",
              purpose="long_stay_visa", flags=None, draft=None):
    case = models.Case(
        id=case_id,
        draft_json=json.dumps(draft or {}),
        flags_json=json.dumps(flags or {}),
        status=status,
        origin_country=origin,
        dest_country=dest,
        purpose=purpose,
    )
    db.add(case)
    db.commit()
    return case


def _string_values(data: oe.CaseOutcomeData):
    out = []
    for f in dataclass_fields(data):
        v = getattr(data, f.name)
        if isinstance(v, str):
            out.append(v)
    return out


class OutcomeExtractorTests(unittest.TestCase):
    def setUp(self):
        self.db = _make_session()
        # Default: deny the env-flag gate so consent must be explicit.
        os.environ.pop("OUTCOME_EXTRACTION_ENABLED", None)

    def tearDown(self):
        self.db.close()
        os.environ.pop("OUTCOME_EXTRACTION_ENABLED", None)

    # 1 — primary criterion: no source-case PII in any output string column.
    def test_no_pii_in_output(self):
        pii = {
            "email": "john.smith@example.com",
            "phone": "+33612345678",
            "iban": "FR7630001007941234567890185",
            "passport": "AB1234567",
        }
        blob = f"Relocation for John Smith {pii['email']} {pii['phone']} IBAN {pii['iban']} passport {pii['passport']}"
        _add_case(
            self.db, status="rejected", purpose=blob,
            flags={"pathway_type": blob, "rejection_reason_code": blob},
        )
        data = oe.extract_outcome_from_case(self.db, "case-1")
        haystack = " ".join(_string_values(data))
        for label, secret in pii.items():
            self.assertNotIn(secret, haystack, f"{label} leaked into outcome output")

    # 2 — idempotency: one row per case, second call updates not duplicates.
    def test_idempotent_one_row_per_case(self):
        _add_case(self.db, status="approved")
        oe.extract_and_persist(self.db, "case-1", consent_granted=True)
        oe.extract_and_persist(self.db, "case-1", consent_granted=True)
        self.assertEqual(self.db.query(models.CaseOutcome).count(), 1)

    # 3 — consent gate.
    def test_consent_gate(self):
        _add_case(self.db, status="approved")
        # denied explicitly
        self.assertIsNone(oe.extract_and_persist(self.db, "case-1", consent_granted=False))
        self.assertEqual(self.db.query(models.CaseOutcome).count(), 0)
        # denied by default (no users column, env flag off → fail-closed)
        self.assertIsNone(oe.extract_and_persist(self.db, "case-1"))
        self.assertEqual(self.db.query(models.CaseOutcome).count(), 0)
        # allowed via env flag
        os.environ["OUTCOME_EXTRACTION_ENABLED"] = "1"
        self.assertIsNotNone(oe.extract_and_persist(self.db, "case-1"))
        self.assertEqual(self.db.query(models.CaseOutcome).count(), 1)

    # 4 — constraint conformance (Python-level; DB CHECKs validated separately).
    def test_constraint_conformance(self):
        _add_case(self.db, status="approved", origin="FRA", dest="NOR")
        data = oe.extract_outcome_from_case(self.db, "case-1")
        self.assertIn(data.outcome, _VALID_OUTCOMES)
        self.assertTrue(_HASH_RE.match(data.case_ref_hash))
        for code in (data.origin_country_code, data.dest_country_code):
            self.assertTrue(code is None or _ISO2_RE.match(code))
        # rejection_reason_code only when REJECTED
        self.assertIsNone(data.rejection_reason_code)
        if data.submitted_at and data.decided_at:
            self.assertGreaterEqual(data.decided_at, data.submitted_at)

    def test_rejection_reason_only_when_rejected(self):
        _add_case(self.db, status="approved", flags={"rejection_reason_code": "DOC_MISSING"})
        approved = oe.extract_outcome_from_case(self.db, "case-1")
        self.assertIsNone(approved.rejection_reason_code)

        _add_case(self.db, case_id="case-2", status="rejected", flags={"rejection_reason_code": "DOC_MISSING"})
        rejected = oe.extract_outcome_from_case(self.db, "case-2")
        self.assertEqual(rejected.outcome, "REJECTED")
        self.assertEqual(rejected.rejection_reason_code, "DOC_MISSING")

    # 5 — status → outcome mapping.
    def test_outcome_mapping(self):
        cases = {
            "approved": "APPROVED", "rejected": "REJECTED", "withdrawn": "WITHDRAWN",
            "cancelled": "WITHDRAWN", "closed": "WITHDRAWN",
            "submitted": "PENDING", "created": "PENDING", "weird": "PENDING",
        }
        for i, (status, expected) in enumerate(cases.items()):
            _add_case(self.db, case_id=f"c-{i}", status=status)
            data = oe.extract_outcome_from_case(self.db, f"c-{i}")
            self.assertEqual(data.outcome, expected, f"{status} → {expected}")

    # 6 — processing time + country normalization.
    def test_processing_time_and_country_codes(self):
        _add_case(
            self.db, status="approved", origin="France", dest="NO",
            flags={"submitted_at": "2026-01-01T00:00:00", "decided_at": "2026-01-11T00:00:00"},
        )
        data = oe.extract_outcome_from_case(self.db, "case-1")
        self.assertEqual(data.origin_country_code, "FR")  # name → ISO2
        self.assertEqual(data.dest_country_code, "NO")     # already ISO2
        self.assertEqual(data.processing_time_days_actual, 10)

    def test_decided_before_submitted_is_dropped(self):
        _add_case(
            self.db, status="approved",
            flags={"submitted_at": "2026-02-10T00:00:00", "decided_at": "2026-01-01T00:00:00"},
        )
        data = oe.extract_outcome_from_case(self.db, "case-1")
        self.assertIsNone(data.decided_at)  # would violate decided_at >= submitted_at
        self.assertIsNone(data.processing_time_days_actual)

    def test_missing_case_raises(self):
        with self.assertRaises(ValueError):
            oe.extract_outcome_from_case(self.db, "nope")


if __name__ == "__main__":
    unittest.main()

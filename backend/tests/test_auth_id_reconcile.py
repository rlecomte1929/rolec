"""
AUTH-ID-1 (AIQ-780): legacy ReloPass-session id ↔ Supabase UUID reconciliation.

ReloPass's hybrid auth model yields a non-UUID text ``id`` for legacy/seed
session accounts, while immigration/case tables key on uuid columns. Binding
the text id to such a column makes Postgres raise ``invalid input syntax for
type uuid`` (the root cause behind the #269 dossier and #279 immigration-status
500s).

These tests pin the fix:
  - the auth boundary resolves a canonical ``auth_uuid`` (UUID pass-through;
    legacy id bridged to ``profiles.id`` by email; ``None`` when unmappable);
  - the immigration status handler binds that ``auth_uuid`` (a real UUID), not
    the raw legacy text id, to the uuid-typed query parameter.

Deterministic: the db layer is mocked, no network / DB.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app import auth_deps  # noqa: E402
from backend.app.routers import immigration_status  # noqa: E402

_UUID = "11111111-1111-1111-1111-111111111111"


class ResolveAuthUuidTests(unittest.TestCase):
    def test_uuid_native_id_passes_through(self):
        # A Supabase-native account already has a UUID id — no mapping needed.
        with mock.patch.object(auth_deps.db, "get_profile_by_email") as by_email:
            result = auth_deps._resolve_auth_uuid({"id": _UUID, "email": "u@x.com"})
        self.assertEqual(result, _UUID)
        by_email.assert_not_called()  # no extra round-trip for UUID users

    def test_legacy_text_id_resolves_via_email(self):
        with mock.patch.object(
            auth_deps.db, "get_profile_by_email", return_value={"id": _UUID}
        ) as by_email:
            result = auth_deps._resolve_auth_uuid(
                {"id": "seed-emp-testingapril", "email": "Seed@X.com"}
            )
        self.assertEqual(result, _UUID)
        by_email.assert_called_once_with("seed@x.com")  # normalized before lookup

    def test_legacy_id_with_no_matching_profile_is_none(self):
        with mock.patch.object(auth_deps.db, "get_profile_by_email", return_value=None):
            result = auth_deps._resolve_auth_uuid(
                {"id": "seed-emp-testingapril", "email": "seed@x.com"}
            )
        self.assertIsNone(result)

    def test_legacy_id_no_email_is_none(self):
        with mock.patch.object(auth_deps.db, "get_profile_by_email") as by_email:
            result = auth_deps._resolve_auth_uuid({"id": "seed-emp-testingapril"})
        self.assertIsNone(result)
        by_email.assert_not_called()

    def test_profile_id_not_a_uuid_is_none(self):
        # Defensive: a malformed profiles.id must not propagate a non-UUID.
        with mock.patch.object(
            auth_deps.db, "get_profile_by_email", return_value={"id": "not-a-uuid"}
        ):
            result = auth_deps._resolve_auth_uuid({"id": "legacy", "email": "x@y.com"})
        self.assertIsNone(result)


class ImmigrationStatusBindsAuthUuidTests(unittest.TestCase):
    """The handler must bind the resolved UUID, not the raw legacy id."""

    def test_interview_status_passes_auth_uuid_to_consent(self):
        captured = {}

        def fake_consent(case_id, employee_id):
            captured["consent_employee_id"] = employee_id
            return True

        def fake_session(case_id, employee_id):
            captured["session_employee_id"] = employee_id
            return None  # no session → early friendly return, no DB needed

        with mock.patch.object(immigration_status, "_check_consent", side_effect=fake_consent), \
             mock.patch.object(immigration_status, "_load_session", side_effect=fake_session):
            result = immigration_status.interview_status(
                case_id="case-1",
                current_user={"id": "seed-emp-testingapril", "auth_uuid": _UUID},
            )

        # Bound the UUID, never the legacy text id.
        self.assertEqual(captured["consent_employee_id"], _UUID)
        self.assertEqual(captured["session_employee_id"], _UUID)
        self.assertFalse(result["has_session"])

    def test_unresolved_legacy_user_binds_none_not_text_id(self):
        # auth_uuid is None when unmappable → consent lookup gets None (no match),
        # which is safe (no uuid-cast 500); handler surfaces the consent screen.
        captured = {}

        def fake_consent(case_id, employee_id):
            captured["consent_employee_id"] = employee_id
            return False  # None never matches a real consent row

        with mock.patch.object(immigration_status, "_check_consent", side_effect=fake_consent):
            with self.assertRaises(immigration_status.HTTPException) as ctx:
                immigration_status.interview_status(
                    case_id="case-1",
                    current_user={"id": "seed-emp-testingapril", "auth_uuid": None},
                )
        self.assertIsNone(captured["consent_employee_id"])  # not the text id
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()

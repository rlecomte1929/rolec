"""Tests for Supabase Auth provisioning (duplicate detection + no-op paths)."""
import concurrent.futures
import unittest
from unittest.mock import MagicMock, patch

from gotrue.errors import AuthApiError

from backend.app.services import supabase_auth_sync
from backend.app.services.supabase_auth_sync import (
    InviteOutcome,
    _duplicate_user_error,
    create_auth_user_and_get_id,
    invite_admin_created_user,
    sync_relopass_user_to_supabase_auth,
)


class TestSupabaseAuthSync(unittest.TestCase):
    def test_duplicate_user_error_codes(self) -> None:
        self.assertTrue(_duplicate_user_error(AuthApiError("taken", 400, "email_exists")))
        self.assertTrue(_duplicate_user_error(AuthApiError("taken", 400, "user_already_exists")))
        self.assertFalse(_duplicate_user_error(AuthApiError("bad", 400, "weak_password")))

    def test_sync_returns_true_without_email(self) -> None:
        self.assertTrue(sync_relopass_user_to_supabase_auth("", "secret123", relopass_user_id="u1"))

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_sync_creates_user(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        mock_get.return_value = client
        ok = sync_relopass_user_to_supabase_auth(
            "a@b.com",
            "secret123",
            relopass_user_id="user-uuid-1",
            full_name="A B",
        )
        self.assertTrue(ok)
        client.auth.admin.create_user.assert_called_once()
        args = client.auth.admin.create_user.call_args[0][0]
        self.assertEqual(args["email"], "a@b.com")
        self.assertEqual(args["password"], "secret123")
        self.assertTrue(args["email_confirm"])
        self.assertEqual(args["user_metadata"]["relopass_user_id"], "user-uuid-1")

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_sync_treats_duplicate_as_ok(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.create_user.side_effect = AuthApiError("exists", 400, "email_exists")
        mock_get.return_value = client
        ok = sync_relopass_user_to_supabase_auth("a@b.com", "secret123", relopass_user_id="u1")
        self.assertTrue(ok)


class TestInviteAdminCreatedUser(unittest.TestCase):
    """AIQ-535: invite returns a typed outcome carrying a failure reason."""

    def test_no_email_is_benign_noop(self) -> None:
        out = invite_admin_created_user("")
        self.assertEqual(out, InviteOutcome(True, None))
        self.assertIsNone(out.error)

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_invite_sent_ok(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        mock_get.return_value = client
        out = invite_admin_created_user("a@b.com", full_name="A B", role="EMPLOYEE")
        self.assertEqual(out, InviteOutcome(True, None))
        client.auth.admin.invite_user_by_email.assert_called_once()

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_missing_admin_interface_reports_reason(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin = None
        mock_get.return_value = client
        out = invite_admin_created_user("a@b.com")
        self.assertFalse(out.sent)
        self.assertIn("admin interface", (out.error or "").lower())

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_timeout_reports_reason(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.invite_user_by_email.side_effect = concurrent.futures.TimeoutError()
        mock_get.return_value = client
        out = invite_admin_created_user("a@b.com")
        self.assertFalse(out.sent)
        self.assertIn("timed out", (out.error or "").lower())

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_duplicate_is_success_no_error(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.invite_user_by_email.side_effect = AuthApiError("exists", 400, "email_exists")
        mock_get.return_value = client
        out = invite_admin_created_user("a@b.com")
        self.assertEqual(out, InviteOutcome(True, None))

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_generic_failure_reports_safe_reason(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.invite_user_by_email.side_effect = RuntimeError("smtp://user:pass@host leaked")
        mock_get.return_value = client
        out = invite_admin_created_user("a@b.com")
        self.assertFalse(out.sent)
        # Reason names the exception type but must NOT leak the raw message (creds/URLs).
        self.assertIn("RuntimeError", out.error or "")
        self.assertNotIn("smtp://", out.error or "")


class TestCreateAuthUserAndGetId(unittest.TestCase):
    """AIQ-937: duplicate-user recovery must use the auth.users DB resolver,
    not GoTrue list_users (which 500s past page 1 on prod)."""

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_create_returns_new_uid(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.create_user.return_value = MagicMock(user=MagicMock(id="new-uid-1"))
        mock_get.return_value = client
        self.assertEqual(create_auth_user_and_get_id("a@b.com"), "new-uid-1")

    @patch("backend.app.services.supabase_auth_sync._resolve_auth_user_id_by_email")
    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_duplicate_resolves_uid_via_db_not_list_users(
        self, mock_get: MagicMock, mock_resolve: MagicMock
    ) -> None:
        client = MagicMock()
        client.auth.admin.create_user.side_effect = AuthApiError("exists", 400, "email_exists")
        mock_get.return_value = client
        mock_resolve.return_value = "existing-uid-9"

        uid = create_auth_user_and_get_id("dupe@b.com")

        self.assertEqual(uid, "existing-uid-9")
        mock_resolve.assert_called_once_with("dupe@b.com")
        # The broken GoTrue scan must NOT be used for duplicate recovery.
        client.auth.admin.list_users.assert_not_called()


if __name__ == "__main__":
    unittest.main()

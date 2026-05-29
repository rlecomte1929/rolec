"""Tests for Supabase Auth provisioning (duplicate detection + no-op paths)."""
import unittest
from unittest.mock import MagicMock, patch

from gotrue.errors import AuthApiError

from backend.app.services.supabase_auth_sync import (
    _duplicate_user_error,
    _rate_limited_error,
    provision_admin_created_user,
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


class TestProvisionAdminCreatedUser(unittest.TestCase):
    """B7: HR-initiated provisioning with rate-limit-safe fallback."""

    def test_rate_limited_error_detection(self) -> None:
        self.assertTrue(_rate_limited_error(AuthApiError("slow down", 429, "over_email_send_rate_limit")))
        self.assertTrue(_rate_limited_error(AuthApiError("too many", 429, "over_request_rate_limit")))
        self.assertFalse(_rate_limited_error(AuthApiError("nope", 400, "email_exists")))

    def test_noop_without_email(self) -> None:
        out = provision_admin_created_user("")
        self.assertEqual(out["status"], "noop")
        self.assertFalse(out["invite_sent"])

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_invite_succeeds(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        mock_get.return_value = client
        out = provision_admin_created_user("a@b.com", full_name="A B", role="employee")
        self.assertEqual(out["status"], "invited")
        self.assertTrue(out["invite_sent"])
        client.auth.admin.invite_user_by_email.assert_called_once()
        client.auth.admin.create_user.assert_not_called()

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_rate_limit_falls_back_to_create_user(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.invite_user_by_email.side_effect = AuthApiError(
            "rate", 429, "over_email_send_rate_limit"
        )
        mock_get.return_value = client
        out = provision_admin_created_user("bulk@b.com", full_name="Bulk User")
        self.assertEqual(out["status"], "created_pending_invite")
        self.assertFalse(out["invite_sent"])
        client.auth.admin.create_user.assert_called_once()
        attrs = client.auth.admin.create_user.call_args[0][0]
        self.assertEqual(attrs["email"], "bulk@b.com")
        self.assertTrue(attrs["email_confirm"])
        self.assertTrue(len(attrs["password"]) >= 6)

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_duplicate_invite_treated_as_exists(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.invite_user_by_email.side_effect = AuthApiError("dup", 400, "email_exists")
        mock_get.return_value = client
        out = provision_admin_created_user("dupe@b.com")
        self.assertEqual(out["status"], "exists")
        client.auth.admin.create_user.assert_not_called()

    @patch("backend.app.services.supabase_auth_sync.get_supabase_admin_client")
    def test_non_rate_limit_invite_error_is_error(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.invite_user_by_email.side_effect = AuthApiError("boom", 500, "unexpected_failure")
        mock_get.return_value = client
        out = provision_admin_created_user("err@b.com")
        self.assertEqual(out["status"], "error")
        client.auth.admin.create_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Tests for Supabase Auth provisioning (duplicate detection + no-op paths)."""
import unittest
from unittest.mock import MagicMock, patch

from gotrue.errors import AuthApiError

from backend.services.supabase_auth_sync import _duplicate_user_error, sync_relopass_user_to_supabase_auth


class TestSupabaseAuthSync(unittest.TestCase):
    def test_duplicate_user_error_codes(self) -> None:
        self.assertTrue(_duplicate_user_error(AuthApiError("taken", 400, "email_exists")))
        self.assertTrue(_duplicate_user_error(AuthApiError("taken", 400, "user_already_exists")))
        self.assertFalse(_duplicate_user_error(AuthApiError("bad", 400, "weak_password")))

    def test_sync_returns_true_without_email(self) -> None:
        self.assertTrue(sync_relopass_user_to_supabase_auth("", "secret123", relopass_user_id="u1"))

    @patch("backend.services.supabase_auth_sync.get_supabase_admin_client")
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

    @patch("backend.services.supabase_auth_sync.get_supabase_admin_client")
    def test_sync_treats_duplicate_as_ok(self, mock_get: MagicMock) -> None:
        client = MagicMock()
        client.auth.admin.create_user.side_effect = AuthApiError("exists", 400, "email_exists")
        mock_get.return_value = client
        ok = sync_relopass_user_to_supabase_auth("a@b.com", "secret123", relopass_user_id="u1")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

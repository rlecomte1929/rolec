"""AIQ-1521 — supplier magic-link.

The security properties here are NOT the same as the provider magic-link, on purpose. The
provider JWT is stateless: `verify` never touches the DB, so `revoked_at` is only honoured at
redemption and a revoked link keeps working for its full life. Submitting a quote is a FINANCIAL
write, so this one re-reads the invite row on EVERY request.

These tests pin exactly that difference:
  * a revoked link stops working immediately
  * a link cannot be used twice (no second quote)
  * a link for RFQ A cannot be replayed against RFQ B
  * an expired link is refused
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-for-supplier-jwt")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import HTTPException  # noqa: E402

from backend.app.services.supplier_jwt import (  # noqa: E402
    generate_supplier_token,
    hash_token,
    verify_supplier_token,
)


class TokenTests(unittest.TestCase):
    def test_token_is_scoped_to_one_rfq_and_one_supplier(self):
        t = generate_supplier_token(
            recipient_id="rec-1", rfq_id="rfq-1", vendor_id="v-1", email="ops@mover.com"
        )
        claims = verify_supplier_token(t)
        self.assertEqual(claims["recipient_id"], "rec-1")
        self.assertEqual(claims["rfq_id"], "rfq-1")
        self.assertEqual(claims["vendor_id"], "v-1")
        self.assertEqual(claims["app_role"], "supplier")

    def test_a_provider_token_cannot_be_replayed_as_a_supplier_token(self):
        # The whole reason supplier_jwt is a SIBLING of provider_jwt rather than a reuse: if we
        # overloaded provider_id to carry a vendor id, every /api/provider/* route would accept
        # this token and query provider_tasks with a vendor id.
        import jwt as pyjwt

        forged = pyjwt.encode(
            {"app_role": "provider", "provider_id": "p-1", "rfq_id": "rfq-1",
             "exp": int((datetime.now(tz=timezone.utc) + timedelta(days=1)).timestamp())},
            os.environ["SUPABASE_JWT_SECRET"],
            algorithm="HS256",
        )
        with self.assertRaises(ValueError):
            verify_supplier_token(forged)

    def test_the_raw_token_is_never_what_we_store(self):
        t = generate_supplier_token(
            recipient_id="rec-1", rfq_id="rfq-1", vendor_id="v-1", email="ops@mover.com"
        )
        h = hash_token(t)
        self.assertNotEqual(h, t)
        self.assertEqual(len(h), 64)  # sha256 hex
        self.assertEqual(h, hash_token(t))  # stable


def _recipient(**over):
    row = {
        "id": "rec-1",
        "rfq_id": "rfq-1",
        "vendor_id": "v-1",
        "status": "sent",
        "revoked_at": None,
        "expires_at": datetime.now(tz=timezone.utc) + timedelta(days=7),
        "quote_submitted_at": None,
        "invited_email": "ops@mover.com",
        "first_viewed_at": None,
    }
    row.update(over)
    return row


class LinkGuardTests(unittest.TestCase):
    """require_supplier_link is the gate. It must fail CLOSED."""

    def setUp(self):
        from unittest import mock

        from backend.app.routers import supplier_rfq

        self.mod = supplier_rfq
        self.mock = mock

    def _call(self, row, token=None):
        token = token or generate_supplier_token(
            recipient_id="rec-1", rfq_id="rfq-1", vendor_id="v-1", email="ops@mover.com"
        )
        db = self.mock.MagicMock()
        conn = db.engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.mappings.return_value.first.return_value = row
        with self.mock.patch.object(self.mod, "db", db):
            return self.mod.require_supplier_link(authorization=f"Bearer {token}")

    def test_a_valid_link_resolves(self):
        got = self._call(_recipient())
        self.assertEqual(got["id"], "rec-1")

    def test_a_REVOKED_link_is_refused(self):
        # The provider magic-link does NOT do this — its stateless JWT sails past revocation.
        with self.assertRaises(HTTPException) as ctx:
            self._call(_recipient(revoked_at=datetime.now(tz=timezone.utc)))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_a_link_cannot_be_used_TWICE(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(_recipient(quote_submitted_at=datetime.now(tz=timezone.utc)))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_GET_allows_already_quoted_read_only(self):
        token = generate_supplier_token(
            recipient_id="rec-1", rfq_id="rfq-1", vendor_id="v-1", email="ops@mover.com"
        )
        db = self.mock.MagicMock()
        conn = db.engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.mappings.return_value.first.return_value = _recipient(
            quote_submitted_at=datetime.now(tz=timezone.utc)
        )
        with self.mock.patch.object(self.mod, "db", db):
            got = self.mod.require_supplier_link_read(authorization=f"Bearer {token}")
        self.assertEqual(got["id"], "rec-1")
        self.assertTrue(got.get("quote_submitted_at"))

    def test_an_EXPIRED_link_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(_recipient(expires_at=datetime.now(tz=timezone.utc) - timedelta(days=1)))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_an_unknown_token_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(None)  # no matching token_hash row
        self.assertEqual(ctx.exception.status_code, 401)

    def test_a_token_for_ANOTHER_rfq_cannot_be_replayed(self):
        # Token says rfq-1; the row it hashes to says rfq-2. Refuse.
        with self.assertRaises(HTTPException) as ctx:
            self._call(_recipient(rfq_id="rfq-2"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_no_token_at_all_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            self.mod.require_supplier_link(authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)


class SendGuardTests(unittest.TestCase):
    def test_sending_is_OPT_IN(self):
        """Minting a link is harmless. Emailing a real company that has never heard of us is
        not. `send_email` defaults to False so a send can never happen by accident."""
        from backend.app.routers.supplier_rfq import SendSupplierLinksPayload

        p = SendSupplierLinksPayload(targets=[])
        self.assertFalse(p.send_email)


if __name__ == "__main__":
    unittest.main()

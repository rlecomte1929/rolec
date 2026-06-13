"""AIQ-913 root-cause guard — verify_* probe scripts must not seed PROD by default.

Covers scripts/_prod_write_guard.py: prod-host classification, hard abort when a
write script targets prod without opt-in, and the local / explicit-opt-in paths.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPTS = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _prod_write_guard import is_prod_base, guard_prod_writes  # noqa: E402


class ProdWriteGuardTests(unittest.TestCase):
    def test_prod_host_classification(self):
        self.assertTrue(is_prod_base("https://api.relopass.com"))
        self.assertTrue(is_prod_base("https://relopass.com"))
        self.assertFalse(is_prod_base("http://localhost:8000"))
        self.assertFalse(is_prod_base("https://staging.example.com"))
        self.assertFalse(is_prod_base(""))

    def test_aborts_on_prod_without_optin(self):
        old = os.environ.pop("RELOPASS_ALLOW_PROD_WRITES", None)
        try:
            with self.assertRaises(SystemExit) as cm:
                guard_prod_writes("https://api.relopass.com")
            self.assertEqual(cm.exception.code, 2)
        finally:
            if old is not None:
                os.environ["RELOPASS_ALLOW_PROD_WRITES"] = old

    def test_non_prod_passes(self):
        old = os.environ.pop("RELOPASS_ALLOW_PROD_WRITES", None)
        try:
            guard_prod_writes("http://localhost:8000")  # must not raise
        finally:
            if old is not None:
                os.environ["RELOPASS_ALLOW_PROD_WRITES"] = old

    def test_prod_with_explicit_optin_passes(self):
        os.environ["RELOPASS_ALLOW_PROD_WRITES"] = "1"
        try:
            guard_prod_writes("https://api.relopass.com")  # must not raise
        finally:
            del os.environ["RELOPASS_ALLOW_PROD_WRITES"]


if __name__ == "__main__":
    unittest.main()

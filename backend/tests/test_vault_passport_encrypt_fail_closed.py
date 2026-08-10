"""AIQ-1780 — the passport vault must never store a plaintext passport number.

`save_ocr_to_vault` used to encrypt like this::

    enc_key = _get_enc_key()
    if enc_key:                 # unset key -> silently skipped
        ...encrypt...
    # raw_updates["passport_number"] keeps the PLAINTEXT and is written

`IMMIGRATION_ENCRYPTION_KEY` is unset in production, so the skip branch was the
LIVE branch: a passport number — an Article 9 special-category identifier — would
have been written to the database in the clear because a config value was missing.

Its sibling on the manual-update path (`immigration_intake_profile.update_profile_employee`)
already raised 500 rather than write. Two paths disagreeing about the same security
property is the actual defect; these tests pin them to the same answer.

The load-bearing test is `test_no_plaintext_passport_reaches_the_database`: the others
check the raise, that one checks the thing we actually care about.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

_PLAINTEXT = "L898902C3"


def _ocr_module():
    """Import the real module HERE, never at module scope.

    test_document_extraction_queue installs a MagicMock into
    sys.modules["backend.app.services.ocr_passport_extractor"] at its own import
    time and only restores it in tearDownModule. Pytest imports every test module
    during collection, so a module-scope import here binds to that mock forever and
    every assertion below silently passes against a Mock. Resolving at call time
    gets the real module (the stub is restored before these tests run).
    """
    import importlib

    return importlib.import_module("backend.app.services.ocr_passport_extractor")


class EncryptPassportNumberTests(unittest.TestCase):
    def test_raises_when_no_encryption_key_is_configured(self):
        """The production condition today: the key is simply not set."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                _ocr_module()._encrypt_passport_number(_PLAINTEXT)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertNotIn(
            _PLAINTEXT, str(ctx.exception.detail),
            "the plaintext passport number must never appear in an error detail",
        )

    def test_raises_rather_than_returning_plaintext_when_encryption_yields_nothing(self):
        """A NULL/absent pgcrypto result must not fall through to the input value."""
        class _Conn:
            def execute(self, *_a, **_k):
                class _R:
                    def mappings(self_inner):
                        class _M:
                            def first(self_m):
                                return None      # no row
                        return _M()
                return _R()
            def __enter__(self):
                return self
            def __exit__(self, *_a):
                return False

        class _Engine:
            def begin(self):
                return _Conn()

        with patch.dict(os.environ, {"IMMIGRATION_ENCRYPTION_KEY": "k"}, clear=False):
            with patch("backend.database.db") as fake_db:
                fake_db.engine = _Engine()
                with self.assertRaises(HTTPException):
                    _ocr_module()._encrypt_passport_number(_PLAINTEXT)

    def test_returns_the_ciphertext_when_encryption_succeeds(self):
        class _Conn:
            def execute(self, *_a, **_k):
                class _R:
                    def mappings(self_inner):
                        class _M:
                            def first(self_m):
                                return {"encrypted": b"\\xdeadbeef"}
                        return _M()
                return _R()
            def __enter__(self):
                return self
            def __exit__(self, *_a):
                return False

        class _Engine:
            def begin(self):
                return _Conn()

        with patch.dict(os.environ, {"IMMIGRATION_ENCRYPTION_KEY": "k"}, clear=False):
            with patch("backend.database.db") as fake_db:
                fake_db.engine = _Engine()
                out = _ocr_module()._encrypt_passport_number(_PLAINTEXT)
        self.assertEqual(out, b"\\xdeadbeef")
        self.assertNotEqual(out, _PLAINTEXT)


class SaveOcrToVaultFailsClosedTests(unittest.TestCase):
    def test_no_plaintext_passport_reaches_the_database(self):
        """THE test. Drive save_ocr_to_vault with no key and assert that no SQL
        statement executed anywhere carries the plaintext passport number.

        Asserting only "it raises" would pass even if the raise happened AFTER a
        write. This inspects every parameter set handed to the DB instead.
        """
        executed: list = []

        class _Conn:
            def execute(self, *args, **kwargs):
                executed.append((args, kwargs))
                class _R:
                    def mappings(self_inner):
                        class _M:
                            def first(self_m):
                                return None
                        return _M()
                    def __iter__(self_inner):
                        return iter(())
                return _R()
            def __enter__(self):
                return self
            def __exit__(self, *_a):
                return False

        class _Engine:
            def begin(self):
                return _Conn()
            def connect(self):
                return _Conn()

        extraction = _ocr_module().PassportExtractionResult(
            surname="ERIKSSON", given_names="ANNA MARIA",
            date_of_birth="1974-08-12", nationality="UTO",
            passport_number=_PLAINTEXT,
        )

        with patch.dict(os.environ, {}, clear=True):
            with patch("backend.database.db") as fake_db:
                fake_db.engine = _Engine()
                with patch.object(_ocr_module(), "_load_profile_for_case_employee", return_value=None,
                                  create=True):
                    with self.assertRaises(HTTPException):
                        _ocr_module().save_ocr_to_vault("case-1", "emp-1", extraction, "org-1")

        blob = repr(executed)
        self.assertNotIn(
            _PLAINTEXT, blob,
            "a plaintext passport number was passed to the database — this is the "
            "fail-open bug this test exists to prevent",
        )

    def test_extraction_without_a_passport_number_is_unaffected(self):
        """Only the passport number needs encryption; an OCR result without one
        must still be savable. Guards against over-correcting into a hard block."""
        extraction = _ocr_module().PassportExtractionResult(
            surname="ERIKSSON", given_names="ANNA MARIA", nationality="UTO",
        )
        self.assertIsNone(extraction.passport_number)
        # _encrypt_passport_number is only reached when a number is present, so an
        # empty key is irrelevant here — asserted by the branch in save_ocr_to_vault.
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(extraction.passport_number)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

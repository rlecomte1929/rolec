"""AIQ-1802 — an undecryptable passport number must be withheld, never surfaced.

Three code paths decrypted the stored passport number and all three failed OPEN: on
failure they left the CIPHERTEXT in place and handed it onward as though it were the
value. It reached the Article 15 subject-access PDF, the employee's own profile view,
and — worst — got pre-filled onto an immigration form, where an unreadable blob would
have been submitted to a government authority.

All three were the live path: IMMIGRATION_ENCRYPTION_KEY is unset in production, so
`_get_encryption_key()` raises on every call.

WHY THESE ASSERT ON OUTPUT, not on return values. The sibling `dt.label` defect survived
for the whole life of its endpoint because the failure was swallowed one layer below
where anyone looked. A leak here would be at the RENDERING layer, so the PDF bytes and
the response body are what get inspected.

Complements backend/tests/integration/test_vault_passport_roundtrip.py (AIQ-1800), which
proves the pgcrypto/DB layer against real Postgres. This file covers the display layer
above it; neither substitutes for the other.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.services import immigration_service as imm  # noqa: E402

CIPHERTEXT = "\\x4c383938393032433320656e6372797074656420626c6f62"
PLAINTEXT = "L898902C3"


class TestHelperNeverReturnsCiphertext(unittest.TestCase):
    """The contract, stated once: plaintext or None. Never the input."""

    def test_an_unset_key_withholds_rather_than_echoing_the_input(self) -> None:
        """The exact production condition today."""
        with patch.dict(os.environ, {}, clear=True):
            result = imm.decrypt_passport_for_display({"passport_number": CIPHERTEXT})
        self.assertIsNone(result.profile["passport_number"])
        self.assertTrue(result.withheld)

    def test_a_database_failure_withholds(self) -> None:
        engine = MagicMock()
        engine.begin.side_effect = RuntimeError("pgcrypto unavailable")
        with patch.dict(os.environ, {"IMMIGRATION_ENCRYPTION_KEY": "k"}, clear=False), \
             patch.object(imm.db, "engine", engine):
            result = imm.decrypt_passport_for_display({"passport_number": CIPHERTEXT})
        self.assertIsNone(result.profile["passport_number"])
        self.assertTrue(result.withheld)

    def test_a_null_decrypt_result_withholds_rather_than_falling_through(self) -> None:
        """A NULL result is a failure, not an empty passport number. Falling through to
        the input is precisely how the ciphertext used to come back."""
        with patch.dict(os.environ, {"IMMIGRATION_ENCRYPTION_KEY": "k"}, clear=False), \
             patch.object(imm.db, "engine", _engine_returning({"decrypted": None})):
            result = imm.decrypt_passport_for_display({"passport_number": CIPHERTEXT})
        self.assertIsNone(result.profile["passport_number"])
        self.assertTrue(result.withheld)

    def test_a_successful_decrypt_returns_the_plaintext(self) -> None:
        with patch.dict(os.environ, {"IMMIGRATION_ENCRYPTION_KEY": "k"}, clear=False), \
             patch.object(imm.db, "engine", _engine_returning({"decrypted": PLAINTEXT})):
            result = imm.decrypt_passport_for_display({"passport_number": CIPHERTEXT})
        self.assertEqual(result.profile["passport_number"], PLAINTEXT)
        self.assertFalse(result.withheld)

    def test_no_passport_number_is_not_a_withholding(self) -> None:
        result = imm.decrypt_passport_for_display({"passport_number": None, "surname": "X"})
        self.assertFalse(result.withheld)
        self.assertEqual(result.profile["surname"], "X")

    def test_the_input_dict_is_not_mutated(self) -> None:
        original = {"passport_number": CIPHERTEXT}
        with patch.dict(os.environ, {}, clear=True):
            imm.decrypt_passport_for_display(original)
        self.assertEqual(original["passport_number"], CIPHERTEXT,
                         "the caller's dict must be left alone")


def _engine_returning(row):
    class _Conn:
        def execute(self, *_a, **_k):
            class _R:
                def mappings(self_inner):
                    class _M:
                        def first(self_m):
                            return row
                    return _M()
            return _R()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    engine = MagicMock()
    engine.begin.return_value = _Conn()
    return engine


class TestTheArticle15PdfSaysWhatItWithheld(unittest.TestCase):
    """A silent omission is its own Art. 15 problem: the subject cannot tell a field we
    never held from one we could not return."""

    def _pdf(self, profile, withheld):
        from datetime import datetime, timezone

        from backend.app.services.gdpr_export_service import build_data_export_pdf
        return build_data_export_pdf(
            case_id="case-1", employee_id="emp-1", profile=profile,
            interview_answers={}, consent_records=[], access_log=[],
            generated_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            withheld_fields=withheld,
        )

    def test_the_ciphertext_never_reaches_the_pdf(self) -> None:
        pdf = self._pdf({"passport_number": None, "surname": "ERIKSSON"},
                        ["passport_number"])
        self.assertNotIn(CIPHERTEXT.encode(), pdf)
        self.assertNotIn(b"4c383938393032433", pdf)

    def test_a_withheld_field_is_named_in_the_pdf(self) -> None:
        pdf = self._pdf({"passport_number": None}, ["passport_number"])
        # reportlab compresses streams, so assert on something durable: the PDF renders
        # and is materially larger than the same export without the notice.
        baseline = self._pdf({"passport_number": None}, [])
        self.assertGreater(len(pdf), len(baseline),
                           "the withheld notice must actually be rendered")

    def test_the_signature_stays_backward_compatible(self) -> None:
        """Existing callers pass no withheld_fields; that must keep working."""
        from datetime import datetime, timezone

        from backend.app.services.gdpr_export_service import build_data_export_pdf
        pdf = build_data_export_pdf(
            case_id="c", employee_id="e", profile={"surname": "X"},
            interview_answers={}, consent_records=[], access_log=[],
            generated_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        self.assertTrue(pdf.startswith(b"%PDF"))


class TestThereIsExactlyOneDecryptImplementation(unittest.TestCase):
    """Three copies of one rule drifted into two different failure behaviours — one
    logged a warning, two `pass`ed silently. That divergence is what let the same defect
    exist three times with three different comments explaining it away."""

    # Files permitted to call pgp_sym_decrypt directly, each with the reason.
    #
    # prefill_engine has its own value-level copy and is ALREADY FAIL-CLOSED: it returns
    # None on every failure path and never echoes the input. It is the one place that got
    # this right. Its contract differs too — it takes a raw value and returns
    # Optional[str], where the shared helper takes and returns a profile — so folding it
    # in would mean rewriting correct code to satisfy a guard. Consolidating the two onto
    # a shared value-level primitive is a reasonable follow-up, not part of a fix whose
    # subject is fail-OPEN behaviour.
    _ALLOWED = {
        "app/services/immigration_service.py": "the canonical helper",
        "app/services/prefill_engine.py": "already fail-closed; value-level contract",
    }

    def test_no_new_copy_of_passport_decryption_appears(self) -> None:
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        offenders = [
            str(p.relative_to(root))
            for p in (root / "app").rglob("*.py")
            if "pgp_sym_decrypt" in p.read_text(encoding="utf-8")
            and str(p.relative_to(root)) not in self._ALLOWED
        ]
        self.assertEqual(
            offenders, [],
            "a new passport-decryption implementation appeared. Use "
            "immigration_service.decrypt_passport_for_display — three divergent copies, "
            "two of them failing open, is exactly how this defect spread. If a direct "
            "call is genuinely needed, add it to _ALLOWED with the reason it is "
            "fail-closed.",
        )

    def test_the_allowlisted_files_still_exist(self) -> None:
        """A stale allowlist entry would silently weaken the guard."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        for rel in self._ALLOWED:
            self.assertTrue((root / rel).exists(), f"{rel} is allowlisted but gone")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

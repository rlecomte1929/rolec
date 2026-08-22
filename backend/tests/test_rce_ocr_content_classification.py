"""[AIQ-2121] The extraction pipeline classifies a document by READING it, not by its name.

`classify_document_content` — the real C1-04a classifier — was built, tested and had zero
production callers. Everything live called `classify_document`, the filename heuristic, whose
four codes map to NO runtime extractor at all: `runtime_code_for` returns None for every one
of them. So a document routed by filename could never reach an agent, and the pipeline's own
docstring says so ("the fallback has never been able to route anything").

Measured 2026-08-22: filename codes that route = 0 of 4; content codes that route = 6 of 11
(EMPLOYMENT_CONTRACT, PASSPORT_TD3, ID_CARD, VISA_PERMIT, DIPLOMA×2). That gap is what these
tests pin — `test_the_filename_classifier_still_routes_nothing` is the control, and without it
the rest could pass against a change that achieved nothing.

The pre-OCR `document_type` guess still chooses the OCR ENGINE, because you cannot read text
before OCR has run. Content classification is a REFINEMENT once text exists; it never
overrides a type the caller actually stated.

No key and no network: `general_ocr` is injected, and the classifier is patched at the symbol
rce_ocr_parser imported.
"""
from __future__ import annotations

import asyncio
from unittest import mock
from uuid import uuid4

import pytest

from backend.app.services import rce_ocr_parser as parser
from backend.app.services.document_classifier import (
    METHOD_CONTENT,
    METHOD_FILENAME_FALLBACK,
    Classification,
    classify_document,
)
from backend.app.services.document_type_vocabulary import runtime_code_for

CONTRACT_TEXT = (
    "CONTRACT OF EMPLOYMENT\nEmployer: ACME Ireland Ltd\nEmployee: A. Ramirez\n"
    "Position: Senior Data Engineer\nCommencement date: 1 October 2026\n"
    "Gross annual salary: EUR 58,000\nPlace of work: Dublin 2, Ireland"
)


def _classification(code, runtime, *, method=METHOD_CONTENT, confidence=0.94):
    return Classification(
        code=code, runtime_code=runtime, confidence=confidence,
        method=method, fallback_reason=None,
    )


def _parse(**overrides):
    """Drive parse_stored_document with every side effect injected."""
    kwargs = dict(
        document_id=uuid4(),
        case_id=uuid4(),
        storage_path="case-docs/c1/contract.pdf",
        mime_type="application/pdf",
        file_name="scan_001.pdf",          # deliberately meaningless
        downloader=lambda _p: b"%PDF-1.4 fake",
        general_ocr=lambda _c, _m: CONTRACT_TEXT,
    )
    kwargs.update(overrides)
    return asyncio.run(parser.parse_stored_document(**kwargs))


# ── the control: what the live path could do BEFORE this change ────────────────────


class TestTheGapThisCloses:
    def test_the_filename_classifier_still_routes_nothing(self):
        """Not a tautology — it is the reason the change exists. If this ever starts
        returning a runtime code, the premise has changed and the wiring below should be
        re-argued rather than kept out of habit."""
        for name in ("scan_001.pdf", "passport.jpg", "my_contract.pdf", "payslip_july.pdf"):
            code = classify_document(name, "application/pdf")
            assert runtime_code_for(code) is None, (
                f"{name!r} -> {code!r} now maps to a runtime code; re-check AIQ-2121"
            )

    def test_the_content_vocabulary_does_route(self):
        assert runtime_code_for("EMPLOYMENT_CONTRACT") == "EMPLOYMENT_CONTRACT"
        assert runtime_code_for("PASSPORT_TD3") == "PASSPORT_TD3"
        assert runtime_code_for("EU_NATIONAL_ID") == "ID_CARD"


# ── the wiring ─────────────────────────────────────────────────────────────────────


class TestContentClassificationIsWiredIn:
    def test_a_contract_named_scan_001_gets_a_routable_runtime_code(self):
        with mock.patch.object(
            parser, "classify_document_content",
            return_value=_classification("EMPLOYMENT_CONTRACT", "EMPLOYMENT_CONTRACT"),
        ) as fake:
            result = _parse()
        assert result.ok is True
        assert result.runtime_code == "EMPLOYMENT_CONTRACT"
        # It was handed the OCR text, not the filename.
        assert fake.call_args.args[0] == CONTRACT_TEXT

    def test_an_explicitly_stated_type_is_never_overridden(self):
        """A stored rce.documents type is a stated fact; the classifier only replaces a
        guess. It must not even be consulted."""
        with mock.patch.object(parser, "classify_document_content") as fake:
            result = _parse(document_type="DIPLOMA")
        fake.assert_not_called()
        assert result.document_type == "DIPLOMA"
        assert result.runtime_code is None

    def test_no_text_means_no_classifier_call_and_unchanged_behaviour(self):
        with mock.patch.object(parser, "classify_document_content") as fake:
            result = _parse(general_ocr=lambda _c, _m: "")
        fake.assert_not_called()
        assert result.ok is False
        assert result.runtime_code is None

    def test_an_unroutable_content_code_yields_none_not_a_guess(self):
        """UNKNOWN and classified-but-unsupported codes map to None, and that must stay
        None — inventing a nearest match would send an unverified guess to a real
        extractor."""
        with mock.patch.object(
            parser, "classify_document_content",
            return_value=_classification("PAYSLIP", None),
        ):
            assert _parse().runtime_code is None

    def test_a_filename_fallback_inside_the_classifier_is_carried_through_honestly(self):
        with mock.patch.object(
            parser, "classify_document_content",
            return_value=_classification("UNKNOWN", None, method=METHOD_FILENAME_FALLBACK,
                                         confidence=None),
        ):
            result = _parse()
        assert result.runtime_code is None
        assert result.ok is True  # OCR still succeeded; only the type is unknown

    def test_a_classifier_explosion_does_not_break_the_pipeline(self):
        """classify_document_content promises never to raise, but this path is fail-soft in
        its own right and must not depend on that promise holding."""
        with mock.patch.object(
            parser, "classify_document_content", side_effect=RuntimeError("boom"),
        ):
            result = _parse()
        assert result.runtime_code is None
        assert isinstance(result, parser.OcrParseResult)

    def test_the_passport_branch_is_untouched(self):
        """MRZ documents route to the passport OCR before any text exists — content
        classification must not be reached, and that branch must not regress."""
        sentinel = object()

        async def _passport(_content, _mime):
            return sentinel

        with mock.patch.object(parser, "classify_document_content") as fake, \
             mock.patch.object(parser, "passport_result_to_parsed_document",
                               return_value="passport-result") as to_doc:
            out = _parse(document_type="PASSPORT_TD3", passport_ocr=_passport)
        fake.assert_not_called()
        to_doc.assert_called_once()
        assert out == "passport-result"


# ── the gate that decides whether extraction runs at all ───────────────────────────


class TestWorkerUsesTheDerivedCode:
    """`code` (the stored type) was the ONLY gate, so a document with no stored type
    skipped extraction even after a clean OCR — and nothing could ever supply one."""

    def _run(self, monkeypatch, *, stored_code, runtime_code):
        from types import SimpleNamespace
        from backend.app.services import rce_pipeline_worker as worker

        seen = {}
        doc = {
            "document_id": uuid4(), "case_id": str(uuid4()), "mime_type": "application/pdf",
            "storage_uri": "case-docs/c1/x.pdf", "original_filename": "scan_001.pdf",
            "document_type_code": stored_code,
        }
        ocr = SimpleNamespace(ok=True, runtime_code=runtime_code)

        async def _parse_stub(**_kw):
            return ocr

        async def _extract(*, ocr_result, document_type_code, engine=None):
            seen["code"] = document_type_code
            return SimpleNamespace(status="ok")

        monkeypatch.setattr(worker, "_load_rce_document", lambda eng, rid: doc)
        monkeypatch.setattr(worker, "parse_stored_document", _parse_stub)
        monkeypatch.setattr(worker, "run_extraction_for_document", _extract)
        monkeypatch.setattr(worker, "resolve_case_persons", lambda c, *, engine: 0)
        monkeypatch.setattr(
            worker, "run_contradiction_detection_for_case", lambda c, *, engine: []
        )
        # A real UUID string: the worker does UUID(rce_document_id) inside the
        # parse_stored_document call, so a non-UUID raises before any stub is reached and
        # the whole stage fails-soft into 'skipped_no_ocr' — which would make these tests
        # pass for entirely the wrong reason.
        result = asyncio.run(worker.process_rce_document(str(uuid4()), engine=object()))
        return result, seen

    def test_extraction_runs_on_the_derived_code_when_none_is_stored(self, monkeypatch):
        result, seen = self._run(
            monkeypatch, stored_code=None, runtime_code="EMPLOYMENT_CONTRACT"
        )
        assert seen.get("code") == "EMPLOYMENT_CONTRACT"
        assert result.extraction_status == "ok"

    def test_a_stored_code_still_wins_over_the_derived_one(self, monkeypatch):
        _result, seen = self._run(
            monkeypatch, stored_code="PASSPORT_TD3", runtime_code="EMPLOYMENT_CONTRACT"
        )
        assert seen.get("code") == "PASSPORT_TD3"

    def test_neither_code_means_extraction_is_still_skipped(self, monkeypatch):
        result, seen = self._run(monkeypatch, stored_code=None, runtime_code=None)
        assert "code" not in seen
        assert result.extraction_status == "skipped_no_ocr"

"""[S4/S5/S6] Golden harness for the DE/FR data sheets.

PARSES BY TEMPLATE CODE, not by position. The FR->NO harness
(test_golden_case_fr_no_datasheet.py) takes the FIRST `'[{...}]'::jsonb` literal in the
migration it reads, which works only because that file seeds exactly one template. This
migration seeds two, each with a fields array, a trigger_rules array and a sections array —
six jsonb literals — so position-based parsing would silently read the wrong one and every
assertion below would still pass while covering nothing.

The literal scanner respects SQL `''` escaping. Naive regex is what gave
check_form_template_honesty.py three silent blind spots (a `;` inside a note, dollar
quoting, and a `--` comment between two values), each of which dropped templates from the
scan without a word.

WHAT THE OMISSIONS ARE FOR. ReloPass_DE-FR_Requirements_VERIFICATION.md forbids specific
content, and those prohibitions are the point of this file — a data sheet that quietly
regains a plausible-but-unsourced figure is worse than one that never had it, because the
employee cannot tell the difference. Each negative assertion below names its report item.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import unittest
from typing import Dict, List, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.data_sheet_pdf import render_data_sheet  # noqa: E402
from backend.app.services.localised_labels import localised_label  # noqa: E402

_MIGRATION = os.path.join(
    _REPO_ROOT, "supabase", "migrations", "20261027000000_seed_de_fr_data_sheets.sql"
)
_CODES = ("RP-DE-DATASHEET", "RP-FR-DATASHEET")


# ── SQL literal scanning ─────────────────────────────────────────────────────


def _literals(sql: str) -> List[Tuple[int, int, str]]:
    """Every single-quoted SQL literal as (start_offset, end_offset, decoded_value).

    Handles the `''` escape. Skips `--` line comments and `/* */` blocks so a quote inside
    prose cannot desynchronise the scan.

    The END offset is recorded during the scan rather than derived from the decoded value's
    length. Deriving it is wrong the moment a literal contains an escaped quote — the raw
    text is longer than the decoded string — and that silently broke the `::jsonb` lookahead
    on the first run, which then found zero arrays.
    """
    out: List[Tuple[int, int, str]] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if ch == "/" and sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if ch == "'":
            start = i
            i += 1
            buf: List[str] = []
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(sql[i])
                i += 1
            out.append((start, i, "".join(buf)))
            continue
        i += 1
    return out


def _parse() -> Dict[str, Dict[str, object]]:
    sql = open(_MIGRATION, encoding="utf-8").read()
    lits = _literals(sql)
    parsed: Dict[str, Dict[str, object]] = {c: {} for c in _CODES}

    # fields / trigger_rules: the jsonb arrays that follow each code literal, in order.
    for code in _CODES:
        anchors = [start for start, _end, val in lits if val == code]
        assert anchors, f"{code} not found in {_MIGRATION}"
        insert_at = anchors[0]
        jsons = []
        for start, end, val in lits:
            if start <= insert_at:
                continue
            if not sql[end:end + 8].startswith("::jsonb"):
                continue
            try:
                jsons.append(json.loads(val))
            except json.JSONDecodeError:
                continue
            if len(jsons) == 2:
                break
        assert len(jsons) == 2, f"{code}: expected fields + trigger_rules, got {len(jsons)}"
        parsed[code]["fields"], parsed[code]["trigger_rules"] = jsons

    # sections: keyed off `WHERE code = '<code>'` at the end of each UPDATE.
    for m in re.finditer(
        r"SET sections = ('\[(?:[^']|'')*\]')::jsonb[\s\S]*?WHERE code = '([A-Z0-9-]+)'", sql
    ):
        code = m.group(2)
        if code not in parsed:
            continue
        raw = m.group(1)[1:-1].replace("''", "'")
        parsed[code]["sections"] = json.loads(raw)

    for code in _CODES:
        assert "sections" in parsed[code], f"{code}: no sections UPDATE found"
    return parsed


_P = _parse()


def _fields(code: str) -> List[dict]:
    return _P[code]["fields"]  # type: ignore[return-value]


def _sections(code: str) -> List[dict]:
    return _P[code]["sections"]  # type: ignore[return-value]


def _all_text(code: str) -> str:
    return json.dumps(_P[code], ensure_ascii=False)


# ── Structure ────────────────────────────────────────────────────────────────


class TestStructure(unittest.TestCase):
    def test_the_parser_found_two_distinct_templates(self) -> None:
        """Guards the harness itself. If position-based parsing crept back in, both codes
        would resolve to the same arrays and every test below would pass vacuously."""
        self.assertNotEqual(_fields("RP-DE-DATASHEET"), _fields("RP-FR-DATASHEET"))
        self.assertNotEqual(_sections("RP-DE-DATASHEET"), _sections("RP-FR-DATASHEET"))
        self.assertEqual(len(_fields("RP-DE-DATASHEET")), 13)
        self.assertEqual(len(_fields("RP-FR-DATASHEET")), 10)

    def test_no_section_references_a_field_that_does_not_exist(self) -> None:
        for code in _CODES:
            ids = {f["id"] for f in _fields(code)}
            refs = {r for s in _sections(code) for r in s["field_ids"]}
            self.assertEqual(sorted(refs - ids), [], code)

    def test_no_field_is_left_out_of_every_section(self) -> None:
        """A field in no section silently disappears once sections drive the layout."""
        for code in _CODES:
            ids = {f["id"] for f in _fields(code)}
            refs = {r for s in _sections(code) for r in s["field_ids"]}
            self.assertEqual(sorted(ids - refs), [], code)

    def test_every_fields_section_key_names_a_real_section(self) -> None:
        """SUBSET, not equality — and that is the whole reason S1 exists.

        The FR->NO harness could assert `{section ids} == {fields[].section}` because every
        section there has fields. Both sheets here open with a section that has NONE
        (Germany issues no residence document; France has no arrival registration), so an
        empty section legitimately appears in the section ids and in no field. Asserting
        equality would forbid the feature this seed was waiting for.
        """
        for code in _CODES:
            section_ids = {s["id"] for s in _sections(code)}
            field_sections = {f["section"] for f in _fields(code)}
            self.assertTrue(field_sections <= section_ids,
                            f"{code}: {sorted(field_sections - section_ids)} not a section")

    def test_each_sheet_has_exactly_one_empty_section(self) -> None:
        expected = {
            "RP-DE-DATASHEET": "no_residence_document",
            "RP-FR-DATASHEET": "no_arrival_registration",
        }
        for code in _CODES:
            empty = [s["id"] for s in _sections(code) if not s["field_ids"]]
            self.assertEqual(empty, [expected[code]], code)

    def test_section_numbers_are_contiguous_from_one(self) -> None:
        for code in _CODES:
            nums = [s["number"] for s in _sections(code)]
            self.assertEqual(nums, list(range(1, len(nums) + 1)), code)

    def test_every_section_carries_every_key_a_renderer_reads(self) -> None:
        keys = ("id", "number", "title", "authority", "portal_url", "deadline_hint",
                "session_group", "callout_top", "callout_bottom", "field_ids")
        for code in _CODES:
            for s in _sections(code):
                for k in keys:
                    self.assertIn(k, s, f"{code}/{s['id']} omits {k}")

    def test_field_ids_are_unique_within_a_sheet(self) -> None:
        for code in _CODES:
            ids = [f["id"] for f in _fields(code)]
            self.assertEqual(len(ids), len(set(ids)), code)


# ── Localisation (C1) ────────────────────────────────────────────────────────


class TestLocalisedLabels(unittest.TestCase):
    _LANG = {"RP-DE-DATASHEET": "de", "RP-FR-DATASHEET": "fr"}

    def test_every_field_resolves_a_localised_label(self) -> None:
        """C1 generalised label_nb to label_<lang>. If a field lacks the key, the dossier's
        translation toggle silently falls back to English for that row only, which reads as
        a bug rather than as a missing translation."""
        for code, lang in self._LANG.items():
            for f in _fields(code):
                self.assertTrue(
                    localised_label(f, lang),
                    f"{code}/{f['id']} has no label_{lang}",
                )

    def test_the_localised_label_is_not_just_the_english_one(self) -> None:
        for code, lang in self._LANG.items():
            same = [f["id"] for f in _fields(code)
                    if localised_label(f, lang) == f["label"]]
            self.assertEqual(same, [], f"{code}: untranslated label_{lang} on {same}")


# ── The prohibitions ────────────────────────────────────────────────────────


class TestForbiddenContent(unittest.TestCase):
    """Each of these is a specific figure the verification report refused to authorise.

    They are asserted negatively because the failure mode is regaining them: a later editor
    adds a plausible number in good faith, and the employee cannot tell a sourced figure
    from an invented one.
    """

    def test_no_steuer_idnr_lead_time(self) -> None:
        """Report item 2. A short lead time circulates widely and appears on no BZSt page;
        the only official timing is the three-month chase threshold."""
        de = _all_text("RP-DE-DATASHEET")
        # NO adjacency check. I tried twice to catch "an IdNr lead time expressed in weeks"
        # by proximity, and both versions flagged correct text: the sheet legitimately
        # quotes the two-week ANMELDUNG deadline (BMG § 17) immediately before explaining
        # that the IdNr is triggered by that registration. Nothing short of semantics
        # separates those two sentences, so this asserts on the specific forbidden figures
        # instead — which is what the report actually prohibits.
        for pat in (r"\bfour weeks\b", r"\bvier Wochen\b", r"\b4 weeks\b"):
            self.assertIsNone(re.search(pat, de, re.IGNORECASE), pat)
        self.assertIn("three months", de,
                      "the three-month chase threshold is the fact that replaces it")

    def test_no_steuerklasse_vi_withholding_claim(self) -> None:
        """Report item 10, explicitly NOT verified. It would be excellent content — the DE
        analogue of Norway's 50% rule — but the BZSt employer FAQ does not say it."""
        self.assertNotRegex(_all_text("RP-DE-DATASHEET"), r"(?i)Steuerklasse|tax class")

    def test_no_income_threshold_figure_for_private_cover(self) -> None:
        """Report item 8. The ministry page does not publish the threshold."""
        de = _all_text("RP-DE-DATASHEET")
        self.assertNotRegex(de, r"(?i)Jahresarbeitsentgeltgrenze")
        self.assertNotRegex(de, r"\b\d{2}[.,]\d{3}\s*(?:EUR|€|Euro)")

    def test_no_article_16_posting_ceiling(self) -> None:
        """Report item 7. An Art. 16 agreement can extend beyond 24 months, but the
        commonly cited ~5 years is not corridor-confirmed. Both sheets DO mention 'five
        years' in a legitimate permanent-residence context, so this asserts on proximity to
        the Article 16 clause rather than on the bare number — my first version of this
        check flagged the correct text."""
        for code in _CODES:
            text = _all_text(code)
            for m in re.finditer(r"(?i)article\s*16", text):
                window = text[m.start(): m.start() + 400]
                self.assertIsNone(
                    re.search(r"(?i)\b(five|5)\s*(years|ans|Jahre)\b", window),
                    f"{code}: a ceiling appears next to the Article 16 clause",
                )

    def test_the_24_month_limit_is_present_because_it_IS_sourced(self) -> None:
        """The mirror of the above: restraint must not become silence on the fact that was
        confirmed."""
        for code in _CODES:
            self.assertRegex(_all_text(code), r"24 months")

    def test_the_dpae_is_the_employers_duty_not_the_employees(self) -> None:
        """Report item 6. Putting a DPAE action on the employee's sheet asks them to do
        something they cannot."""
        fr = _all_text("RP-FR-DATASHEET")
        self.assertRegex(fr, r"(?i)employer['’]?s? (?:obligation|duty)")
        dpae = [s for s in _sections("RP-FR-DATASHEET") if s["id"] == "dpae"][0]
        self.assertRegex(str(dpae["authority"]), r"(?i)employer")
        self.assertRegex(str(dpae["callout_top"]), r"(?i)NOTHING IN THIS SECTION IS YOURS")

    def test_no_german_residence_document_instruction(self) -> None:
        """Report item 3, REFUTED AS STATED. § 2(4) FreizügG/EU: an EU citizen needs no
        residence title, and the Freizügigkeitsbescheinigung no longer exists. This is the
        defect that WAS live in prod as RESID-PERMIT-DE."""
        de = _all_text("RP-DE-DATASHEET")
        for pat in (r"(?i)obtain\s+(?:your\s+)?residence\s+(?:title|document|permit)",
                    r"(?i)apply\s+for\s+a\s+residence\s+(?:title|permit)",
                    r"(?i)book\s+an?\s+Ausl\w*nderbeh\w*rde\s+appointment"):
            self.assertIsNone(re.search(pat, de), pat)
        self.assertRegex(de, r"(?i)no residence title|none required")

    def test_france_states_the_absence_rather_than_omitting_it(self) -> None:
        """Report item 4, called 'the highest content risk in the DE->FR sheet': left as a
        silent gap, an employee reasonably assumes ReloPass forgot it."""
        sec = [s for s in _sections("RP-FR-DATASHEET")
               if s["id"] == "no_arrival_registration"][0]
        self.assertEqual(sec["number"], 1, "the absence should be the first thing read")
        self.assertRegex(str(sec["callout_top"]), r"(?i)no arrival registration")
        self.assertRegex(str(sec["callout_bottom"]), r"(?i)not an omission")


# ── Rendering ────────────────────────────────────────────────────────────────


def _text(pdf: bytes) -> str:
    import pypdf
    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)


class TestRendering(unittest.TestCase):
    def test_both_sheets_render_every_section_title(self) -> None:
        for code in _CODES:
            pdf = render_data_sheet(
                title=code, fields=_fields(code), values={}, sections=_sections(code)
            )
            self.assertIsNotNone(pdf, code)
            body = _text(pdf)
            for s in _sections(code):
                # The renderer may wrap; match on a distinctive head of the title.
                head = re.split(r"[(/—]", s["title"])[0].strip()
                self.assertIn(head, body, f"{code}: section '{s['id']}' did not render")

    def test_the_empty_section_renders_as_a_statement(self) -> None:
        """The property that did not exist before S1: both renderers grouped BY FIELD, so a
        section with no inputs could not appear at all."""
        for code, sec_id in (("RP-DE-DATASHEET", "no_residence_document"),
                             ("RP-FR-DATASHEET", "no_arrival_registration")):
            sec = [s for s in _sections(code) if s["id"] == sec_id][0]
            body = _text(render_data_sheet(
                title=code, fields=_fields(code), values={}, sections=_sections(code)))
            head = re.split(r"[(/—]", sec["title"])[0].strip()
            self.assertIn(head, body, f"{code}: the empty section vanished")

    def test_no_fillable_field_renders_blank_when_a_value_exists(self) -> None:
        """The FR->NO harness's '0 blank / 0 wrong' property, per sheet.

        Scoped to FILLABLE fields. `consult_professional` fields are excluded because the
        renderer deliberately refuses to print a value for them — see the test below. My
        first version asserted every value rendered and failed on exactly the three DE
        determinations, which is the renderer being right and the test being wrong.
        """
        for code in _CODES:
            fillable = [f for f in _fields(code) if not f.get("consult_professional")]
            values = {f["id"]: f"VAL-{i}" for i, f in enumerate(fillable)}
            body = _text(render_data_sheet(
                title=code, fields=_fields(code), values=values,
                sections=_sections(code)))
            missing = [v for v in values.values() if v not in body]
            self.assertEqual(missing, [], f"{code}: values absent from the PDF: {missing}")

    def test_a_determination_never_renders_as_a_filled_in_answer(self) -> None:
        """The honesty property, and the reason the exclusion above is correct rather than
        convenient: a field marked `consult_professional` must show the referral, never a
        value — even when a value has somehow been stored against it. Pre-filling a
        tax-residency or A1 determination would be ReloPass asserting a professional
        judgement it is not entitled to make."""
        for code in _CODES:
            determinations = [f for f in _fields(code) if f.get("consult_professional")]
            self.assertTrue(determinations, f"{code}: expected determinations")
            values = {f["id"]: f"LEAKED-{f['id']}" for f in determinations}
            body = _text(render_data_sheet(
                title=code, fields=_fields(code), values=values,
                sections=_sections(code)))
            for f in determinations:
                self.assertNotIn(f"LEAKED-{f['id']}", body,
                                 f"{code}/{f['id']}: a determination was pre-filled")
            self.assertIn("Consult a regulated professional", body, code)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

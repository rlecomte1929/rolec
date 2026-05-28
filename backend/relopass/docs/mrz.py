"""
ICAO Doc 9303 MRZ parser — pure-Python, no external dependencies.

C1-02. Deterministic primitive that parses TD3 (passport, 2×44) Machine
Readable Zones and validates every check digit via the 7-3-1 weighting in
ICAO 9303 Part 3 §4.9. Failed check digits surface as `WARN`-level
findings rather than exceptions — the Resolution UI shows the conflict and
the human decides.

Supported formats:
  - TD3: passport (2 lines × 44 characters)            — full support
  - TD2: smaller passports / ID cards (2 × 36)         — basic parse only
  - TD1: ID cards (3 × 30)                              — basic parse only

For TD1/TD2 the structural fields are extracted but check-digit validation
is limited to the document_number, dob, and expiry fields shared with TD3.

The MRZ is the authoritative source for the following identity fields:
surname, given_names, document_number, nationality_iso3, date_of_birth,
sex, expiry_date, issuing_state_iso3. Resolution against other sources
(visible inspection zone, contract, etc.) happens above this layer.

References:
  - ICAO Doc 9303 Part 3 (Consolidated):
    https://www.icao.int/sites/default/files/publications/DocSeries/9303_p3_cons_en.pdf
  - ICAO 9303 Part 3 §6: transliteration tables.

Transliteration scope (v1):
  - German set (DEU, AUT, CHE): Ä→AE, Ö→OE, Ü→UE, ß→SS
  - Scandinavian set (NOR, SWE, DNK, ISL, FIN): Å→AA, Æ→AE, Ø→OE
  - Other Latin states: NFD + Mn-strip (best-effort diacritic fold;
    round-trip not guaranteed)
  - Devanagari (Indian passports): deferred — see follow-up note in the
    Notion ticket. ISO 15919 round-trip will land in C1-02-a.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Module-level singleton: the transliteration table is loaded once. Loading
# is lazy so import time stays fast and tests can monkeypatch the path.
_TRANSLITERATION_TABLE: Optional[Dict] = None


def _load_transliteration_table() -> Dict:
    global _TRANSLITERATION_TABLE
    if _TRANSLITERATION_TABLE is not None:
        return _TRANSLITERATION_TABLE
    # Walk up from this file to find the repo root, then read data/transliteration/icao_9303.json.
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "data" / "transliteration" / "icao_9303.json"
        if candidate.is_file():
            with candidate.open("r", encoding="utf-8") as fh:
                _TRANSLITERATION_TABLE = json.load(fh)
                return _TRANSLITERATION_TABLE
    # Fallback: empty table — diacritic-fold path still works.
    _TRANSLITERATION_TABLE = {
        "german_scandinavian": {},
        "scandinavian_extras": {},
        "issuing_states_using_german_scandinavian": [],
        "issuing_states_using_scandinavian_extras": [],
    }
    return _TRANSLITERATION_TABLE


# ─────────────────────────────────────────────────────────────────────────────
# Public data classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DocumentValidationFinding:
    """A single validation observation about the parsed MRZ.

    Severities follow the broader ReloPass docs taxonomy:
      - INFO  : informational (e.g. transliteration applied)
      - WARN  : the MRZ parsed but a check digit failed or a field looks off;
                a human should confirm before relying on the value
      - ERROR : structural failure — MRZ couldn't be parsed at all
    """
    severity: str
    code: str
    field: Optional[str]
    detail: str


@dataclass(frozen=True)
class CheckDigitResult:
    """Per-field outcome of a 7-3-1 check-digit verification."""
    field: str
    expected: int
    actual: int
    passed: bool


@dataclass(frozen=True)
class MRZParseResult:
    """Structured parse result. `findings` collects all issues; `format`
    indicates which TDn shape the input matched."""
    format: str  # 'TD1' | 'TD2' | 'TD3' | 'UNKNOWN'
    surname: Optional[str] = None
    given_names: Optional[str] = None
    document_number: Optional[str] = None
    nationality_iso3: Optional[str] = None
    issuing_state_iso3: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None  # 'M' | 'F' | None
    expiry_date: Optional[date] = None
    personal_number: Optional[str] = None
    check_digits: Dict[str, CheckDigitResult] = field(default_factory=dict)
    all_check_digits_valid: bool = False
    findings: List[DocumentValidationFinding] = field(default_factory=list)
    raw_lines: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_well_formed(self) -> bool:
        """True iff the input matched a recognized TDn shape — i.e. no
        ERROR-level structural finding. WARN-level check-digit failures
        do not make a parse 'not well-formed'."""
        return self.format != "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────────
# Check digits (ICAO 9303 Part 3 §4.9)
# ─────────────────────────────────────────────────────────────────────────────

_WEIGHTS = (7, 3, 1)


def _char_value(ch: str) -> int:
    """Map a single MRZ character to its check-digit numeric value.

    Per ICAO 9303: digits 0–9 → 0–9; letters A–Z → 10–35; the filler '<' → 0.
    Unexpected characters are treated as 0 (and would typically cause the
    check digit to mismatch, surfacing as a WARN finding).
    """
    if ch == "<":
        return 0
    if "0" <= ch <= "9":
        return ord(ch) - ord("0")
    upper = ch.upper()
    if "A" <= upper <= "Z":
        return ord(upper) - ord("A") + 10
    return 0


def compute_check_digit(s: str) -> int:
    """Compute the ICAO 9303 7-3-1 check digit for a string.

    >>> compute_check_digit("L898902C3")
    6
    >>> compute_check_digit("740812")
    2
    """
    total = sum(_char_value(c) * _WEIGHTS[i % 3] for i, c in enumerate(s))
    return total % 10


# ─────────────────────────────────────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_mrz_date(yymmdd: str, *, default_century_pivot: int = 50) -> Optional[date]:
    """Convert an MRZ YYMMDD field to a calendar date.

    The 2-digit year is disambiguated against `default_century_pivot`:
    years below the pivot are 2000s, others are 1900s. The pivot of 50
    is the convention used by ICAO 9303 implementations.

    Returns None on any parse failure (invalid digits, out-of-range month/day).
    """
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy = int(yymmdd[0:2])
    mm = int(yymmdd[2:4])
    dd = int(yymmdd[4:6])
    year = 2000 + yy if yy < default_century_pivot else 1900 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Transliteration (ICAO 9303 Part 3 §6)
# ─────────────────────────────────────────────────────────────────────────────


def _reverse_transliterate(mrz_name: str, issuing_state_iso3: Optional[str]) -> str:
    """Convert an MRZ-encoded name (uppercase Latin, '<' as separator) back
    toward its display form.

    Step 1: replace '<' with space and collapse runs.
    Step 2: apply the German/Scandinavian reverse digraph map when the
            issuing state is in the relevant set.
    Step 3: title-case the result.

    Notes:
      - Round-trip for non-German/non-Scandinavian states is best-effort.
        The original diacritics are LOST in MRZ encoding, so we restore
        the ASCII-folded display form.
      - Devanagari is not handled in v1 — Indian passport MRZs that
        contain Hindi-origin names are returned as the Latin transliteration
        the issuing state encoded. ISO 15919 reverse mapping is deferred.
    """
    if not mrz_name:
        return ""
    cleaned = mrz_name.replace("<", " ").strip()
    cleaned = " ".join(cleaned.split())  # collapse runs of whitespace
    state = (issuing_state_iso3 or "").upper().strip("<")
    if not state:
        return cleaned.title()

    table = _load_transliteration_table()
    digraph_states = set(table.get("issuing_states_using_german_scandinavian", []))
    scandi_states = set(table.get("issuing_states_using_scandinavian_extras", []))

    out = cleaned
    if state in digraph_states:
        gs = table.get("german_scandinavian", {})
        # Apply longest-key-first so 'SS' doesn't get split as two 'S's
        for digraph, glyph in sorted(gs.items(), key=lambda kv: -len(kv[0])):
            out = out.replace(digraph, glyph)
    if state in scandi_states:
        sc = table.get("scandinavian_extras", {})
        out = out.replace("AA", "Å").replace("OE", "Ø").replace("AE", "Æ")
        # The sc table entries are documentation; the order above mirrors the
        # canonical Scandinavian reverse rules.
        _ = sc
    return out.title()


def fold_diacritics(text: str) -> str:
    """Strip Latin diacritics — useful for MRZ-encoding a display name
    when the issuing state has no specific reverse table.

    >>> fold_diacritics("José")
    'Jose'
    >>> fold_diacritics("Müller")
    'Muller'
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def parse_mrz(text: str, issuing_state_hint: Optional[str] = None) -> MRZParseResult:
    """Parse an MRZ string into a structured result. The string may contain
    one or more lines separated by newlines; leading/trailing whitespace is
    ignored on each line.

    `issuing_state_hint` is an ISO-3 country code used to disambiguate
    transliteration when the MRZ itself does not yet provide one (rare).

    Failed check digits do NOT raise — they emit WARN findings. Truly
    malformed input (wrong line count or length) emits an ERROR finding
    and returns a result with `format='UNKNOWN'`.
    """
    findings: List[DocumentValidationFinding] = []
    lines = tuple(l.strip() for l in text.strip().splitlines() if l.strip())

    # Format detection by line count and length.
    if len(lines) == 2 and all(len(l) == 44 for l in lines):
        return _parse_td3(lines, issuing_state_hint, findings)
    if len(lines) == 2 and all(len(l) == 36 for l in lines):
        return _parse_td2(lines, issuing_state_hint, findings)
    if len(lines) == 3 and all(len(l) == 30 for l in lines):
        return _parse_td1(lines, issuing_state_hint, findings)

    findings.append(
        DocumentValidationFinding(
            severity="ERROR",
            code="MRZ_FORMAT_UNRECOGNIZED",
            field=None,
            detail=(
                f"Could not detect TD1/TD2/TD3 — got {len(lines)} line(s) with "
                f"lengths {[len(l) for l in lines]}"
            ),
        )
    )
    return MRZParseResult(format="UNKNOWN", findings=findings, raw_lines=lines)


# ─────────────────────────────────────────────────────────────────────────────
# TD3 (passport, 2×44)
# ─────────────────────────────────────────────────────────────────────────────


def _parse_td3(
    lines: Tuple[str, ...],
    hint: Optional[str],
    findings: List[DocumentValidationFinding],
) -> MRZParseResult:
    line1, line2 = lines
    issuing = line1[2:5]
    # Document type prefix should start with P (passport). Don't fail hard;
    # surface as INFO since the rest of the structure may still be sound.
    if not line1.startswith("P"):
        findings.append(
            DocumentValidationFinding(
                severity="INFO",
                code="MRZ_TD3_NONPASSPORT_PREFIX",
                field=None,
                detail=f"Line 1 starts with {line1[0:2]!r}, expected 'P<'",
            )
        )

    # Names occupy positions 5..43 (39 chars); split on '<<'.
    name_field = line1[5:44]
    if "<<" in name_field:
        surname_raw, given_raw = name_field.split("<<", 1)
    else:
        surname_raw, given_raw = name_field, ""

    state_for_translit = issuing.strip("<") or (hint or "")
    surname = _reverse_transliterate(surname_raw, state_for_translit)
    given_names = _reverse_transliterate(given_raw, state_for_translit)

    # Line 2 fields.
    doc_num_field = line2[0:9]
    doc_cd_actual = _digit_or_minus_one(line2[9])
    nationality = line2[10:13]
    dob_raw = line2[13:19]
    dob_cd_actual = _digit_or_minus_one(line2[19])
    sex = line2[20]
    expiry_raw = line2[21:27]
    expiry_cd_actual = _digit_or_minus_one(line2[27])
    personal_field = line2[28:42]
    personal_cd_actual = _digit_or_minus_one(line2[42])
    composite_cd_actual = _digit_or_minus_one(line2[43])

    # Compute expected check digits.
    doc_cd_exp = compute_check_digit(doc_num_field)
    dob_cd_exp = compute_check_digit(dob_raw)
    expiry_cd_exp = compute_check_digit(expiry_raw)
    personal_cd_exp = compute_check_digit(personal_field)
    # Composite digest: doc_number(9) + doc_cd(1) + dob(6) + dob_cd(1) +
    # expiry(6) + expiry_cd(1) + personal(14) + personal_cd(1) = 39 chars.
    composite_input = line2[0:10] + line2[13:20] + line2[21:28] + line2[28:43]
    composite_cd_exp = compute_check_digit(composite_input)

    check_digits = {
        "document_number": CheckDigitResult(
            "document_number", doc_cd_exp, doc_cd_actual, doc_cd_actual == doc_cd_exp
        ),
        "date_of_birth": CheckDigitResult(
            "date_of_birth", dob_cd_exp, dob_cd_actual, dob_cd_actual == dob_cd_exp
        ),
        "expiry_date": CheckDigitResult(
            "expiry_date", expiry_cd_exp, expiry_cd_actual, expiry_cd_actual == expiry_cd_exp
        ),
        "personal_number": CheckDigitResult(
            "personal_number",
            personal_cd_exp,
            personal_cd_actual,
            personal_cd_actual == personal_cd_exp,
        ),
        "composite": CheckDigitResult(
            "composite", composite_cd_exp, composite_cd_actual, composite_cd_actual == composite_cd_exp
        ),
    }

    for cd_field, cd_result in check_digits.items():
        if not cd_result.passed:
            findings.append(
                DocumentValidationFinding(
                    severity="WARN",
                    code="MRZ_CHECK_DIGIT_FAIL",
                    field=cd_field,
                    detail=f"Expected {cd_result.expected}, got {cd_result.actual if cd_result.actual >= 0 else '?'}",
                )
            )

    return MRZParseResult(
        format="TD3",
        surname=surname or None,
        given_names=given_names or None,
        document_number=doc_num_field.replace("<", "") or None,
        nationality_iso3=(nationality.strip("<") or None),
        issuing_state_iso3=(issuing.strip("<") or None),
        date_of_birth=_parse_mrz_date(dob_raw),
        sex=sex if sex in ("M", "F") else None,
        expiry_date=_parse_mrz_date(expiry_raw),
        personal_number=(personal_field.replace("<", "") or None),
        check_digits=check_digits,
        all_check_digits_valid=all(r.passed for r in check_digits.values()),
        findings=findings,
        raw_lines=lines,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TD2 (2×36) and TD1 (3×30) — structural parse only
# ─────────────────────────────────────────────────────────────────────────────


def _parse_td2(
    lines: Tuple[str, ...],
    hint: Optional[str],
    findings: List[DocumentValidationFinding],
) -> MRZParseResult:
    """Basic TD2 parse: extracts the high-level fields but does not yet
    verify composite check digits. Sufficient for surface routing in v1."""
    line1, line2 = lines
    issuing = line1[2:5]
    name_field = line1[5:36]
    if "<<" in name_field:
        surname_raw, given_raw = name_field.split("<<", 1)
    else:
        surname_raw, given_raw = name_field, ""

    state_for_translit = issuing.strip("<") or (hint or "")
    surname = _reverse_transliterate(surname_raw, state_for_translit)
    given_names = _reverse_transliterate(given_raw, state_for_translit)

    doc_num_field = line2[0:9]
    doc_cd_actual = _digit_or_minus_one(line2[9])
    nationality = line2[10:13]
    dob_raw = line2[13:19]
    dob_cd_actual = _digit_or_minus_one(line2[19])
    sex = line2[20]
    expiry_raw = line2[21:27]
    expiry_cd_actual = _digit_or_minus_one(line2[27])

    doc_cd_exp = compute_check_digit(doc_num_field)
    dob_cd_exp = compute_check_digit(dob_raw)
    expiry_cd_exp = compute_check_digit(expiry_raw)
    check_digits = {
        "document_number": CheckDigitResult(
            "document_number", doc_cd_exp, doc_cd_actual, doc_cd_actual == doc_cd_exp
        ),
        "date_of_birth": CheckDigitResult(
            "date_of_birth", dob_cd_exp, dob_cd_actual, dob_cd_actual == dob_cd_exp
        ),
        "expiry_date": CheckDigitResult(
            "expiry_date", expiry_cd_exp, expiry_cd_actual, expiry_cd_actual == expiry_cd_exp
        ),
    }
    for cd_field, cd_result in check_digits.items():
        if not cd_result.passed:
            findings.append(
                DocumentValidationFinding(
                    severity="WARN",
                    code="MRZ_CHECK_DIGIT_FAIL",
                    field=cd_field,
                    detail=f"Expected {cd_result.expected}, got {cd_result.actual if cd_result.actual >= 0 else '?'}",
                )
            )

    return MRZParseResult(
        format="TD2",
        surname=surname or None,
        given_names=given_names or None,
        document_number=doc_num_field.replace("<", "") or None,
        nationality_iso3=(nationality.strip("<") or None),
        issuing_state_iso3=(issuing.strip("<") or None),
        date_of_birth=_parse_mrz_date(dob_raw),
        sex=sex if sex in ("M", "F") else None,
        expiry_date=_parse_mrz_date(expiry_raw),
        personal_number=None,
        check_digits=check_digits,
        all_check_digits_valid=all(r.passed for r in check_digits.values()),
        findings=findings,
        raw_lines=lines,
    )


def _parse_td1(
    lines: Tuple[str, ...],
    hint: Optional[str],
    findings: List[DocumentValidationFinding],
) -> MRZParseResult:
    """Basic TD1 parse: 3 lines × 30. Names are on line 3; doc-level fields
    are split between lines 1 and 2. Composite check digit deferred to a
    follow-up; the field-level digits are validated."""
    line1, line2, line3 = lines
    issuing = line1[2:5]
    doc_num_field = line1[5:14]
    doc_cd_actual = _digit_or_minus_one(line1[14])

    dob_raw = line2[0:6]
    dob_cd_actual = _digit_or_minus_one(line2[6])
    sex = line2[7]
    expiry_raw = line2[8:14]
    expiry_cd_actual = _digit_or_minus_one(line2[14])
    nationality = line2[15:18]

    name_field = line3[0:30]
    if "<<" in name_field:
        surname_raw, given_raw = name_field.split("<<", 1)
    else:
        surname_raw, given_raw = name_field, ""
    state_for_translit = issuing.strip("<") or (hint or "")
    surname = _reverse_transliterate(surname_raw, state_for_translit)
    given_names = _reverse_transliterate(given_raw, state_for_translit)

    doc_cd_exp = compute_check_digit(doc_num_field)
    dob_cd_exp = compute_check_digit(dob_raw)
    expiry_cd_exp = compute_check_digit(expiry_raw)
    check_digits = {
        "document_number": CheckDigitResult(
            "document_number", doc_cd_exp, doc_cd_actual, doc_cd_actual == doc_cd_exp
        ),
        "date_of_birth": CheckDigitResult(
            "date_of_birth", dob_cd_exp, dob_cd_actual, dob_cd_actual == dob_cd_exp
        ),
        "expiry_date": CheckDigitResult(
            "expiry_date", expiry_cd_exp, expiry_cd_actual, expiry_cd_actual == expiry_cd_exp
        ),
    }
    for cd_field, cd_result in check_digits.items():
        if not cd_result.passed:
            findings.append(
                DocumentValidationFinding(
                    severity="WARN",
                    code="MRZ_CHECK_DIGIT_FAIL",
                    field=cd_field,
                    detail=f"Expected {cd_result.expected}, got {cd_result.actual if cd_result.actual >= 0 else '?'}",
                )
            )
    return MRZParseResult(
        format="TD1",
        surname=surname or None,
        given_names=given_names or None,
        document_number=doc_num_field.replace("<", "") or None,
        nationality_iso3=(nationality.strip("<") or None),
        issuing_state_iso3=(issuing.strip("<") or None),
        date_of_birth=_parse_mrz_date(dob_raw),
        sex=sex if sex in ("M", "F") else None,
        expiry_date=_parse_mrz_date(expiry_raw),
        personal_number=None,
        check_digits=check_digits,
        all_check_digits_valid=all(r.passed for r in check_digits.values()),
        findings=findings,
        raw_lines=lines,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _digit_or_minus_one(ch: str) -> int:
    """Return the int value of a single-digit string, or -1 if not a digit.

    Used to capture check-digit slots that may contain '<' filler in some
    older MRZs — we surface that as a failed check rather than an exception.
    """
    return int(ch) if ch.isdigit() else -1

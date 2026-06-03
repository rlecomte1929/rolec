#!/usr/bin/env python3
"""Synthetic passport (TD3) generator — MRZ-valid, no real PII. (C1-17a / AIQ-512)

Generates a SPECIMEN-watermarked TD3 passport biographical page as a PDF whose
machine-readable zone (MRZ) passes ICAO 9303 check-digit validation via the
in-repo parser (``backend/relopass/docs/mrz.py``). The artefact is intentionally
and visibly marked as a test document so it can never be confused with a real
passport.

LICENCE / USAGE
---------------
For TEST FIXTURE generation only. Every page is stamped ``SPECIMEN`` /
``TEST DOCUMENT — NOT VALID FOR TRAVEL``. No real biometric photo is ever
embedded — a neutral silhouette placeholder is drawn instead. Do not use this
tool to produce documents that misrepresent themselves as genuine.

Why this exists: real passport scans cannot ethically be used as test fixtures.
This produces TD3 booklets that pass MRZ check-digit validation but carry
unmistakably synthetic data (default issuing/nationality code ``UTO`` = ICAO
test code for "Utopia").

CLI
---
    python scripts/synth_passport.py \
        --surname "SHARMA" \
        --given-names "PRIYA" \
        --dob 1992-03-14 \
        --sex F \
        --nationality IND \
        --issuing-state IND \
        --document-number L8989ABCD \
        --expiry 2032-06-30 \
        --output fixtures/pilot/priya_001/passport.pdf

Notes / deviations from the original ticket spec (documented intentionally):
  * Lives in ``scripts/`` (repo convention for standalone Python tools); the
    ticket said ``tools/`` but no such directory exists in this repo.
  * Rendered with reportlab (already a dependency) rather than Pillow, so no new
    dependency is introduced. The silhouette is drawn vectorially.
  * MRZ is rendered in Courier (bundled monospace); OCR-B is not bundled. The
    parser reads the PDF text layer, not an OCR pass, so glyph shape is moot for
    validation — the characters and check digits are exact.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Tuple

# Allow `python scripts/synth_passport.py` from the repo root to import backend.*
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.relopass.docs.mrz import compute_check_digit, fold_diacritics  # noqa: E402

# ICAO 9303 test code used when the caller does not specify a country. "UTO"
# (Utopia) is the conventional ICAO specimen code — it can never collide with a
# real ISO 3166-1 alpha-3 code.
ICAO_TEST_CODE = "UTO"

WATERMARK_TEXT = "SPECIMEN"
DISCLAIMER_TEXT = "TEST DOCUMENT — NOT VALID FOR TRAVEL"

_FILLER = "<"
_LINE_LEN = 44


# ─────────────────────────────────────────────────────────────────────────────
# MRZ construction (ICAO 9303 Part 4 — TD3)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class PassportFields:
    surname: str
    given_names: str
    date_of_birth: date
    expiry_date: date
    nationality: str = ICAO_TEST_CODE
    issuing_state: str = ICAO_TEST_CODE
    document_number: str = "SPEC0001"
    sex: str = "<"  # 'M' | 'F' | '<' (unspecified)
    personal_number: str = ""


def _translit_component(value: str) -> str:
    """Transliterate one name component into MRZ characters (A–Z and '<').

    Diacritics are folded (reusing the parser's helper so the round-trip is
    consistent), separators collapse to a single '<', and unsupported glyphs
    (apostrophes, periods) are dropped per ICAO transliteration practice.
    """
    folded = fold_diacritics(value).upper()
    cleaned_chars = []
    for ch in folded:
        if "A" <= ch <= "Z":
            cleaned_chars.append(ch)
        elif ch in " -,'.":
            cleaned_chars.append(" ")
        # any other character is dropped
    words = "".join(cleaned_chars).split()
    return _FILLER.join(words)


def _alnum_upper(value: str) -> str:
    return "".join(c for c in value.upper() if c.isalnum())


def _pad(value: str, length: int) -> str:
    """Right-pad with '<' filler, truncating if longer than `length`."""
    return (value[:length]).ljust(length, _FILLER)


def _yymmdd(d: date) -> str:
    return d.strftime("%y%m%d")


def _normalize_country(code: str) -> str:
    code = (code or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(
            f"country code must be ISO 3166-1 alpha-3 (3 letters), got {code!r}"
        )
    return code


def build_td3_mrz(fields: PassportFields) -> Tuple[str, str]:
    """Build the two 44-character TD3 MRZ lines with valid ICAO check digits.

    The byte layout matches ``_parse_td3`` in backend/relopass/docs/mrz.py
    exactly, so a generated pair round-trips with ``all_check_digits_valid``.
    """
    issuing = _normalize_country(fields.issuing_state)
    nationality = _normalize_country(fields.nationality)
    sex = fields.sex if fields.sex in ("M", "F") else _FILLER

    # ── Line 1: P< + issuing(3) + name field(39) ───────────────────────────
    surname = _translit_component(fields.surname)
    given = _translit_component(fields.given_names)
    name_field = _pad(f"{surname}{_FILLER}{_FILLER}{given}", 39)
    line1 = f"P{_FILLER}{issuing}{name_field}"
    assert len(line1) == _LINE_LEN, len(line1)

    # ── Line 2 ─────────────────────────────────────────────────────────────
    doc_field = _pad(_alnum_upper(fields.document_number), 9)
    doc_cd = compute_check_digit(doc_field)

    dob_raw = _yymmdd(fields.date_of_birth)
    dob_cd = compute_check_digit(dob_raw)

    expiry_raw = _yymmdd(fields.expiry_date)
    expiry_cd = compute_check_digit(expiry_raw)

    personal_field = _pad(_alnum_upper(fields.personal_number), 14)
    personal_cd = compute_check_digit(personal_field)

    # Composite check digit covers the same 39 chars the parser digests:
    # docnum(9)+doccd(1)+dob(6)+dobcd(1)+expiry(6)+expcd(1)+personal(14)+perscd(1)
    composite_input = (
        f"{doc_field}{doc_cd}{dob_raw}{dob_cd}{expiry_raw}{expiry_cd}"
        f"{personal_field}{personal_cd}"
    )
    composite_cd = compute_check_digit(composite_input)

    line2 = (
        f"{doc_field}{doc_cd}{nationality}{dob_raw}{dob_cd}{sex}"
        f"{expiry_raw}{expiry_cd}{personal_field}{personal_cd}{composite_cd}"
    )
    assert len(line2) == _LINE_LEN, len(line2)
    return line1, line2


# ─────────────────────────────────────────────────────────────────────────────
# PDF rendering (reportlab)
# ─────────────────────────────────────────────────────────────────────────────
def render_passport_pdf(
    fields: PassportFields, output_path: str, *, specimen: bool = True
) -> str:
    """Render the biographical page to a PDF at `output_path`. Returns the path.

    Refuses to render unless the SPECIMEN watermark will be stamped — this is a
    hard ethical guard, not a style option.
    """
    if not specimen:
        raise ValueError(
            "refusing to render: synthetic passports must carry the SPECIMEN "
            "watermark (specimen=False is not permitted)"
        )

    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    line1, line2 = build_td3_mrz(fields)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = A4
    c = canvas.Canvas(str(out), pagesize=A4)
    c.setTitle("SPECIMEN — synthetic test passport")
    c.setSubject(DISCLAIMER_TEXT)

    ink = HexColor("#1f2933")
    label = HexColor("#52606d")
    band = HexColor("#eef2f6")

    # ── Header ──────────────────────────────────────────────────────────────
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, page_h - 25 * mm, "PASSPORT / PASSEPORT")
    c.setFont("Helvetica", 9)
    c.setFillColor(label)
    c.drawString(20 * mm, page_h - 31 * mm, f"Type P · Issuing State {_normalize_country(fields.issuing_state)}")

    # ── Photo placeholder (vector silhouette, no real biometric) ─────────────
    box_x, box_y, box_w, box_h = 20 * mm, page_h - 95 * mm, 38 * mm, 50 * mm
    c.setFillColor(band)
    c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=0)
    c.setFillColor(HexColor("#9aa5b1"))
    # head
    c.circle(box_x + box_w / 2, box_y + box_h * 0.62, 8 * mm, fill=1, stroke=0)
    # shoulders
    c.ellipse(
        box_x + box_w * 0.18, box_y + 4 * mm,
        box_x + box_w * 0.82, box_y + box_h * 0.46,
        fill=1, stroke=0,
    )
    c.setFillColor(label)
    c.setFont("Helvetica", 7)
    c.drawCentredString(box_x + box_w / 2, box_y - 5 * mm, "SPECIMEN — no photo")

    # ── Biographical fields ──────────────────────────────────────────────────
    fx = 66 * mm
    fy = page_h - 45 * mm
    rows = [
        ("Surname / Nom", fields.surname),
        ("Given names / Prénoms", fields.given_names),
        ("Nationality / Nationalité", _normalize_country(fields.nationality)),
        ("Date of birth / Date de naissance", fields.date_of_birth.isoformat()),
        ("Sex / Sexe", fields.sex if fields.sex in ("M", "F") else "Unspecified"),
        ("Passport No. / N° de passeport", fields.document_number.upper()),
        ("Date of expiry / Date d'expiration", fields.expiry_date.isoformat()),
    ]
    for lbl, val in rows:
        c.setFont("Helvetica", 7.5)
        c.setFillColor(label)
        c.drawString(fx, fy, lbl.upper())
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(ink)
        c.drawString(fx, fy - 5 * mm, str(val))
        fy -= 13 * mm

    # ── SPECIMEN watermark (diagonal, always stamped) ────────────────────────
    c.saveState()
    c.setFillColor(HexColor("#d62828"))
    c.setFillAlpha(0.18)
    c.translate(page_w / 2, page_h / 2)
    c.rotate(35)
    c.setFont("Helvetica-Bold", 90)
    c.drawCentredString(0, -10 * mm, WATERMARK_TEXT)
    c.restoreState()

    # ── MRZ band ─────────────────────────────────────────────────────────────
    mrz_y = 28 * mm
    c.setFillColor(band)
    c.rect(0, mrz_y - 6 * mm, page_w, 20 * mm, fill=1, stroke=0)
    c.setFillColor(ink)
    c.setFont("Courier-Bold", 14)
    c.drawString(20 * mm, mrz_y + 6 * mm, line1)
    c.drawString(20 * mm, mrz_y - 1 * mm, line2)

    # ── Disclaimer footer ────────────────────────────────────────────────────
    c.setFillColor(HexColor("#d62828"))
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(page_w / 2, 14 * mm, DISCLAIMER_TEXT)

    c.showPage()
    c.save()
    return str(out)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # pragma: no cover - argparse surfaces the message
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a SPECIMEN-watermarked synthetic TD3 passport PDF "
        "(test fixtures only).",
    )
    p.add_argument("--surname", required=True, help="Family name")
    p.add_argument("--given-names", required=True, help="Given name(s)")
    p.add_argument("--dob", required=True, type=_parse_date, help="Date of birth YYYY-MM-DD")
    p.add_argument("--expiry", required=True, type=_parse_date, help="Expiry date YYYY-MM-DD")
    p.add_argument("--sex", default="<", choices=["M", "F", "<"], help="M / F / < (unspecified)")
    p.add_argument("--nationality", default=ICAO_TEST_CODE, help="ISO 3166-1 alpha-3 (default UTO)")
    p.add_argument("--issuing-state", default=ICAO_TEST_CODE, help="ISO 3166-1 alpha-3 (default UTO)")
    p.add_argument("--document-number", default="SPEC0001", help="Passport number")
    p.add_argument("--personal-number", default="", help="Optional personal/national number")
    p.add_argument("--output", required=True, help="Output PDF path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    fields = PassportFields(
        surname=args.surname,
        given_names=args.given_names,
        date_of_birth=args.dob,
        expiry_date=args.expiry,
        nationality=args.nationality,
        issuing_state=args.issuing_state,
        document_number=args.document_number,
        sex=args.sex,
        personal_number=args.personal_number,
    )
    path = render_passport_pdf(fields, args.output)
    line1, line2 = build_td3_mrz(fields)
    print(f"Wrote {path}")
    print("MRZ:")
    print(f"  {line1}")
    print(f"  {line2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

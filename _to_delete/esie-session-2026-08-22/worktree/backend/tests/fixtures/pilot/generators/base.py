"""
AIQ-614 — reportlab-based helpers for synthetic dossier PDF generation.

Provides:
- normalize_bbox: convert reportlab coordinates (bottom-up) to 0-1000 spec space (top-down)
- deterministic_choice: modulo arithmetic pool selection, no random.Random
- Name/employer/city pools for seeded generation
- PageLayout: thin canvas wrapper that tracks drawn text and returns bbox records
"""
from __future__ import annotations

from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Constant name/data pools
# ---------------------------------------------------------------------------

_FIRST_NAMES: List[str] = [
    "Ananya", "Priya", "Rahul", "Sophie", "Lukas",
    "Emma", "Noah", "Lena", "Felix", "Mia",
]

_PRIYA_SURNAMES: List[str] = [
    "Kapoor", "Sharma", "Patel", "Singh", "Kumar",
    "Gupta", "Mehta", "Joshi", "Rao", "Nair",
]

_EMPLOYERS: List[str] = [
    "Tech Solutions GmbH",
    "Global Innovations AG",
    "Future Systems Inc",
    "Digital Corp",
    "Smart Works Ltd",
]

_CITIES: List[str] = [
    "Berlin", "Munich", "Hamburg", "Frankfurt", "Stuttgart",
]

# ---------------------------------------------------------------------------
# FR→NO locale pools (AIQ-511) — added alongside the IN→DE pools above.
# Synthetic only; no real PII. All selection is deterministic.
# ---------------------------------------------------------------------------

#: French given names (the relocating EU worker for the FR→NO corridor)
_FR_FIRST_NAMES: List[str] = [
    "Camille", "Louis", "Hugo", "Lea", "Jules",
    "Manon", "Lucas", "Chloe", "Gabriel", "Ines",
]

#: French surnames
_FR_SURNAMES: List[str] = [
    "Martin", "Bernard", "Dubois", "Moreau", "Laurent",
    "Lefebvre", "Roux", "Girard", "Fontaine", "Rousseau",
]

#: Norwegian given names (used for Norwegian local context / spouse pools)
_NO_FIRST_NAMES: List[str] = [
    "Emma", "Nora", "Jakob", "Emil", "Sofie",
    "Oliver", "Ella", "Aksel", "Ingrid", "Henrik",
]

#: Norwegian surnames
_NO_SURNAMES: List[str] = [
    "Hansen", "Johansen", "Olsen", "Larsen", "Andersen",
    "Pedersen", "Nilsen", "Kristiansen", "Jensen", "Karlsen",
]

#: Norwegian employers (destination companies for FR→NO)
_NO_EMPLOYERS: List[str] = [
    "Nordic Tech AS",
    "Fjord Systems AS",
    "Arctic Data AS",
    "Viking Software AS",
    "Aurora Solutions AS",
]

#: Norwegian destination cities
_NO_CITIES: List[str] = [
    "Oslo", "Bergen", "Trondheim", "Stavanger", "Tromso",
]

#: Street names (corridor-agnostic, synthetic) for address fields
_STREETS: List[str] = [
    "Storgata", "Kirkegata", "Hauptstrasse", "Schillerweg", "Parkveien",
]

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def deterministic_choice(pool: List[Any], seed_offset: int, idx: int) -> Any:
    """Return pool[(seed_offset + idx) % len(pool)] — no random.Random."""
    return pool[(seed_offset + idx) % len(pool)]


def normalize_bbox(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    page_width: float,
    page_height: float,
) -> Dict[str, int]:
    """Convert reportlab bottom-up pt coords to 0-1000 top-down spec space.

    reportlab origin is bottom-left; spec origin is top-left.
    Formula:
        x_norm = round(x / page_width  * 1000)
        y_norm = round((page_height - y_top) / page_height * 1000)
    where y_top is the top edge of the bounding box (max Y in reportlab coords).
    """
    x0_n = round(x0 / page_width * 1000)
    x1_n = round(x1 / page_width * 1000)
    # In reportlab coords y1 > y0 (y grows upward); y1 is the top edge.
    y_top = max(y0, y1)
    y_bot = min(y0, y1)
    y0_n = round((page_height - y_top) / page_height * 1000)
    y1_n = round((page_height - y_bot) / page_height * 1000)
    return {"x0": x0_n, "y0": y0_n, "x1": x1_n, "y1": y1_n}


# ---------------------------------------------------------------------------
# PageLayout
# ---------------------------------------------------------------------------

#: Simple record returned by draw_text / text_bbox
BboxRecord = Dict[str, int]


class PageLayout:
    """Thin wrapper around a reportlab Canvas for a single A4 page.

    Usage::

        layout = PageLayout(output_path)
        bbox = layout.draw_text("Hello World", x=20*mm, y=270*mm, font="Helvetica", size=12)
        layout.save()
    """

    PAGE_WIDTH, PAGE_HEIGHT = A4  # 595.27 pt × 841.89 pt

    def __init__(self, output_path: str) -> None:
        self._path = output_path
        self._canvas = canvas.Canvas(output_path, pagesize=A4)

    def text_bbox(
        self, text: str, x: float, y: float, font: str, size: float
    ) -> BboxRecord:
        """Return the 0-1000 normalised bbox for *text* drawn at (x, y).

        (x, y) is the baseline origin in reportlab pt coords (bottom-left origin).
        The bbox height is approximated as `size * 1.2` points (standard line-height
        heuristic for PDF glyphs; good enough for ground-truth IoU purposes).
        """
        self._canvas.setFont(font, size)
        text_width = self._canvas.stringWidth(text, font, size)
        text_height = size * 1.2
        x0 = x
        y0 = y  # baseline → treat as bottom of glyph box
        x1 = x + text_width
        y1 = y + text_height
        return normalize_bbox(x0, y0, x1, y1, self.PAGE_WIDTH, self.PAGE_HEIGHT)

    def draw_text(
        self, text: str, x: float, y: float, font: str, size: float
    ) -> BboxRecord:
        """Draw *text* on the canvas and return its normalised bbox."""
        bbox = self.text_bbox(text, x, y, font, size)
        self._canvas.setFont(font, size)
        self._canvas.drawString(x, y, text)
        return bbox

    def save(self) -> None:
        """Finalise the page and write the PDF to disk."""
        self._canvas.showPage()
        self._canvas.save()


# ---------------------------------------------------------------------------
# Document helpers (AIQ-511) — reusable single-page doc writers
# ---------------------------------------------------------------------------


def write_national_id_pdf(
    path: str,
    *,
    surname: str,
    given_name: str,
    dob: str,
    nationality: str,
    address: str,
) -> Dict[str, BboxRecord]:
    """Write an EU/EEA national-ID stub (FR→NO uses this instead of passport+visa).

    Returns a mapping of field-key → normalised bbox for the drawn lines.
    """
    layout = PageLayout(path)
    bboxes: Dict[str, BboxRecord] = {}
    bboxes["national_id_title"] = layout.draw_text(
        "EUROPEAN UNION — NATIONAL IDENTITY CARD", 20 * mm, 280 * mm, "Helvetica-Bold", 12
    )
    bboxes["national_id_surname"] = layout.draw_text(
        f"Surname: {surname}", 20 * mm, 270 * mm, "Helvetica", 12
    )
    bboxes["national_id_given_name"] = layout.draw_text(
        f"Given name: {given_name}", 20 * mm, 260 * mm, "Helvetica", 12
    )
    bboxes["national_id_dob"] = layout.draw_text(
        f"Date of birth: {dob}", 20 * mm, 250 * mm, "Helvetica", 12
    )
    bboxes["national_id_nationality"] = layout.draw_text(
        f"Nationality: {nationality} (EU/EEA)", 20 * mm, 240 * mm, "Helvetica", 12
    )
    bboxes["national_id_address"] = layout.draw_text(
        f"Address: {address}", 20 * mm, 230 * mm, "Helvetica", 12
    )
    layout.save()
    return bboxes


def write_spouse_pdf(
    path: str,
    *,
    surname: str,
    given_name: str,
    dob: str,
    nationality: str,
    relationship: str = "Spouse",
) -> Dict[str, BboxRecord]:
    """Write a spouse / dependant stub document.

    Returns a mapping of field-key → normalised bbox for the drawn lines.
    """
    layout = PageLayout(path)
    bboxes: Dict[str, BboxRecord] = {}
    bboxes["spouse_relationship"] = layout.draw_text(
        f"Relationship: {relationship}", 20 * mm, 270 * mm, "Helvetica", 12
    )
    bboxes["spouse_surname"] = layout.draw_text(
        f"Surname: {surname}", 20 * mm, 260 * mm, "Helvetica", 12
    )
    bboxes["spouse_given_name"] = layout.draw_text(
        f"Given name: {given_name}", 20 * mm, 250 * mm, "Helvetica", 12
    )
    bboxes["spouse_dob"] = layout.draw_text(
        f"Date of birth: {dob}", 20 * mm, 240 * mm, "Helvetica", 12
    )
    bboxes["spouse_nationality"] = layout.draw_text(
        f"Nationality: {nationality}", 20 * mm, 230 * mm, "Helvetica", 12
    )
    layout.save()
    return bboxes

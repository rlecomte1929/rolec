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

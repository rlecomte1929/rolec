#!/usr/bin/env python3
"""
Write minimal PDFs for local policy assistant audit testing (repo root: docs/samples/).

Requires: pip install reportlab
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "docs" / "samples"


def main() -> int:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        print("Install reportlab: pip install reportlab", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)

    def write_pdf(path: Path, lines: list) -> None:
        c = canvas.Canvas(str(path), pagesize=letter)
        y = 750
        for line in lines:
            c.drawString(72, y, line[:120])
            y -= 16
        c.save()

    write_pdf(
        OUT / "GOPS 12102.pdf",
        [
            "Global Operations Policy Summary (sample)",
            "Relocation allowance: up to USD 2500 for assignees with two dependants.",
            "Long-term assignment mobility premium: 10 percent of base.",
            "COLA applies when cost of living differential exceeds threshold.",
            "Home leave: two round trips per assignment year for eligible families.",
        ],
    )
    write_pdf(
        OUT / "Long Term Assignment Policy Summary.pdf",
        [
            "Long Term Assignment Policy Summary (sample)",
            "Mobility premium for LTA: 12 percent for grades 8 and above.",
            "COLA: reviewed annually; applies after six months on assignment.",
            "Home leave: one economy round trip per year; two for family status A.",
            "Dependants: relocation allowance tier increases with two dependants.",
        ],
    )
    print(f"Wrote sample PDFs under {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

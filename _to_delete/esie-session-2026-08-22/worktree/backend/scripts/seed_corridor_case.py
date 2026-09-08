"""Seed one corridor case into ``rce.*`` so the StepGraph (C2-07) has data.

Idempotent: deterministic ids mean re-running is a no-op upsert. Run once per
environment.

    DATABASE_URL=postgresql://... python -m backend.scripts.seed_corridor_case

Default fixture: the Priya Sharma IN→DE EU Blue Card case (the C1-09 corridor
``IN_DE_BLUECARD_2026``), with a target arrival date so deadlines compute.
"""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from backend.app.services import corridor_registry
from backend.app.services.corridor_persistence import persist_corridor_case
from backend.relopass.corridors import load_corridor

# Stable namespace shared with corridor_persistence so the case id is reproducible.
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://relopass.com/rce")

REPO_ROOT = Path(__file__).resolve().parents[2]
# I-3 Stage 5: resolve the eligibility pathway file via the registry (single
# source for where corridor pathway specs live) rather than a hardcoded path.
CORRIDOR_PATH = corridor_registry.get_pathway_file("IN_DE", "BLUECARD_2026")

# Priya Sharma — Bengaluru SWE → Munich Blue Card (Architecture Report §4.1 demo).
PRIYA_CASE_ID = uuid.uuid5(_NS, "case:IN_DE_BLUECARD_2026:priya_sharma")
PRIYA_TARGET_ARRIVAL = date(2026, 9, 1)


def main() -> None:
    corridor = load_corridor(CORRIDOR_PATH)
    summary = persist_corridor_case(
        corridor,
        case_id=PRIYA_CASE_ID,
        target_arrival_date=PRIYA_TARGET_ARRIVAL,
        status="ACTIVE",
    )
    print(f"Seeded corridor {corridor.corridor_id} for case {PRIYA_CASE_ID}:")
    for table, n in summary.items():
        print(f"  rce.{table}: {n}")


if __name__ == "__main__":
    main()

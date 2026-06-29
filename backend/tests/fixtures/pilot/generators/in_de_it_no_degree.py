"""
AIQ-511 — IN→DE IT professional WITHOUT a diploma (experience route).

dossier_id: IN_DE_NODEG_{seed:03d}. No diploma.pdf; eligibility reflects the
Blue Card IT-specialist experience route. Deterministic; see _builder.build_dossier.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from tests.fixtures.pilot.generators._builder import Profile, build_dossier
from tests.fixtures.pilot.generators.base import (
    _CITIES,
    _EMPLOYERS,
    _FIRST_NAMES,
    _PRIYA_SURNAMES,
)

PROFILE = Profile(
    id_prefix="IN_DE_NODEG",
    corridor="IN_DE",
    persona="Indian IT professional, no degree — Blue Card experience route to Germany",
    primary_doc="passport",
    eligibility=["ELIGIBLE_BLUE_CARD_IT_EXPERIENCE"],
    given_pool=_FIRST_NAMES,
    surname_pool=_PRIYA_SURNAMES,
    employer_pool=_EMPLOYERS,
    city_pool=_CITIES,
    nationality="Indian",
    has_diploma=False,
    has_spouse=False,
)


def generate(seed: int, output_dir: Path, contradiction: Optional[str] = None) -> dict:
    """Generate one IN→DE no-degree dossier; return the ground_truth dict."""
    return build_dossier(PROFILE, seed, output_dir, contradiction)

"""
AIQ-511 — IN→DE Blue Card dossier WITH a family member (spouse).

dossier_id: IN_DE_FAM_{seed:03d}. Mirrors in_de_generic but adds a spouse.pdf
and a SPOUSE canonical entity. Deterministic; see _builder.build_dossier.
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
    id_prefix="IN_DE_FAM",
    corridor="IN_DE",
    persona="Indian Blue Card applicant relocating to Germany with spouse",
    primary_doc="passport",
    eligibility=["ELIGIBLE_BLUE_CARD"],
    given_pool=_FIRST_NAMES,
    surname_pool=_PRIYA_SURNAMES,
    employer_pool=_EMPLOYERS,
    city_pool=_CITIES,
    nationality="Indian",
    has_diploma=True,
    has_spouse=True,
    spouse_kind="non_eea",
    spouse_given_pool=_FIRST_NAMES,
    spouse_surname_pool=_PRIYA_SURNAMES,
    spouse_nationality="Indian",
)


def generate(seed: int, output_dir: Path, contradiction: Optional[str] = None) -> dict:
    """Generate one IN→DE-with-family dossier; return the ground_truth dict."""
    return build_dossier(PROFILE, seed, output_dir, contradiction)

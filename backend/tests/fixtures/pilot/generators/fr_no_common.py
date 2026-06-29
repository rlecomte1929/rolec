"""
AIQ-511 — FR→NO clean EU free-movement dossier (no family).

dossier_id: FR_NO_{seed:03d}. French (EU) national relocating to Norway. Uses an
EU national-ID document instead of passport+visa. Deterministic; see
_builder.build_dossier.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from tests.fixtures.pilot.generators._builder import Profile, build_dossier
from tests.fixtures.pilot.generators.base import (
    _FR_FIRST_NAMES,
    _FR_SURNAMES,
    _NO_CITIES,
    _NO_EMPLOYERS,
)

PROFILE = Profile(
    id_prefix="FR_NO",
    corridor="FR_NO",
    persona="French (EU) national relocating to Norway under free movement",
    primary_doc="national_id",
    eligibility=["ELIGIBLE_EU_FREE_MOVEMENT"],
    given_pool=_FR_FIRST_NAMES,
    surname_pool=_FR_SURNAMES,
    employer_pool=_NO_EMPLOYERS,
    city_pool=_NO_CITIES,
    nationality="French",
    has_diploma=False,
    has_spouse=False,
)


def generate(seed: int, output_dir: Path, contradiction: Optional[str] = None) -> dict:
    """Generate one FR→NO clean dossier; return the ground_truth dict."""
    return build_dossier(PROFILE, seed, output_dir, contradiction)

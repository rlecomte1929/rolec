"""
AIQ-511 — FR→NO worker with a FRENCH (EU) spouse.

dossier_id: FR_NO_FRSP_{seed:03d}. Both partners are French (EU) nationals; both
move under free movement. Deterministic; see _builder.build_dossier.
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
    id_prefix="FR_NO_FRSP",
    corridor="FR_NO",
    persona="French (EU) worker relocating to Norway with a French (EU) spouse",
    primary_doc="national_id",
    eligibility=["ELIGIBLE_EU_FREE_MOVEMENT"],
    given_pool=_FR_FIRST_NAMES,
    surname_pool=_FR_SURNAMES,
    employer_pool=_NO_EMPLOYERS,
    city_pool=_NO_CITIES,
    nationality="French",
    has_diploma=False,
    has_spouse=True,
    spouse_kind="eu",
    spouse_given_pool=_FR_FIRST_NAMES,
    spouse_surname_pool=_FR_SURNAMES,
    spouse_nationality="French",
)


def generate(seed: int, output_dir: Path, contradiction: Optional[str] = None) -> dict:
    """Generate one FR→NO French-spouse dossier; return the ground_truth dict."""
    return build_dossier(PROFILE, seed, output_dir, contradiction)

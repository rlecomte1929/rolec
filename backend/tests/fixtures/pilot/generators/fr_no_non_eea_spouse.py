"""
AIQ-511 — FR→NO worker with a NON-EEA spouse.

dossier_id: FR_NO_NEEA_{seed:03d}. French (EU) worker; spouse is a non-EEA
national (family reunification path). Deterministic; see _builder.build_dossier.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from tests.fixtures.pilot.generators._builder import Profile, build_dossier
from tests.fixtures.pilot.generators.base import (
    _FIRST_NAMES,
    _FR_FIRST_NAMES,
    _FR_SURNAMES,
    _NO_CITIES,
    _NO_EMPLOYERS,
    _PRIYA_SURNAMES,
)

PROFILE = Profile(
    id_prefix="FR_NO_NEEA",
    corridor="FR_NO",
    persona="French (EU) worker relocating to Norway with a non-EEA spouse",
    primary_doc="national_id",
    eligibility=["ELIGIBLE_EU_FREE_MOVEMENT"],
    given_pool=_FR_FIRST_NAMES,
    surname_pool=_FR_SURNAMES,
    employer_pool=_NO_EMPLOYERS,
    city_pool=_NO_CITIES,
    nationality="French",
    has_diploma=False,
    has_spouse=True,
    spouse_kind="non_eea",
    spouse_given_pool=_FIRST_NAMES,
    spouse_surname_pool=_PRIYA_SURNAMES,
    spouse_nationality="Indian",
)


def generate(seed: int, output_dir: Path, contradiction: Optional[str] = None) -> dict:
    """Generate one FR→NO non-EEA-spouse dossier; return the ground_truth dict."""
    return build_dossier(PROFILE, seed, output_dir, contradiction)

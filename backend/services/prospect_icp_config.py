"""
ICP (Ideal Customer Profile) configuration for the HR prospect pipeline.

Edit this file to tune who counts as a `hot` / `warm` / `nurture` /
`not_icp` prospect. The LLM enrichment service receives the human-readable
sections below as context, and the deterministic post-processor applies
the band thresholds to the model's 0..100 score.

Keep it in code (not DB) for now — once the criteria have stabilised over
two or three tuning cycles, promote to an admin-editable DB row.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class IcpConfig:
    # Human prose fed to the LLM so it understands the qualification rubric.
    mission_summary: str
    target_size_bands: List[str]
    target_sectors: List[str]
    target_regions: List[str]
    strong_signals: List[str]
    weak_signals: List[str]
    disqualifiers: List[str]
    contact_titles: List[str]
    # Thresholds applied deterministically to the LLM's 0..100 icp_score
    # after it returns. Inclusive lower bounds.
    band_thresholds: Dict[str, int] = field(
        default_factory=lambda: {"hot": 75, "warm": 55, "nurture": 30}
    )


ICP_CONFIG = IcpConfig(
    mission_summary=(
        "ReloPass is an international relocation operations platform for "
        "small and mid-market companies that move employees across borders "
        "and want to replace spreadsheets + disconnected vendors with a "
        "single structured workflow."
    ),
    target_size_bands=[
        "50-250 employees",
        "250-1000 employees",
        "1000-5000 employees",
    ],
    target_sectors=[
        "Technology / SaaS",
        "Engineering & R&D",
        "Professional services / consulting",
        "Life sciences / pharma",
        "Financial services",
        "Manufacturing with global footprint",
    ],
    target_regions=[
        "Europe (especially France, UK, Germany, Netherlands, Nordics)",
        "APAC hubs (Singapore, Hong Kong)",
        "Middle East (UAE)",
        "North America (when expanding into EMEA)",
    ],
    strong_signals=[
        "Active job postings mentioning 'relocation', 'visa sponsorship', "
        "'international assignment', or 'expat package'",
        "Recent announcement of a new international office, legal entity, "
        "or market expansion",
        "Recent funding round with explicit 'international hiring' or "
        "'global expansion' language",
        "Public-facing Head of Global Mobility / International HR role",
        "Multi-country careers page or localised hiring landing pages",
    ],
    weak_signals=[
        "Headcount growing >30% YoY",
        "Offices or subsidiaries in 3+ countries",
        "Careers page mentions 'global team' / 'work from anywhere'",
        "Member of industry bodies (EuRA, Worldwide ERC, FIDI)",
    ],
    disqualifiers=[
        "Fewer than 25 employees and no mention of international hiring",
        "Single-country business with no expansion signals",
        "Primary activity is itself a relocation services / immigration "
        "firm (those are suppliers, not prospects)",
        "Staffing / PEO / EOR providers (Remote, Deel, Oyster, etc.)",
    ],
    contact_titles=[
        "Head of Global Mobility",
        "Global Mobility Manager",
        "International HR Director",
        "Head of People",
        "Chief People Officer",
        "People Operations Lead",
        "Head of Total Rewards",
    ],
)


def config_as_prompt_block() -> str:
    """Render the ICP config as a single text block for the LLM prompt."""
    cfg = ICP_CONFIG
    parts = [
        f"MISSION: {cfg.mission_summary}",
        "TARGET COMPANY SIZE BANDS:\n- " + "\n- ".join(cfg.target_size_bands),
        "TARGET SECTORS:\n- " + "\n- ".join(cfg.target_sectors),
        "TARGET REGIONS:\n- " + "\n- ".join(cfg.target_regions),
        "STRONG POSITIVE SIGNALS (increase score):\n- " + "\n- ".join(cfg.strong_signals),
        "WEAK POSITIVE SIGNALS (small boost):\n- " + "\n- ".join(cfg.weak_signals),
        "DISQUALIFIERS (force score below 30):\n- " + "\n- ".join(cfg.disqualifiers),
        "PREFERRED CONTACT TITLES (rank in this order):\n- "
        + "\n- ".join(cfg.contact_titles),
    ]
    return "\n\n".join(parts)


def band_for_score(score: int | None) -> str:
    if score is None:
        return "not_icp"
    t = ICP_CONFIG.band_thresholds
    if score >= t["hot"]:
        return "hot"
    if score >= t["warm"]:
        return "warm"
    if score >= t["nurture"]:
        return "nurture"
    return "not_icp"

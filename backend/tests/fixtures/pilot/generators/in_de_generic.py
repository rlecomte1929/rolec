"""
AIQ-614 — Seed-driven generator for the IN→DE Blue Card pilot corpus.

Each call to generate(seed, output_dir) produces one dossier directory containing:
  - 6 minimal 1-page PDF stubs (passport, employment_contract, payslip_01-03, diploma)
  - ground_truth.json  (full Dossier model)
  - generation.json    (GenerationMeta sidecar)

All data is derived deterministically from `seed`; no random.Random is used.
The IN_DE_001 fixture (seed=1) is the canonical reference dossier.

Usage::

    cd backend && python -m eval.<module_name> --corpus tests/fixtures/pilot/
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict

from reportlab.lib.units import mm

from tests.fixtures.pilot.generators.base import (
    PageLayout,
    _CITIES,
    _EMPLOYERS,
    _FIRST_NAMES,
    _PRIYA_SURNAMES,
    deterministic_choice,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DOB_YEARS = list(range(1980, 1996))  # 16 options keeps pool compact
_SALARY_BASE = [3500, 4000, 4500, 5000, 5200, 5800, 6000, 6500, 7000, 7500]
_DIPLOMA_FIELDS = [
    "Computer Science",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Information Technology",
    "Data Science",
    "Software Engineering",
    "Business Informatics",
    "Mathematics",
    "Physics",
    "Biotechnology",
]


def _make_dossier_id(seed: int) -> str:
    return f"IN_DE_{seed:03d}"


def _generate_pdfs(
    output_dir: Path,
    given_name: str,
    surname: str,
    dob: str,
    employer: str,
    salary: int,
    diploma_field: str,
) -> Dict[str, Dict]:
    """Generate all 6 PDF stubs and return a mapping of doc_key → bboxes dict."""
    bboxes: Dict[str, Dict] = {}

    # --- passport ---
    path = str(output_dir / "passport.pdf")
    layout = PageLayout(path)
    bboxes["passport_surname"] = layout.draw_text(
        f"Surname: {surname}", 20 * mm, 270 * mm, "Helvetica", 12
    )
    bboxes["passport_given_name"] = layout.draw_text(
        f"Given name: {given_name}", 20 * mm, 260 * mm, "Helvetica", 12
    )
    bboxes["passport_dob"] = layout.draw_text(
        f"Date of birth: {dob}", 20 * mm, 250 * mm, "Helvetica", 12
    )
    layout.save()

    # --- employment_contract ---
    path = str(output_dir / "employment_contract.pdf")
    layout = PageLayout(path)
    bboxes["contract_employer"] = layout.draw_text(
        f"Employer: {employer}", 20 * mm, 270 * mm, "Helvetica", 12
    )
    bboxes["contract_salary"] = layout.draw_text(
        f"Monthly salary: EUR {salary}", 20 * mm, 260 * mm, "Helvetica", 12
    )
    layout.save()

    # --- payslips (3 months) ---
    for i in range(1, 4):
        path = str(output_dir / f"payslip_0{i}.pdf")
        layout = PageLayout(path)
        bboxes[f"payslip_{i:02d}_employer"] = layout.draw_text(
            f"Employer: {employer}", 20 * mm, 270 * mm, "Helvetica", 12
        )
        bboxes[f"payslip_{i:02d}_salary"] = layout.draw_text(
            f"Net salary: EUR {salary}", 20 * mm, 260 * mm, "Helvetica", 12
        )
        layout.save()

    # --- diploma ---
    path = str(output_dir / "diploma.pdf")
    layout = PageLayout(path)
    bboxes["diploma_field"] = layout.draw_text(
        f"Field of study: {diploma_field}", 20 * mm, 270 * mm, "Helvetica", 12
    )
    bboxes["diploma_name"] = layout.draw_text(
        f"Graduate: {given_name} {surname}", 20 * mm, 260 * mm, "Helvetica", 12
    )
    layout.save()

    return bboxes


def generate(seed: int, output_dir: Path) -> dict:
    """Generate one IN→DE Blue Card dossier into *output_dir*.

    Creates the directory if it does not exist, writes all PDF stubs,
    ground_truth.json, and generation.json. Returns the ground_truth dict.
    """
    dossier_id = _make_dossier_id(seed)
    dossier_path = Path(output_dir) / dossier_id
    dossier_path.mkdir(parents=True, exist_ok=True)

    # Deterministic data selection
    given_name: str = deterministic_choice(_FIRST_NAMES, seed, 0)
    surname: str = deterministic_choice(_PRIYA_SURNAMES, seed, 1)
    employer: str = deterministic_choice(_EMPLOYERS, seed, 2)
    city: str = deterministic_choice(_CITIES, seed, 3)
    salary: int = deterministic_choice(_SALARY_BASE, seed, 4)
    diploma_field: str = deterministic_choice(_DIPLOMA_FIELDS, seed, 5)
    dob_year: int = deterministic_choice(_DOB_YEARS, seed, 6)
    # Simple deterministic dob
    dob_month = (seed % 12) + 1
    dob_day = (seed % 28) + 1
    dob = date(dob_year, dob_month, dob_day).isoformat()

    bboxes = _generate_pdfs(
        dossier_path, given_name, surname, dob, employer, salary, diploma_field
    )

    # Build ground_truth structure using plain dicts (no Pydantic import needed at
    # generation time — keeps this module importable without the eval package on path)
    def _bbox(key: str) -> dict:
        b = bboxes[key]
        return {"x0": b["x0"], "y0": b["y0"], "x1": b["x1"], "y1": b["y1"]}

    generation_meta = {
        "dossier_id": dossier_id,
        "seed": seed,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schema_version": "1.0",
    }

    extracted_fields = [
        {
            "field_key": "surname",
            "value": surname,
            "bbox": _bbox("passport_surname"),
            "confidence": 1.0,
        },
        {
            "field_key": "given_name",
            "value": given_name,
            "bbox": _bbox("passport_given_name"),
            "confidence": 1.0,
        },
        {
            "field_key": "dob",
            "value": dob,
            "bbox": _bbox("passport_dob"),
            "confidence": 1.0,
        },
        {
            "field_key": "employer_name",
            "value": employer,
            "bbox": _bbox("contract_employer"),
            "confidence": 1.0,
        },
        {
            "field_key": "monthly_salary_eur",
            "value": str(salary),
            "bbox": _bbox("contract_salary"),
            "confidence": 1.0,
        },
        {
            "field_key": "diploma_field",
            "value": diploma_field,
            "bbox": _bbox("diploma_field"),
            "confidence": 1.0,
        },
    ]

    ground_truth = {
        "dossier_id": dossier_id,
        "extracted_fields": extracted_fields,
        "canonical_entities": [
            {
                "entity_type": "PERSON",
                "canonical_value": f"{given_name} {surname}",
                "source_field_keys": ["given_name", "surname"],
            },
            {
                "entity_type": "EMPLOYER",
                "canonical_value": employer,
                "source_field_keys": ["employer_name"],
            },
            {
                "entity_type": "SALARY_EUR",
                "canonical_value": str(salary),
                "source_field_keys": ["monthly_salary_eur"],
            },
        ],
        "eligibility_verdict": {
            "outcome_set": ["ELIGIBLE_BLUE_CARD"],
            "citations": [],
        },
        "step_graph": {
            "steps": [
                {
                    "step_id": "collect_passport",
                    "description": "Collect valid passport",
                    "required": True,
                    "order": 1,
                },
                {
                    "step_id": "collect_employment_contract",
                    "description": "Collect signed employment contract",
                    "required": True,
                    "order": 2,
                },
                {
                    "step_id": "collect_diploma",
                    "description": "Collect recognised diploma",
                    "required": True,
                    "order": 3,
                },
            ]
        },
        "seeded_contradictions": [],
        "generation_meta": generation_meta,
        "meta": {
            "city": city,
        },
    }

    # Write files
    with open(dossier_path / "ground_truth.json", "w", encoding="utf-8") as fh:
        json.dump(ground_truth, fh, indent=2, ensure_ascii=False)

    with open(dossier_path / "generation.json", "w", encoding="utf-8") as fh:
        json.dump(generation_meta, fh, indent=2, ensure_ascii=False)

    return ground_truth

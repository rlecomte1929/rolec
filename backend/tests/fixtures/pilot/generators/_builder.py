"""
AIQ-511 — Shared deterministic dossier builder for the C1 pilot corpus.

The five new generator modules (in_de_with_family, in_de_it_no_degree,
fr_no_common, fr_no_non_eea_spouse, fr_no_french_spouse) are thin wrappers
around :func:`build_dossier`. They differ only by a :class:`Profile`.

The output mirrors ``in_de_generic.generate`` precisely — each call writes a
``<dossier_id>/`` directory containing the PDF stubs, ``ground_truth.json`` and
``generation.json``, and returns the ground_truth dict.

Everything is derived deterministically from ``seed`` via
``deterministic_choice`` / modulo arithmetic. The single non-deterministic field
is ``generation_meta.generated_at`` (``datetime.utcnow``), exactly as in
``in_de_generic``.

Contradiction seeding: pass ``contradiction`` as one of the five canonical types
to introduce exactly one real inconsistency into the documents and record it in
``seeded_contradictions``:

    SURNAME_MISMATCH  — passport/national-id surname != diploma graduate surname
    DOB_MISMATCH      — passport/national-id dob != employment-contract dob
    EMPLOYER_MISMATCH — employment-contract employer != payslip employer
    SALARY_MISMATCH   — employment-contract salary != payslip salary
    ADDRESS_MISMATCH  — primary-id address != employment-contract address
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib.units import mm

from tests.fixtures.pilot.generators.base import (
    PageLayout,
    deterministic_choice,
    write_national_id_pdf,
    write_spouse_pdf,
)

# Canonical contradiction types (mirrors test_10 in test_schema.py).
CONTRADICTION_TYPES: List[str] = [
    "SURNAME_MISMATCH",
    "DOB_MISMATCH",
    "EMPLOYER_MISMATCH",
    "SALARY_MISMATCH",
    "ADDRESS_MISMATCH",
]

_DOB_YEARS = list(range(1980, 1996))  # 16 options keeps the pool compact
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
_STREET_NUMBERS = [12, 27, 34, 48, 56, 63, 71, 88, 95, 104]


@dataclass
class Profile:
    """Static description of a dossier archetype."""

    id_prefix: str            # e.g. "IN_DE_FAM"
    corridor: str             # "IN_DE" | "FR_NO"
    persona: str              # human-readable persona description
    primary_doc: str          # "passport" | "national_id"
    eligibility: List[str]    # eligibility_verdict.outcome_set
    given_pool: List[str] = field(default_factory=list)
    surname_pool: List[str] = field(default_factory=list)
    employer_pool: List[str] = field(default_factory=list)
    city_pool: List[str] = field(default_factory=list)
    nationality: str = ""     # primary applicant nationality
    has_diploma: bool = True
    has_spouse: bool = False
    spouse_kind: Optional[str] = None  # "eu" | "non_eea"
    # spouse name pools (only used when has_spouse)
    spouse_given_pool: List[str] = field(default_factory=list)
    spouse_surname_pool: List[str] = field(default_factory=list)
    spouse_nationality: str = ""


def _distinct_choice(pool: List, seed: int, idx: int, avoid) -> object:
    """Deterministically pick a pool entry that is != *avoid*."""
    for step in range(len(pool)):
        candidate = deterministic_choice(pool, seed, idx + step)
        if candidate != avoid:
            return candidate
    return avoid  # pool had a single value; cannot differ


def _bbox(bboxes: Dict[str, Dict], key: str) -> dict:
    b = bboxes[key]
    return {"x0": b["x0"], "y0": b["y0"], "x1": b["x1"], "y1": b["y1"]}


def build_dossier(
    profile: Profile,
    seed: int,
    output_dir: Path,
    contradiction: Optional[str] = None,
) -> dict:
    """Build one dossier for *profile* / *seed* into *output_dir*; return ground_truth."""
    if contradiction is not None and contradiction not in CONTRADICTION_TYPES:
        raise ValueError(f"Unknown contradiction type: {contradiction!r}")

    dossier_id = f"{profile.id_prefix}_{seed:03d}"
    dossier_path = Path(output_dir) / dossier_id
    dossier_path.mkdir(parents=True, exist_ok=True)

    # --- deterministic primary data ---
    given_name = deterministic_choice(profile.given_pool, seed, 0)
    surname = deterministic_choice(profile.surname_pool, seed, 1)
    employer = deterministic_choice(profile.employer_pool, seed, 2)
    city = deterministic_choice(profile.city_pool, seed, 3)
    salary = deterministic_choice(_SALARY_BASE, seed, 4)
    diploma_field = deterministic_choice(_DIPLOMA_FIELDS, seed, 5)
    dob_year = deterministic_choice(_DOB_YEARS, seed, 6)
    street = deterministic_choice(["Storgata", "Kirkegata", "Hauptstrasse", "Schillerweg", "Parkveien"], seed, 7)
    street_no = deterministic_choice(_STREET_NUMBERS, seed, 8)
    dob = date(dob_year, (seed % 12) + 1, (seed % 28) + 1).isoformat()
    address = f"{street_no} {street}, {city}"

    # --- secondary (doc-to-doc) values; default identical to primary ---
    diploma_surname = surname
    contract_dob = dob
    payslip_employer = employer
    payslip_salary = salary
    contract_address = address

    seeded_contradictions: List[dict] = []
    primary_pdf = f"{profile.primary_doc}.pdf"

    if contradiction == "SURNAME_MISMATCH":
        diploma_surname = _distinct_choice(profile.surname_pool, seed, 1, surname)
        seeded_contradictions.append({
            "contradiction_type": "SURNAME_MISMATCH",
            "field_key": "surname",
            "affected_documents": [primary_pdf, "diploma.pdf"],
        })
    elif contradiction == "DOB_MISMATCH":
        alt_year = dob_year + 1 if dob_year < 1995 else dob_year - 1
        contract_dob = date(alt_year, (seed % 12) + 1, (seed % 28) + 1).isoformat()
        seeded_contradictions.append({
            "contradiction_type": "DOB_MISMATCH",
            "field_key": "dob",
            "affected_documents": [primary_pdf, "employment_contract.pdf"],
        })
    elif contradiction == "EMPLOYER_MISMATCH":
        payslip_employer = _distinct_choice(profile.employer_pool, seed, 2, employer)
        seeded_contradictions.append({
            "contradiction_type": "EMPLOYER_MISMATCH",
            "field_key": "employer_name",
            "affected_documents": ["employment_contract.pdf", "payslip_01.pdf"],
        })
    elif contradiction == "SALARY_MISMATCH":
        payslip_salary = salary + 500
        seeded_contradictions.append({
            "contradiction_type": "SALARY_MISMATCH",
            "field_key": "monthly_salary_eur",
            "affected_documents": ["employment_contract.pdf", "payslip_01.pdf"],
        })
    elif contradiction == "ADDRESS_MISMATCH":
        alt_city = _distinct_choice(profile.city_pool, seed, 3, city)
        alt_no = _distinct_choice(_STREET_NUMBERS, seed, 8, street_no)
        contract_address = f"{alt_no} {street}, {alt_city}"
        seeded_contradictions.append({
            "contradiction_type": "ADDRESS_MISMATCH",
            "field_key": "address",
            "affected_documents": [primary_pdf, "employment_contract.pdf"],
        })

    bboxes: Dict[str, Dict] = {}

    # --- primary identity document ---
    if profile.primary_doc == "national_id":
        nid = write_national_id_pdf(
            str(dossier_path / "national_id.pdf"),
            surname=surname,
            given_name=given_name,
            dob=dob,
            nationality=profile.nationality,
            address=address,
        )
        bboxes["surname"] = nid["national_id_surname"]
        bboxes["given_name"] = nid["national_id_given_name"]
        bboxes["dob"] = nid["national_id_dob"]
        bboxes["address"] = nid["national_id_address"]
    else:
        layout = PageLayout(str(dossier_path / "passport.pdf"))
        bboxes["surname"] = layout.draw_text(f"Surname: {surname}", 20 * mm, 270 * mm, "Helvetica", 12)
        bboxes["given_name"] = layout.draw_text(f"Given name: {given_name}", 20 * mm, 260 * mm, "Helvetica", 12)
        bboxes["dob"] = layout.draw_text(f"Date of birth: {dob}", 20 * mm, 250 * mm, "Helvetica", 12)
        bboxes["address"] = layout.draw_text(f"Address: {address}", 20 * mm, 240 * mm, "Helvetica", 12)
        layout.save()

    # --- employment contract ---
    layout = PageLayout(str(dossier_path / "employment_contract.pdf"))
    bboxes["employer_name"] = layout.draw_text(f"Employer: {employer}", 20 * mm, 270 * mm, "Helvetica", 12)
    bboxes["monthly_salary_eur"] = layout.draw_text(f"Monthly salary: EUR {salary}", 20 * mm, 260 * mm, "Helvetica", 12)
    layout.draw_text(f"Work address: {contract_address}", 20 * mm, 250 * mm, "Helvetica", 12)
    if contradiction == "DOB_MISMATCH":
        layout.draw_text(f"Date of birth: {contract_dob}", 20 * mm, 240 * mm, "Helvetica", 12)
    layout.save()

    # --- payslips (3 months) ---
    for i in range(1, 4):
        layout = PageLayout(str(dossier_path / f"payslip_0{i}.pdf"))
        layout.draw_text(f"Employer: {payslip_employer}", 20 * mm, 270 * mm, "Helvetica", 12)
        layout.draw_text(f"Net salary: EUR {payslip_salary}", 20 * mm, 260 * mm, "Helvetica", 12)
        layout.save()

    # --- diploma (only when the profile has one) ---
    if profile.has_diploma:
        layout = PageLayout(str(dossier_path / "diploma.pdf"))
        bboxes["diploma_field"] = layout.draw_text(
            f"Field of study: {diploma_field}", 20 * mm, 270 * mm, "Helvetica", 12
        )
        layout.draw_text(f"Graduate: {given_name} {diploma_surname}", 20 * mm, 260 * mm, "Helvetica", 12)
        layout.save()

    # --- spouse / dependant document ---
    spouse_entity = None
    if profile.has_spouse:
        sp_given = deterministic_choice(profile.spouse_given_pool, seed, 10)
        sp_surname = deterministic_choice(profile.spouse_surname_pool, seed, 11)
        sp_year = deterministic_choice(_DOB_YEARS, seed, 12)
        sp_dob = date(sp_year, (seed % 12) + 1, ((seed + 3) % 28) + 1).isoformat()
        write_spouse_pdf(
            str(dossier_path / "spouse.pdf"),
            surname=sp_surname,
            given_name=sp_given,
            dob=sp_dob,
            nationality=profile.spouse_nationality,
            relationship="Spouse",
        )
        spouse_entity = {
            "entity_type": "SPOUSE",
            "canonical_value": f"{sp_given} {sp_surname}",
            "source_field_keys": ["spouse_name"],
        }

    # --- ground truth assembly ---
    generation_meta = {
        "dossier_id": dossier_id,
        "seed": seed,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schema_version": "1.0",
    }

    extracted_fields = [
        {"field_key": "surname", "value": surname, "bbox": _bbox(bboxes, "surname"), "confidence": 1.0},
        {"field_key": "given_name", "value": given_name, "bbox": _bbox(bboxes, "given_name"), "confidence": 1.0},
        {"field_key": "dob", "value": dob, "bbox": _bbox(bboxes, "dob"), "confidence": 1.0},
        {"field_key": "address", "value": address, "bbox": _bbox(bboxes, "address"), "confidence": 1.0},
        {"field_key": "employer_name", "value": employer, "bbox": _bbox(bboxes, "employer_name"), "confidence": 1.0},
        {"field_key": "monthly_salary_eur", "value": str(salary), "bbox": _bbox(bboxes, "monthly_salary_eur"), "confidence": 1.0},
    ]
    if profile.has_diploma:
        extracted_fields.append(
            {"field_key": "diploma_field", "value": diploma_field, "bbox": _bbox(bboxes, "diploma_field"), "confidence": 1.0}
        )

    canonical_entities = [
        {"entity_type": "PERSON", "canonical_value": f"{given_name} {surname}", "source_field_keys": ["given_name", "surname"]},
        {"entity_type": "EMPLOYER", "canonical_value": employer, "source_field_keys": ["employer_name"]},
        {"entity_type": "SALARY_EUR", "canonical_value": str(salary), "source_field_keys": ["monthly_salary_eur"]},
    ]
    if spouse_entity is not None:
        canonical_entities.append(spouse_entity)

    # --- step graph (corridor / profile specific) ---
    steps: List[dict] = []
    order = 1
    if profile.primary_doc == "national_id":
        steps.append({"step_id": "collect_national_id", "description": "Collect EU/EEA national identity document", "required": True, "order": order}); order += 1
        steps.append({"step_id": "register_residence", "description": "Register residence under EU free movement", "required": True, "order": order}); order += 1
    else:
        steps.append({"step_id": "collect_passport", "description": "Collect valid passport", "required": True, "order": order}); order += 1
    steps.append({"step_id": "collect_employment_contract", "description": "Collect signed employment contract", "required": True, "order": order}); order += 1
    if profile.has_diploma:
        steps.append({"step_id": "collect_diploma", "description": "Collect recognised diploma", "required": True, "order": order}); order += 1
    else:
        steps.append({"step_id": "collect_experience_evidence", "description": "Collect IT professional experience evidence (no degree route)", "required": True, "order": order}); order += 1
    if profile.has_spouse:
        steps.append({"step_id": "collect_spouse_document", "description": "Collect spouse / dependant documentation", "required": True, "order": order}); order += 1

    ground_truth = {
        "dossier_id": dossier_id,
        "extracted_fields": extracted_fields,
        "canonical_entities": canonical_entities,
        "eligibility_verdict": {"outcome_set": list(profile.eligibility), "citations": []},
        "step_graph": {"steps": steps},
        "seeded_contradictions": seeded_contradictions,
        "generation_meta": generation_meta,
        "meta": {
            "corridor": profile.corridor,
            "persona": profile.persona,
            "city": city,
        },
    }

    with open(dossier_path / "ground_truth.json", "w", encoding="utf-8") as fh:
        json.dump(ground_truth, fh, indent=2, ensure_ascii=False)
    with open(dossier_path / "generation.json", "w", encoding="utf-8") as fh:
        json.dump(generation_meta, fh, indent=2, ensure_ascii=False)

    return ground_truth

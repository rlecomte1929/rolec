from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, Any

from .db import SessionLocal
from . import crud
from .services.research import run_country_research


def seed_demo_cases() -> None:
    cases = [
        {
            "id": "case-oslo-sg-family",
            "draft": _case_draft(
                origin_country="Norway",
                origin_city="Oslo",
                dest_country="Singapore",
                dest_city="Singapore",
                purpose="employment",
                target_move_date="2024-12-01",
                has_dependents=True,
                spouse_work=True,
                kids_school_age=True,
            ),
        },
        {
            "id": "case-sg-ny-single",
            "draft": _case_draft(
                origin_country="Singapore",
                origin_city="Singapore",
                dest_country="United States",
                dest_city="New York",
                purpose="employment",
                target_move_date="2024-11-05",
                has_dependents=False,
            ),
        },
        {
            "id": "case-eu-sg-couple",
            "draft": _case_draft(
                origin_country="Germany",
                origin_city="Berlin",
                dest_country="Singapore",
                dest_city="Singapore",
                purpose="employment",
                target_move_date="2025-01-15",
                has_dependents=True,
                spouse_work=False,
            ),
        },
    ]

    with SessionLocal() as db:
        for case in cases:
            existing = crud.get_case(db, case["id"])
            if existing:
                continue
            crud.create_case(db, case["id"], case["draft"])

    # Seed country requirements for destinations
    for country in {case["draft"]["relocationBasics"]["destCountry"] for case in cases}:
        run_country_research(country, "employment", {})


def _case_draft(
    origin_country: str,
    origin_city: str,
    dest_country: str,
    dest_city: str,
    purpose: str,
    target_move_date: str,
    has_dependents: bool,
    spouse_work: bool = False,
    kids_school_age: bool = False,
) -> Dict[str, Any]:
    return {
        "relocationBasics": {
            "originCountry": origin_country,
            "originCity": origin_city,
            "destCountry": dest_country,
            "destCity": dest_city,
            "purpose": purpose,
            "targetMoveDate": target_move_date,
            "durationMonths": 12,
            "hasDependents": has_dependents,
        },
        "employeeProfile": {
            "fullName": "Demo Employee",
            "nationality": "Norwegian",
            "passportCountry": origin_country,
            "passportExpiry": "2026-10-01",
            "residenceCountry": origin_country,
            "email": "demo.employee@relopass.local",
        },
        "familyMembers": {
            "maritalStatus": "married" if has_dependents else "single",
            "spouse": {
                "fullName": "Partner Demo" if has_dependents else None,
                "relationship": "spouse",
                "nationality": origin_country,
                "dateOfBirth": "1990-05-05",
                "wantsToWork": spouse_work,
            },
            "children": [
                {
                    "fullName": "Child One",
                    "relationship": "child",
                    "nationality": origin_country,
                    "dateOfBirth": "2015-04-01",
                },
                {
                    "fullName": "Child Two",
                    "relationship": "child",
                    "nationality": origin_country,
                    "dateOfBirth": "2017-08-12",
                },
            ] if kids_school_age else [],
        },
        "assignmentContext": {
            "employerName": "Global Tech",
            "employerCountry": origin_country,
            "workLocation": dest_city,
            "contractStartDate": "2024-11-15",
            "contractType": "assignment",
            "salaryBand": "120k-150k",
            "jobTitle": "Project Manager",
            "seniorityBand": "L2",
        },
    }

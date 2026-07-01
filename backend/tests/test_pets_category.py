"""Pets is registered as a first-class recommendation category.

Guards the registration so `pets` flows through everything that reads the plugin
registry (HR vendor curation, the catalog scraper/populate loop, admin coverage queue)
and the per-category question bank. Pure imports — no DB.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def test_pets_in_registry_and_categories():
    from backend.app.recommendations.registry import list_categories, _REGISTRY
    keys = {c["key"] for c in list_categories()}
    assert "pets" in keys, f"pets must be a registered category; got {sorted(keys)}"
    plug = _REGISTRY["pets"]
    assert plug.title == "Pets"
    # instantiable contract: dataset loads, criteria + score run without error
    assert isinstance(plug.load_dataset(), list)
    r = plug.score(plug.CriteriaModel(), {"name": "X", "rating": 4.0, "availability_level": "high"})
    assert "score_raw" in r


def test_pets_questions_registered():
    from backend.app.services.question_schema import get_questions_for_services
    qs = [q.question_key for q in get_questions_for_services(["pets"])]
    assert qs == ["pet_species", "pet_count", "pet_specific_needs"], qs


def test_pets_in_recommendation_whitelists():
    from backend.app.recommendations.criteria_builder import SERVICE_KEY_TO_BACKEND
    assert SERVICE_KEY_TO_BACKEND.get("pets") == "pets"

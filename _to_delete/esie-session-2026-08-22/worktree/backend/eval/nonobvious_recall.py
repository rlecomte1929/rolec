"""
Non-obvious requirement recall, sliced per (corridor x employee_type).

Replaces the retired aggregate 'corridor completeness %' (the old
``roadmap_completeness`` dashboard metric). Data-centric AI principle (Ng MLOps
C1 W2-3): an aggregate average hides rare-slice failures, and the rare missed
non-obvious requirement is exactly the failure ('the week-seven ambush') the
product exists to kill. So this module:

  - scores recall per slice against a lawyer-verified Human-Level-Performance
    (HLP) baseline (``hlp_nonobvious_baseline.json``):
        recall = non_obvious_requirements_correctly_served
                 / total_lawyer_verified_non_obvious_requirements
  - NEVER averages across slices \u2014 the headline number is the WORST slice,
    and slices are always reported worst-first;
  - counts a requirement as served only when it appears in EVERY produced
    roadmap for the slice, so a single missed requirement in a single case
    visibly lowers that slice (and only that slice).

A produced roadmap is a list of steps; a requirement is served by a roadmap
when the baseline ``match`` substring appears (case-insensitive) in some step
title \u2014 the same matching contract as ``roadmap_metrics.score_roadmap``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_BASELINE_PATH = Path(__file__).resolve().parent / "hlp_nonobvious_baseline.json"


def slice_id(corridor: str, employee_type: str) -> str:
    """Canonical slice identifier, e.g. ``FR_NO:eu_national``."""
    return f"{corridor}:{employee_type}"


def load_baseline(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the HLP baseline. Fails loudly on a malformed file \u2014 a silent
    fallback here would let recall be measured against nothing."""
    baseline = json.loads((path or DEFAULT_BASELINE_PATH).read_text(encoding="utf-8"))
    slices = baseline.get("slices")
    if not isinstance(slices, list) or not slices:
        raise ValueError("HLP baseline has no slices")
    for s in slices:
        if not s.get("corridor") or not s.get("employee_type"):
            raise ValueError("HLP baseline slice missing corridor/employee_type")
        if not s.get("requirements"):
            raise ValueError(f"HLP baseline slice {slice_id(s.get('corridor', '?'), s.get('employee_type', '?'))} has no requirements")
    return baseline


def _roadmap_titles(steps: List[Dict[str, Any]]) -> List[str]:
    return [str(s.get("title") or "").lower() for s in steps]


def _served_in_roadmap(titles: List[str], match: str) -> bool:
    needle = (match or "").strip().lower()
    if not needle:
        return False
    return any(needle in title for title in titles)


def score_slice(slice_def: Dict[str, Any], produced_roadmaps: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Score one (corridor x employee_type) slice against its HLP requirement set.

    A requirement is 'correctly served' only when EVERY produced roadmap for the
    slice contains it \u2014 one roadmap that misses it is one employee who gets
    ambushed, so the slice's recall drops. ``recall`` is None (no data) when the
    slice has no produced roadmaps; the caller must surface that, not skip it.
    """
    requirements = slice_def.get("requirements") or []
    total = len(requirements)
    verification = slice_def.get("verification") or {}

    if not produced_roadmaps:
        return {
            "corridor": slice_def["corridor"],
            "employee_type": slice_def["employee_type"],
            "label": slice_def.get("label"),
            "recall": None,
            "served": 0,
            "total": total,
            "missing": [r["key"] for r in requirements],
            "n_roadmaps": 0,
            "hlp_status": verification.get("status", "unknown"),
        }

    titles_per_roadmap = [_roadmap_titles(steps) for steps in produced_roadmaps]
    missing: List[str] = []
    served = 0
    for req in requirements:
        if all(_served_in_roadmap(titles, req.get("match", "")) for titles in titles_per_roadmap):
            served += 1
        else:
            missing.append(req["key"])

    return {
        "corridor": slice_def["corridor"],
        "employee_type": slice_def["employee_type"],
        "label": slice_def.get("label"),
        "recall": round(served / total, 4) if total else None,
        "served": served,
        "total": total,
        "missing": missing,
        "n_roadmaps": len(produced_roadmaps),
        "hlp_status": verification.get("status", "unknown"),
    }


def score_slices(
    baseline: Dict[str, Any],
    produced_by_slice: Dict[str, List[List[Dict[str, Any]]]],
) -> Dict[str, Any]:
    """Score every baseline slice; report worst-first with NO cross-slice mean.

    ``produced_by_slice`` maps ``"<CORRIDOR>:<employee_type>"`` to a list of
    produced roadmaps (each a list of step dicts). Returns::

        {
          "slices": [...],        # scored slices sorted ascending by recall
                                  # (worst first), then no-data slices
          "worst_slice": {...},   # the scored slice with the lowest recall
          "worst_recall": float,  # its recall \u2014 the ONLY headline number
          "scored_slices": int,
          "unscored_slices": int,
        }
    """
    reports = [
        score_slice(s, produced_by_slice.get(slice_id(s["corridor"], s["employee_type"]), []))
        for s in baseline["slices"]
    ]
    scored = sorted((r for r in reports if r["recall"] is not None), key=lambda r: (r["recall"], r["corridor"], r["employee_type"]))
    unscored = [r for r in reports if r["recall"] is None]
    worst = scored[0] if scored else None
    return {
        "slices": scored + unscored,
        "worst_slice": (
            {"corridor": worst["corridor"], "employee_type": worst["employee_type"], "recall": worst["recall"], "missing": worst["missing"]}
            if worst
            else None
        ),
        "worst_recall": worst["recall"] if worst else None,
        "scored_slices": len(scored),
        "unscored_slices": len(unscored),
    }

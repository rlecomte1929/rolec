"""The precision half of the non-obvious metric: what the roadmap said that it must not.

`nonobvious_recall` measures what a slice *fails to surface*. It is structurally blind to the
opposite failure, and the opposite failure is the one this corridor keeps re-committing:

  * A Spanish national — a free mover into Ireland — was told to obtain a long-stay 'D'
    Employment visa before travelling, and was *asserted* to receive a Critical Skills spouse
    permission on Stamp 1G (fixed in #1951).
  * Their family got a step whose title names Stamp 1G, a permission an EEA family member
    neither receives nor needs.

**Every one of those cost exactly zero recall.** Recall counts requirements that are present;
serving a requirement to someone who must not receive it leaves the recall number at 1.0. So
the recall gate could not have caught any of them, and a framework with only that half reads
green through the failures it exists to prevent.

`must_not_serve` is the other half. Per slice it lists what this audience must never see, and
a violation is counted if the match appears in **any** produced roadmap **or any advisory** —
the mirror of recall's "every roadmap" rule. Recall is strict about presence, so precision is
strict about absence: one employee shown one wrong instruction is one wrong instruction.

The headline is a **sum, not a rate**, for the same reason `worst_recall` is a min rather than
a mean. "97% of instructions were correct" is not a sentence anyone should be able to write
about immigration guidance.

Advisories are scored alongside steps because half the ES→IE over-serving lived there:
`VISA_REQUIRED_NATIONAL` is not a step, and a scorer reading only `steps` would have called
that roadmap clean.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .nonobvious_recall import slice_id


def _haystack(
    produced_roadmaps: Sequence[Sequence[Dict[str, Any]]],
    produced_advisories: Optional[Sequence[Sequence[Dict[str, Any]]]] = None,
) -> List[str]:
    """Every string this audience could read, lowercased.

    Step titles and advisory text are pooled deliberately. The reader does not distinguish
    "a step told me to get a visa" from "a banner told me to get a visa", and neither should
    the metric.
    """
    out: List[str] = []
    for steps in produced_roadmaps or ():
        out.extend(str(s.get("title") or "").lower() for s in steps)
    for advisories in produced_advisories or ():
        for a in advisories or ():
            out.append(str(a.get("text") or "").lower())
            out.append(str(a.get("id") or "").lower())
    return out


def score_slice_overserving(
    slice_def: Dict[str, Any],
    produced_roadmaps: Sequence[Sequence[Dict[str, Any]]],
    produced_advisories: Optional[Sequence[Sequence[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Count what this slice was shown that it must never be shown.

    A slice with no ``must_not_serve`` scores zero violations and says so via
    ``n_forbidden: 0`` — an unconstrained slice must be visibly unconstrained rather than
    silently counted as clean.
    """
    forbidden = slice_def.get("must_not_serve") or []
    corridor = slice_def["corridor"]
    employee_type = slice_def["employee_type"]

    if not produced_roadmaps:
        return {
            "corridor": corridor,
            "employee_type": employee_type,
            "label": slice_def.get("label"),
            "violations": 0,
            "n_forbidden": len(forbidden),
            "violated": [],
            "n_roadmaps": 0,
            "measured": False,
        }

    hay = _haystack(produced_roadmaps, produced_advisories)
    violated = [
        {"key": entry["key"], "match": entry.get("match", ""), "why": entry.get("why")}
        for entry in forbidden
        if (entry.get("match") or "").strip()
        and any((entry["match"].strip().lower()) in text for text in hay)
    ]

    return {
        "corridor": corridor,
        "employee_type": employee_type,
        "label": slice_def.get("label"),
        "violations": len(violated),
        "n_forbidden": len(forbidden),
        "violated": violated,
        "n_roadmaps": len(produced_roadmaps),
        "measured": True,
    }


def score_overserving(
    baseline: Dict[str, Any],
    produced_by_slice: Dict[str, List[List[Dict[str, Any]]]],
    advisories_by_slice: Optional[Dict[str, List[List[Dict[str, Any]]]]] = None,
) -> Dict[str, Any]:
    """Total over-serving violations across every slice, worst first.

    ``unmeasured_slices`` is reported rather than quietly treated as zero: a slice with no
    produced roadmaps has not been shown to be clean, and "nothing was checked" must never
    print the same as "nothing was wrong".
    """
    advisories_by_slice = advisories_by_slice or {}
    scored: List[Dict[str, Any]] = []
    for s in baseline.get("slices") or []:
        sid = slice_id(s["corridor"], s["employee_type"])
        scored.append(
            score_slice_overserving(
                s, produced_by_slice.get(sid) or [], advisories_by_slice.get(sid) or []
            )
        )

    scored.sort(
        key=lambda r: (-r["violations"], r["corridor"], r["employee_type"])
    )
    measured = [r for r in scored if r["measured"]]
    return {
        "slices": scored,
        "violations": sum(r["violations"] for r in scored),
        "measured_slices": len(measured),
        "unmeasured_slices": [
            slice_id(r["corridor"], r["employee_type"]) for r in scored if not r["measured"]
        ],
        "constrained_slices": sum(1 for r in scored if r["n_forbidden"] > 0),
    }

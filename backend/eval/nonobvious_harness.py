"""Drive the real roadmap engine for the non-obvious eval, instead of a hand-written fixture.

`produced_slices_sample.json` is engineered to score 1.0 by construction. Measuring against
it proves the arithmetic works and nothing about the product. This module runs committed case
profiles through `roadmap_builder.derive_roadmap` — the same function
`GET /api/cases/{id}/roadmap` and the plan email call — and returns what it actually emitted.

**Deterministic and offline by construction.** `derive_roadmap`'s only I/O is the committed
`corridors/**` YAML, via `corridor_registry` and `relopass.corridors.load_corridor`. It has
been run here with no `DATABASE_URL`, no `OPENAI_API_KEY` and no network.

One clock dependency exists and is contained: `roadmap_builder._age_from_dob` calls
`date.today()`, reached from `_build_lanes` for children carrying a `dateOfBirth`. It affects
`lanes` only, never `steps` or `advisories`. Both halves of the containment matter — the
committed profiles omit `dateOfBirth`, and this module returns only `steps` and `advisories`
— because either alone would leave the snapshot free to drift with the calendar.

**Several profiles per slice, deliberately.** `score_slice` counts a requirement as served
only when *every* produced roadmap contains it. With one profile per slice that "every" is
vacuous and the rule is dead code. The committed set varies the axis that actually breaks
things: an ISO nationality code, the same nationality as a country NAME (426 of 1389 wizard
cases store a name, per `roadmap_corridor_overlay`'s own note), and a household variant.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_PROFILES_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests" / "fixtures" / "eval" / "nonobvious" / "case_profiles.jsonl"
)


def load_profiles(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load the committed case profiles. Fails loudly on an empty or malformed file.

    Same discipline as `load_baseline`: measuring against nothing must not look like
    measuring successfully.
    """
    p = path or DEFAULT_PROFILES_PATH
    records: List[Dict[str, Any]] = []
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        obj = json.loads(line)
        if "_meta" in obj:
            continue
        for required in ("slice", "profile_id", "case"):
            if required not in obj:
                raise ValueError(f"{p}:{lineno} profile missing {required!r}")
        records.append(obj)
    if not records:
        raise ValueError(f"{p} contains no case profiles")
    return records


def build_produced(
    profiles: List[Dict[str, Any]],
) -> Tuple[Dict[str, List[List[Dict[str, Any]]]], Dict[str, List[List[Dict[str, Any]]]]]:
    """Run every profile through the shipped engine.

    Returns ``({slice_id: [steps, ...]}, {slice_id: [advisories, ...]})``.

    `derive_roadmap` is called rather than `corridor_overlay` directly, deliberately: the
    overlay is only half the composition, and a bug in how `roadmap_builder` merges it —
    a step dropped into a track that does not exist, say — is exactly the kind of defect
    this eval should see. Measuring the part instead of the whole would have missed it.
    """
    from backend.app.services.roadmap_builder import derive_roadmap

    steps_by_slice: Dict[str, List[List[Dict[str, Any]]]] = {}
    advisories_by_slice: Dict[str, List[List[Dict[str, Any]]]] = {}
    for rec in profiles:
        sid = rec["slice"]
        roadmap = derive_roadmap(rec["case"])
        steps_by_slice.setdefault(sid, []).append(list(roadmap.get("steps") or []))
        advisories_by_slice.setdefault(sid, []).append(list(roadmap.get("advisories") or []))
    return steps_by_slice, advisories_by_slice

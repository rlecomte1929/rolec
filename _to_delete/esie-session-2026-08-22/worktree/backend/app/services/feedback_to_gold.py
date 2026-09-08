"""
Feedback → gold candidate conversion (Phase 3a — closing the learning loop).

Turns a human/user signal (`rejected` / `edited` verdict in ai_human_feedback),
joined to its replay record (ai_replay_store), into a CANDIDATE regression gold
case. Once a human promotes a candidate into the authoritative gold
(backend/tests/fixtures/eval/<corridor>/in_de.{json,jsonl}), every confirmed
failure becomes a test the evals run forever — the "gets better the more we use
it" mechanism.

Governance (P5-9 / P5-5 hard rule: feedback is signal, never auto-edits content):
this module ONLY writes to a staging file (``candidates.jsonl``). It never mutates
the authoritative gold — a human reviews and promotes candidates.

Join key: ai_human_feedback.trace_session_id == ai_replay_records.trace_id
(== policy_assistant_traces.id).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONVERTIBLE_VERDICTS = ("rejected", "edited")
_ROADMAP_FEATURE = "rag_roadmap"
_STOPWORDS = {"the", "a", "an", "for", "your", "at", "of", "to", "and", "in", "on", "with"}


def _slug(title: str, used: set) -> str:
    """A short, unique key from a step title (first 3 significant words)."""
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).split()
             if w and w not in _STOPWORDS]
    base = "-".join(words[:3]) or "step"
    key = base
    i = 2
    while key in used:
        key = f"{base}-{i}"
        i += 1
    used.add(key)
    return key


def _match(title: str) -> str:
    """A normalized substring a human can refine; lives inside the source title so
    it can match future produced titles."""
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def _steps_from_output(output_masked: Any) -> List[Dict[str, Any]]:
    if isinstance(output_masked, dict):
        return output_masked.get("steps") or []
    try:
        return (json.loads(output_masked or "{}") or {}).get("steps") or []
    except (json.JSONDecodeError, TypeError):
        return []


def _positive_roadmap_case(edited: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the run_roadmap_outcome_eval gold shape from a corrected roadmap."""
    used: set = set()
    expected_steps = []
    for step in edited.get("steps") or []:
        title = str(step.get("title") or "")
        expected_steps.append({"key": _slug(title, used), "match": _match(title)})
    order = [[expected_steps[i]["key"], expected_steps[i + 1]["key"]]
             for i in range(len(expected_steps) - 1)]
    return {"expected_steps": expected_steps, "order": order}


def build_gold_candidates(
    feedback_rows: List[Dict[str, Any]],
    replay_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build candidate gold cases from rejected/edited feedback joined to replay
    records. Pure + deterministic. Skips approved verdicts and feedback whose trace
    has no replay record."""
    by_trace = {r.get("trace_id"): r for r in replay_records if r.get("trace_id")}
    candidates: List[Dict[str, Any]] = []

    for fb in feedback_rows:
        verdict = fb.get("verdict")
        if verdict not in _CONVERTIBLE_VERDICTS:
            continue
        rec = by_trace.get(fb.get("trace_session_id"))
        if rec is None:
            continue

        common = {
            "source_feedback_id": fb.get("id"),
            "trace_id": rec.get("trace_id"),
            "replay_record_id": rec.get("id"),
            "corridor": rec.get("corridor"),
            "feature_key": rec.get("feature_key"),
            "verdict": verdict,
        }

        edited = fb.get("edited_output_json")
        if verdict == "edited" and edited and rec.get("feature_key") == _ROADMAP_FEATURE:
            candidates.append({**common, "kind": "positive", "case": _positive_roadmap_case(edited)})
        elif verdict == "edited" and edited:
            # Non-roadmap correction: stage the corrected output verbatim for a human.
            candidates.append({**common, "kind": "positive", "case": {"expected_output": edited}})
        else:  # rejected (no correction) → must-not-recur regression case
            candidates.append({**common, "kind": "negative", "case": {
                "reason": fb.get("comment"),
                "original_step_titles": [str(s.get("title") or "")
                                         for s in _steps_from_output(rec.get("output_masked"))],
                "note": "the output that produced this must not recur / must score below threshold",
            }})

    return candidates


# --------------------------------------------------------------------------- #
# DB reader + staging writer + CLI                                            #
# --------------------------------------------------------------------------- #

def _load_feedback(engine, verdicts=_CONVERTIBLE_VERDICTS) -> List[Dict[str, Any]]:
    from sqlalchemy import text

    placeholders = ",".join(f":v{i}" for i in range(len(verdicts)))
    params = {f"v{i}": v for i, v in enumerate(verdicts)}
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, trace_session_id, verdict, edited_output_json, comment "
            f"FROM ai_human_feedback WHERE verdict IN ({placeholders})"
        ), params).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("edited_output_json"), str):
            try:
                d["edited_output_json"] = json.loads(d["edited_output_json"])
            except (json.JSONDecodeError, TypeError):
                d["edited_output_json"] = None
        out.append(d)
    return out


def write_candidates(candidates: List[Dict[str, Any]], out_dir: Path, corridor: str) -> Path:
    """Append candidates to the corridor STAGING file (never the authoritative gold)."""
    dest_dir = out_dir / corridor
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "candidates.jsonl"
    with dest.open("a") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")
    return dest


def summarize(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    pos = sum(1 for c in candidates if c["kind"] == "positive")
    neg = sum(1 for c in candidates if c["kind"] == "negative")
    return {"n_candidates": len(candidates), "positive": pos, "negative": neg,
            "by_feature": {fk: sum(1 for c in candidates if c["feature_key"] == fk)
                           for fk in sorted({c["feature_key"] for c in candidates})}}


def main(argv: Optional[List[str]] = None) -> int:
    from .. import db as _db
    from .ai_replay_store import list_replay_records

    parser = argparse.ArgumentParser(description="Convert rejected/edited feedback into gold candidates.")
    parser.add_argument("--corridor", default=None, help="Scope to one corridor (e.g. IN_DE).")
    parser.add_argument("--out", type=Path,
                        default=Path("backend/tests/fixtures/eval/_candidates"),
                        help="Staging dir for candidates.jsonl (NOT the authoritative gold).")
    args = parser.parse_args(argv)

    feedback = _load_feedback(_db.engine)
    replays = list_replay_records(corridor=args.corridor, limit=5000)
    candidates = build_gold_candidates(feedback, replays)

    summary = summarize(candidates)
    print(json.dumps(summary, indent=2))

    by_corridor: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        by_corridor.setdefault(c.get("corridor") or "UNKNOWN", []).append(c)
    for corridor, group in by_corridor.items():
        dest = write_candidates(group, args.out, corridor)
        print(f"staged {len(group)} candidate(s) → {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

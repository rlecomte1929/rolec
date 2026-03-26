"""
PolicySnapshotDiffService — compare two knowledge snapshots (facts, applicability, ambiguity, sources).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from ..database import Database


def _fingerprint(f: Dict[str, Any]) -> str:
    """Stable key for diffing without requiring stable DB ids across revisions."""
    nv = f.get("normalized_value_json") or {}
    ap = f.get("applicability_json") or {}
    return json.dumps(
        {
            "ft": f.get("fact_type"),
            "cat": f.get("category"),
            "sub": f.get("subcategory"),
            "nv": nv,
            "ap": ap,
            "amb": bool(f.get("ambiguity_flag")),
        },
        sort_keys=True,
        default=str,
    )


def compare_snapshots(db: Database, old_snapshot_id: str, new_snapshot_id: str) -> Dict[str, Any]:
    old_facts = db.list_policy_facts_for_snapshot(old_snapshot_id)
    new_facts = db.list_policy_facts_for_snapshot(new_snapshot_id)
    old_map: Dict[str, Dict[str, Any]] = {}
    for f in old_facts:
        old_map[_fingerprint(f)] = f
    new_map: Dict[str, Dict[str, Any]] = {}
    for f in new_facts:
        new_map[_fingerprint(f)] = f

    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())
    added = [new_map[k] for k in sorted(new_keys - old_keys)]
    removed = [old_map[k] for k in sorted(old_keys - new_keys)]

    changed: List[Dict[str, Any]] = []
    for k in sorted(old_keys & new_keys):
        o, n = old_map[k], new_map[k]
        if (
            (o.get("source_quote") or "") != (n.get("source_quote") or "")
            or (o.get("source_section") or "") != (n.get("source_section") or "")
            or int(o.get("ambiguity_flag") or 0) != int(n.get("ambiguity_flag") or 0)
        ):
            changed.append({"old": o, "new": n, "fingerprint": k})

    return {
        "older_snapshot_id": old_snapshot_id,
        "newer_snapshot_id": new_snapshot_id,
        "summary": {
            "added_count": len(added),
            "removed_count": len(removed),
            "unchanged_count": len(old_keys & new_keys) - len(changed),
            "changed_count": len(changed),
        },
        "added_facts": added,
        "removed_facts": removed,
        "changed_facts": changed,
    }


class PolicySnapshotDiffService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def compare_snapshots(self, old_snapshot_id: str, new_snapshot_id: str) -> Dict[str, Any]:
        return compare_snapshots(self._db, old_snapshot_id, new_snapshot_id)

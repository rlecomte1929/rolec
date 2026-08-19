"""Corridor deadline-alert metrics (the destination-evolution scorecard).

Reports the metrics that decide whether a corridor is ready to alert, and whether
the alerting model is still honest as destinations are added.

    python -m backend.scripts.corridor_alert_metrics              # repo-only
    DATABASE_URL=... python -m backend.scripts.corridor_alert_metrics --with-ledger

Repo metrics need no database — they are computed from the corridor YAML alone,
which is the point: a corridor author can run this before anything is deployed.
``--with-ledger`` adds the runtime metrics (exactly-once, failures surfaced) and
is the only part that touches the database, read-only.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from typing import Any, Dict, List

from ..relopass.corridors import load_corridor
from ..relopass.corridors.deadline_alerts import check_tag_destination_invariant

PATHWAY_GLOB = "corridors/*/pathways/*/v1.yaml"


def repo_metrics() -> Dict[str, Any]:
    corridors = {}
    for f in sorted(glob.glob(PATHWAY_GLOB)):
        c = load_corridor(f)
        corridors[c.corridor_id] = c

    per_corridor: List[Dict[str, Any]] = []
    tag_bindings: Dict[str, List[str]] = {}

    for cid, c in sorted(corridors.items()):
        windowed = [s for s in c.step_graph if s.time_window_relative_to]
        triggered = [s for s in c.step_graph if s.deadline_trigger]
        for s in triggered:
            tag_bindings.setdefault(s.deadline_trigger.tag, []).append(f"{cid}.{s.step_id}")
        per_corridor.append(
            {
                "corridor": cid,
                "destination": c.destination_country_iso3,
                "steps": len(c.step_graph),
                "windowed_steps": len(windowed),
                "alerting_steps": len(triggered),
                # The delta a corridor author closes: a statutory window with no
                # trigger is a deadline the product knows about and stays silent on.
                "windowed_without_trigger": sorted(
                    s.step_id for s in windowed if s.deadline_trigger is None
                ),
            }
        )

    violations = check_tag_destination_invariant(corridors)
    reused = {t: b for t, b in tag_bindings.items() if len(b) > 1}

    return {
        "corridors": len(corridors),
        "corridors_alerting": sum(1 for r in per_corridor if r["alerting_steps"]),
        "total_tags": len(tag_bindings),
        # Rising reuse is the evidence that "state the rule once" is working: one
        # tag serving two corridors means one message, authored once.
        "reuse_ratio": round(len(reused) / len(tag_bindings), 3) if tag_bindings else 0.0,
        "reused_tags": {t: sorted(b) for t, b in sorted(reused.items())},
        # Target 0, enforced by the test suite — reported here so a drift shows up
        # in the scorecard as well as in a red build.
        "tag_invariant_violations": violations,
        "per_corridor": per_corridor,
    }


def ledger_metrics() -> Dict[str, Any]:
    from ..database import db

    with db.engine.connect() as conn:
        from sqlalchemy import text

        totals = conn.execute(
            text(
                "SELECT status, count(*) AS n FROM public.corridor_deadline_events "
                "GROUP BY status"
            )
        ).mappings().all()
        # The PK makes duplicates impossible; this asserts that rather than
        # assuming it, because a guard nobody measures is a guard nobody notices
        # losing.
        dupes = conn.execute(
            text(
                "SELECT count(*) AS n FROM ("
                "  SELECT case_ref, step_id, due_date FROM public.corridor_deadline_events"
                "  GROUP BY case_ref, step_id, due_date HAVING count(*) > 1"
                ") d"
            )
        ).scalar()
        unresolved = conn.execute(
            text(
                "SELECT event_uid, case_ref, step_id, status, detail "
                "FROM public.corridor_deadline_events "
                "WHERE status IN ('no_contact','error') "
                "ORDER BY created_at DESC LIMIT 50"
            )
        ).mappings().all()

    return {
        "by_status": {r["status"]: r["n"] for r in totals},
        "duplicate_event_keys": dupes,
        # 100% of failures must reach an operator; this is the list.
        "failures_needing_attention": [dict(r) for r in unresolved],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Corridor deadline-alert metrics")
    ap.add_argument("--with-ledger", action="store_true",
                    help="add runtime metrics from corridor_deadline_events (read-only)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    out: Dict[str, Any] = {"repo": repo_metrics()}
    if args.with_ledger:
        try:
            out["ledger"] = ledger_metrics()
        except Exception as exc:  # noqa: BLE001
            out["ledger"] = {"error": str(exc)}

    if args.json:
        print(json.dumps(out, indent=2, default=str))
        return 0

    r = out["repo"]
    print(f"corridors:            {r['corridors']}  ({r['corridors_alerting']} alerting)")
    print(f"alert tags:           {r['total_tags']}  (reuse ratio {r['reuse_ratio']})")
    print(f"invariant violations: {len(r['tag_invariant_violations'])}")
    for v in r["tag_invariant_violations"]:
        print(f"    ✗ {v}")
    for t, b in r["reused_tags"].items():
        print(f"    reused: {t} -> {', '.join(b)}")
    print()
    print(f"{'corridor':28} {'dest':5} {'steps':>5} {'windowed':>9} {'alerting':>9}  gap")
    for c in r["per_corridor"]:
        gap = ",".join(c["windowed_without_trigger"]) or "-"
        print(f"{c['corridor']:28} {str(c['destination']):5} {c['steps']:>5} "
              f"{c['windowed_steps']:>9} {c['alerting_steps']:>9}  {gap}")

    if "ledger" in out:
        print()
        led = out["ledger"]
        if "error" in led:
            print(f"ledger: unavailable ({led['error']})")
        else:
            print(f"ledger by status:       {led['by_status']}")
            print(f"duplicate event keys:   {led['duplicate_event_keys']}  (must be 0)")
            print(f"failures to review:     {len(led['failures_needing_attention'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

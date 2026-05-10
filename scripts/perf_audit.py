#!/usr/bin/env python3
"""
Lightweight performance audit for the ReloPass codebase.

Outputs a non-specialist-friendly summary with measured baselines where possible:
- backend startup/import cost
- relocation-plan assembly benchmark
- policy pipeline observability readiness
- frontend route-loading shape
- admin/database hotspot candidates

This script intentionally prefers safe local measurements and static heuristics over
needing live infrastructure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_MAIN = REPO_ROOT / "backend" / "main.py"
FRONTEND_APP = REPO_ROOT / "frontend" / "src" / "App.tsx"
VENV_PYTHON = REPO_ROOT / "venv" / "bin" / "python"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _pick_local_db() -> Optional[Path]:
    for candidate in (REPO_ROOT / "test.db", REPO_ROOT / "relopass.db"):
        if candidate.exists():
            return candidate
    return None


def _render_sqlite_url(path: Path) -> str:
    return f"sqlite:///{path}"


def _run(cmd: List[str], *, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _tail_nonempty_lines(text: str, limit: int = 5) -> List[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-limit:]


def _percentile(values: List[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio))))
    return ordered[idx]


@dataclass
class FunctionHotspot:
    file: str
    function: str
    line: int
    lines: int
    select_count: int
    execute_count: int
    nested_select_count: int
    supabase_table_calls: int
    summary: str


def collect_startup_import_audit() -> Dict[str, Any]:
    db_path = _pick_local_db()
    if db_path is None:
        return {
            "available": False,
            "reason": "No local SQLite database found (expected test.db or relopass.db).",
        }

    with tempfile.TemporaryDirectory(prefix="relopass-startup-audit-") as tmpdir:
        db_copy = Path(tmpdir) / db_path.name
        shutil.copy2(db_path, db_copy)
        env = os.environ.copy()
        env["DATABASE_URL"] = _render_sqlite_url(db_copy)
        proc = _run([str(VENV_PYTHON), "-X", "importtime", "-c", "import backend.main"], env=env)
        stderr = proc.stderr or ""
        imports: List[Dict[str, Any]] = []
        for line in stderr.splitlines():
            match = re.match(r"import time:\s+(\d+) \|\s+(\d+) \|\s+(.+)$", line.strip())
            if not match:
                continue
            self_us, cumulative_us, module = match.groups()
            imports.append(
                {
                    "module": module.strip(),
                    "self_ms": round(int(self_us) / 1000.0, 3),
                    "cumulative_ms": round(int(cumulative_us) / 1000.0, 3),
                }
            )

        backend_imports = sorted(
            [row for row in imports if row["module"].startswith("backend.")],
            key=lambda row: row["cumulative_ms"],
            reverse=True,
        )
        main_entry = next((row for row in backend_imports if row["module"] == "backend.main"), None)
        failure_tail = _tail_nonempty_lines(stderr, limit=8) if proc.returncode != 0 else []
        return {
            "available": True,
            "db_source": str(db_path),
            "baseline_import_ms": main_entry["cumulative_ms"] if main_entry else None,
            "top_backend_modules": backend_imports[:8],
            "completed_cleanly": proc.returncode == 0,
            "failure_tail": failure_tail,
        }


def collect_relocation_plan_benchmark() -> Dict[str, Any]:
    db_path = _pick_local_db()
    if db_path is None:
        return {
            "available": False,
            "reason": "No local SQLite database found for relocation-plan benchmark.",
        }

    with tempfile.TemporaryDirectory(prefix="relopass-plan-bench-") as tmpdir:
        db_copy = Path(tmpdir) / db_path.name
        shutil.copy2(db_path, db_copy)
        previous_db = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = _render_sqlite_url(db_copy)
        try:
            from backend.app.services.timeline_service import OPERATIONAL_TASK_DEFAULTS
            from backend.services.relocation_plan_view_service import build_relocation_plan_view_response
        finally:
            if previous_db is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_db

    class StubDB:
        def __init__(self, selected: Optional[List[str]] = None) -> None:
            self._selected = selected or []

        def list_case_services(self, assignment_id: str) -> List[Dict[str, Any]]:
            return [{"service_key": key, "selected": True} for key in self._selected]

    def milestone_row(spec: Dict[str, Any], *, status: str = "pending") -> Dict[str, Any]:
        return {
            "id": f"id-{spec['milestone_type']}",
            "milestone_type": spec["milestone_type"],
            "title": spec["title"],
            "status": status,
            "owner": spec["owner"],
            "criticality": spec["criticality"],
            "sort_order": spec.get("sort_order", 0),
        }

    full_milestones = [milestone_row(spec) for spec in OPERATIONAL_TASK_DEFAULTS]
    full_profile = {
        "primaryApplicant": {
            "fullName": "Alex Assignee",
            "nationality": "US",
            "employer": {"jobLevel": "IC4", "roleTitle": "Engineer"},
        },
        "movePlan": {"origin": "United States", "destination": "Germany"},
        "complianceDocs": {"hasEmploymentLetter": True, "hasPassportScans": True},
        "maritalStatus": "married",
        "spouse": {"fullName": "Sam Spouse"},
    }

    scenarios = [
        ("empty_case", [], {}, 150),
        ("full_case", full_milestones, full_profile, 150),
    ]

    results: List[Dict[str, Any]] = []
    db = StubDB(selected=["housing", "movers"])
    for label, milestones, profile_draft, loops in scenarios:
        durations: List[float] = []
        for _ in range(loops):
            start = time.perf_counter()
            build_relocation_plan_view_response(
                case_id="case-audit",
                assignment_id="assignment-audit",
                milestones=milestones,
                profile_draft=profile_draft,
                mobility_case_id=None,
                db=db,
                viewer_role="employee",
                debug=False,
                request_id="perf-audit",
            )
            durations.append((time.perf_counter() - start) * 1000.0)
        results.append(
            {
                "scenario": label,
                "loops": loops,
                "mean_ms": round(statistics.mean(durations), 3),
                "p95_ms": round(_percentile(durations, 0.95), 3),
                "max_ms": round(max(durations), 3),
            }
        )

    return {
        "available": True,
        "scope": "Python assembly only; excludes HTTP auth, DB reads, and network latency.",
        "results": results,
    }


def collect_policy_pipeline_audit() -> Dict[str, Any]:
    db_path = _pick_local_db()
    if db_path is None:
        return {
            "available": False,
            "reason": "No local SQLite database found for policy analytics scan.",
        }

    conn = sqlite3.connect(str(db_path))
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_events'"
        ).fetchone()
        if not table_exists:
            return {
                "available": False,
                "reason": "analytics_events table is not present in the local SQLite snapshot.",
                "event_instrumentation_present": True,
                "next_step": "Use production or staging analytics_events data to measure upload-to-classify throughput.",
            }

        names = [
            "policy_upload_started",
            "policy_upload_completed",
            "policy_upload_failed",
            "policy_classify_started",
            "policy_classify_completed",
            "policy_classify_failed",
        ]
        counts: Dict[str, int] = {}
        for name in names:
            row = conn.execute(
                "SELECT COUNT(*) FROM analytics_events WHERE event_name = ?",
                (name,),
            ).fetchone()
            counts[name] = int(row[0]) if row else 0

        return {
            "available": True,
            "event_counts": counts,
        }
    finally:
        conn.close()


def collect_frontend_route_audit() -> Dict[str, Any]:
    text = FRONTEND_APP.read_text()
    eager_imports = re.findall(r"^import\s+\{?[^;\n]+from\s+'(\./pages[^']+)'", text, re.MULTILINE)
    lazy_imports = re.findall(r"lazy\(\(\) => import\('(\./pages[^']+)'\)", text)
    eager_admin = [path for path in eager_imports if "/admin/" in path or path.endswith("/admin")]
    lazy_admin = [path for path in lazy_imports if "/admin/" in path or path.endswith("/admin")]
    return {
        "available": True,
        "eager_page_import_count": len(eager_imports),
        "lazy_page_import_count": len(lazy_imports),
        "eager_admin_import_count": len(eager_admin),
        "lazy_admin_import_count": len(lazy_admin),
        "sample_eager_pages": eager_imports[:12],
    }


def _extract_function_hotspot(path: Path, function_name: str, summary: str) -> FunctionHotspot:
    lines = path.read_text().splitlines()
    start_idx = -1
    indent = 0
    patterns = [
        f"def {function_name}(",
        f"    def {function_name}(",
    ]
    for idx, line in enumerate(lines):
        if any(line.startswith(pattern) for pattern in patterns):
            start_idx = idx
            indent = len(line) - len(line.lstrip(" "))
            break
    if start_idx == -1:
        raise ValueError(f"Function {function_name} not found in {path}")

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        line = lines[idx]
        stripped = line.lstrip(" ")
        current_indent = len(line) - len(stripped)
        if stripped.startswith("def ") and current_indent == indent:
            end_idx = idx
            break

    block = "\n".join(lines[start_idx:end_idx])
    return FunctionHotspot(
        file=str(path.relative_to(REPO_ROOT)),
        function=function_name,
        line=start_idx + 1,
        lines=end_idx - start_idx,
        select_count=block.count("SELECT "),
        execute_count=block.count(".execute("),
        nested_select_count=block.count("(SELECT "),
        supabase_table_calls=block.count(".table("),
        summary=summary,
    )


def collect_db_hotspots() -> Dict[str, Any]:
    hotspots = [
        _extract_function_hotspot(
            REPO_ROOT / "backend" / "database.py",
            "get_admin_company_index",
            "Company index still does orphan scans and multi-query aggregation, but no longer relies on per-company correlated counts.",
        ),
        _extract_function_hotspot(
            REPO_ROOT / "backend" / "services" / "review_queue_service.py",
            "list_review_queue_items",
            "Review queue listing is a likely admin hotspot as dataset volume grows.",
        ),
        _extract_function_hotspot(
            REPO_ROOT / "backend" / "services" / "freshness_service.py",
            "get_freshness_overview",
            "Freshness overview aggregates multiple content-quality signals into one dashboard payload.",
        ),
        _extract_function_hotspot(
            REPO_ROOT / "backend" / "services" / "staging_review_service.py",
            "get_staging_dashboard_counts",
            "Staging dashboard counts are a natural candidate for read-model or cached aggregation.",
        ),
        _extract_function_hotspot(
            REPO_ROOT / "backend" / "services" / "ops_analytics_service.py",
            "get_sla_overview",
            "Ops overview pulls multiple Supabase datasets and computes SLA metrics in Python.",
        ),
    ]

    return {
        "available": True,
        "hotspots": [
            {
                "file": hotspot.file,
                "function": hotspot.function,
                "line": hotspot.line,
                "lines": hotspot.lines,
                "select_count": hotspot.select_count,
                "execute_count": hotspot.execute_count,
                "nested_select_count": hotspot.nested_select_count,
                "supabase_table_calls": hotspot.supabase_table_calls,
                "summary": hotspot.summary,
            }
            for hotspot in hotspots
        ],
    }


def build_roi_roadmap(audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    startup = audit["startup"]
    relocation = audit["relocation_plan"]
    frontend = audit["frontend"]
    policy = audit["policy_pipeline"]
    db_hotspots = audit["db_hotspots"]

    startup_baseline = startup.get("baseline_import_ms")
    startup_note = (
        f"`backend.main` imports in about {startup_baseline:.1f} ms before runtime DB-init writes kick in."
        if startup_baseline is not None
        else "Startup baseline unavailable locally."
    )
    relocation_full = next(
        (row for row in relocation.get("results", []) if row["scenario"] == "full_case"),
        None,
    )
    relocation_note = (
        f"Synthetic full-plan assembly averages {relocation_full['mean_ms']:.2f} ms, so pure Python assembly is not the main bottleneck."
        if relocation_full
        else "Relocation-plan benchmark unavailable locally."
    )
    frontend_note = (
        f"{frontend.get('lazy_admin_import_count', 0)} admin pages are lazy-loaded, but {frontend.get('eager_page_import_count', 0)} page modules still load eagerly."
    )
    policy_note = (
        "Local analytics snapshot does not contain analytics_events, so production throughput still needs a measured baseline."
        if not policy.get("available")
        else "Policy pipeline analytics data is available locally."
    )
    top_hotspot = db_hotspots["hotspots"][0] if db_hotspots.get("hotspots") else None
    db_note = (
        f"`{top_hotspot['function']}` already shows {top_hotspot['nested_select_count']} nested subqueries and {top_hotspot['execute_count']} execute paths in one function."
        if top_hotspot
        else "Admin DB hotspot scan unavailable."
    )

    return [
        {
            "priority": 1,
            "area": "Backend startup and import-time work",
            "current_baseline": startup_note,
            "why_slow": "The backend still performs meaningful work during import, including DB initialization side effects and a very large module graph.",
            "fix_options": [
                "Move DB initialization out of module import and into startup hooks or first use.",
                "Split large import fan-out in backend.main so cold starts load less code up front.",
                "Keep import-time profiling in CI or release checks to prevent regressions.",
            ],
            "effort": "medium",
            "benefit": "high",
            "roi": "very high",
            "business_outcome": "Faster cold starts, faster deploy health checks, and lower risk of startup-related outages.",
        },
        {
            "priority": 2,
            "area": "Relocation-plan end-to-end request timing",
            "current_baseline": relocation_note,
            "why_slow": "The assembly code is fast in isolation, which means any slowness users feel is more likely to come from DB reads, auth/visibility checks, or request wiring.",
            "fix_options": [
                "Add request-span timings around the three main reads feeding the plan endpoint.",
                "Measure cache hit rate versus cold path before investing in snapshotting.",
                "Only move to a materialized snapshot if real request traces stay slow after measurement.",
            ],
            "effort": "low",
            "benefit": "medium-high",
            "roi": "high",
            "business_outcome": "Avoids spending time on the wrong bottleneck and keeps a high-traffic user flow responsive.",
        },
        {
            "priority": 3,
            "area": "Frontend loading cost on key screens",
            "current_baseline": frontend_note,
            "why_slow": "Admin lazy loading is now in place, but the main user routes still import many page modules eagerly.",
            "fix_options": [
                "Benchmark the top three business-critical pages first.",
                "Lazy-load the heaviest non-admin routes that are not part of first-session navigation.",
                "Use the existing page-perf instrumentation to compare before/after payload and render time.",
            ],
            "effort": "low-medium",
            "benefit": "medium",
            "roi": "high",
            "business_outcome": "Pages feel lighter on slower laptops and networks, improving perceived quality without a backend rewrite.",
        },
        {
            "priority": 4,
            "area": "Admin query hotspots and scaling risk",
            "current_baseline": db_note,
            "why_slow": "Some admin read models combine multiple scans or correlated subqueries, which often degrade gradually as the dataset grows.",
            "fix_options": [
                "Add a measured EXPLAIN pass for the top admin queries in staging or production.",
                "Apply small index and query-shape fixes before any schema redesign.",
                "Cache or pre-aggregate dashboard-style counters that do not need real-time precision.",
            ],
            "effort": "low-medium",
            "benefit": "medium",
            "roi": "medium-high",
            "business_outcome": "Keeps admin tooling usable as data volume grows and reduces the chance of a late scaling fire drill.",
        },
        {
            "priority": 5,
            "area": "Policy-document throughput and failure visibility",
            "current_baseline": policy_note,
            "why_slow": "Upload UX is faster now, but there is still no local measured baseline for queue-to-completion time or failure classes.",
            "fix_options": [
                "Use analytics_events in staging or production to measure upload-to-classify completion time.",
                "Summarize failure classes so fixes are driven by real document errors, not guesswork.",
                "Promote a proper job queue only if throughput or reliability data justifies it.",
            ],
            "effort": "low",
            "benefit": "medium",
            "roi": "medium",
            "business_outcome": "Makes policy processing predictable for HR without prematurely adding heavy infrastructure.",
        },
    ]


def collect_full_audit() -> Dict[str, Any]:
    audit = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "startup": collect_startup_import_audit(),
        "relocation_plan": collect_relocation_plan_benchmark(),
        "policy_pipeline": collect_policy_pipeline_audit(),
        "frontend": collect_frontend_route_audit(),
        "db_hotspots": collect_db_hotspots(),
    }
    audit["roadmap"] = build_roi_roadmap(audit)
    return audit


def render_markdown(audit: Dict[str, Any]) -> str:
    startup = audit["startup"]
    relocation = audit["relocation_plan"]
    frontend = audit["frontend"]
    policy = audit["policy_pipeline"]
    db_hotspots = audit["db_hotspots"]

    roadmap_lines = []
    for item in audit["roadmap"]:
        roadmap_lines.append(
            f"| {item['priority']} | {item['area']} | {item['benefit']} | {item['effort']} | {item['roi']} | {item['business_outcome']} |"
        )

    top_modules = "\n".join(
        f"- `{row['module']}`: {row['cumulative_ms']} ms cumulative"
        for row in startup.get("top_backend_modules", [])[:5]
    ) or "- Startup import details unavailable."

    relocation_rows = "\n".join(
        f"- `{row['scenario']}`: mean {row['mean_ms']} ms, p95 {row['p95_ms']} ms, max {row['max_ms']} ms"
        for row in relocation.get("results", [])
    ) or "- Relocation-plan benchmark unavailable."

    hotspot_rows = "\n".join(
        f"- `{row['function']}` in `{row['file']}` (line {row['line']}): {row['summary']}"
        for row in db_hotspots.get("hotspots", [])[:5]
    ) or "- No DB hotspot candidates found."

    policy_summary = (
        f"- {policy['reason']}"
        if not policy.get("available")
        else "\n".join(f"- `{k}`: {v}" for k, v in policy.get("event_counts", {}).items())
    )

    lines = [
        "# ReloPass Performance Audit",
        "",
        f"Generated at: `{audit['generated_at']}`",
        "",
        "## Executive Roadmap",
        "| Priority | Area | Benefit | Effort | ROI | Business outcome |",
        "| --- | --- | --- | --- | --- | --- |",
        *roadmap_lines,
        "",
        "## Current Baselines",
        f"- Backend startup import baseline: `{startup.get('baseline_import_ms', 'n/a')}` ms",
        f"- Relocation-plan benchmark scope: {relocation.get('scope', 'n/a')}",
        f"- Frontend eager page imports: `{frontend.get('eager_page_import_count', 'n/a')}`",
        f"- Frontend lazy admin imports: `{frontend.get('lazy_admin_import_count', 'n/a')}`",
        "",
        "## Startup Audit",
        top_modules,
        "",
        "## Relocation-Plan Benchmark",
        relocation_rows,
        "",
        "## Policy Pipeline Audit",
        policy_summary,
        "",
        "## Frontend Route Audit",
        f"- Eager page imports: `{frontend.get('eager_page_import_count', 0)}`",
        f"- Lazy page imports: `{frontend.get('lazy_page_import_count', 0)}`",
        f"- Eager admin pages: `{frontend.get('eager_admin_import_count', 0)}`",
        f"- Lazy admin pages: `{frontend.get('lazy_admin_import_count', 0)}`",
        "",
        "## Admin / DB Hotspot Candidates",
        hotspot_rows,
    ]
    return "\n".join(lines).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lightweight ReloPass performance audit.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--write", help="Optional output file path.")
    args = parser.parse_args()

    audit = collect_full_audit()
    rendered = json.dumps(audit, indent=2) if args.format == "json" else render_markdown(audit)

    if args.write:
        out_path = Path(args.write)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

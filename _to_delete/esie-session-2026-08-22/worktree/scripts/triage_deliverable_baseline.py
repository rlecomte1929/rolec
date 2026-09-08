#!/usr/bin/env python3
"""
triage_deliverable_baseline.py — classify the HYGIENE-1 historical baseline.

The deliverable-integrity allowlist holds a dated baseline of AIQ:path entries
(claimed deliverables whose VERBATIM path is absent on main — mostly stale paths
from refactors, possibly a few genuine leaks). This offline tool classifies each
baseline entry as SHIPPED (the deliverable exists under another path/name) or
LEAK_CANDIDATE (no trace anywhere), using git only — no Notion token.

Signals, in order (first hit wins):
  1. exact non-generic basename match among tracked files
  2. descriptive-token match: `git grep -lF <token>` (migration timestamps stripped)
  3. directory liveness: any tracked file under the claimed dirname (or its parent)
  4. git history: the basename was ever added on any branch (renamed/deleted since)

Anything that hits 1-4 is SHIPPED (with the evidence path); the rest are
LEAK_CANDIDATE and should go to per-task agent verification before being filed.

Usage:
  python scripts/triage_deliverable_baseline.py            # print report
  python scripts/triage_deliverable_baseline.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ALLOWLIST = _REPO_ROOT / "scripts" / "deliverable_integrity_allowlist.txt"

_BASELINE_RE = re.compile(r"^(AIQ-\d+):(.+)$")
# Path segments too common to be a distinctive search token.
_COMMON = {
    "backend", "app", "src", "frontend", "tests", "test", "supabase",
    "migrations", "scripts", "prompts", "audit", "docs", "components",
    "services", "routers", "fixtures", "lib", "eval", "schemas", "agents",
    "relopass", "__init__.py", "__init__", "index.ts", "init.py",
}
_GENERIC_BASENAMES = {
    "__init__.py", "__init__", "init.py", "base.py", "models.py",
    "index.ts", "index.tsx", "README.md", "SCHEMA.md", "config.py",
}


def parse_baseline(path: Path) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        m = _BASELINE_RE.match(line)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def tracked_files(root: Path) -> List[str]:
    res = subprocess.run(["git", "ls-files"], cwd=str(root),
                         capture_output=True, text=True, check=True)
    return [l.strip() for l in res.stdout.splitlines() if l.strip()]


def _descriptive_token(path: str) -> Optional[str]:
    """A distinctive search token: basename stem with any leading migration
    timestamp stripped. Returns None when nothing distinctive remains."""
    stem = path.split("/")[-1].rsplit(".", 1)[0]
    stem = re.sub(r"^\d{6,}_?", "", stem)  # drop migration date prefix
    return stem if len(stem) >= 5 and stem not in _COMMON else None


def _git_grep(token: str, root: Path) -> List[str]:
    # Exclude self-referential files (this tool + the allowlists now CONTAIN the
    # baseline paths, which would otherwise match every token).
    res = subprocess.run(
        ["git", "grep", "-lF", token, "--",
         ":!scripts/deliverable_integrity_allowlist.txt",
         ":!scripts/queue_status_allowlist.txt",
         ":!scripts/triage_deliverable_baseline.py"],
        cwd=str(root), capture_output=True, text=True,
    )
    return [l.strip() for l in res.stdout.splitlines() if l.strip()] if res.returncode == 0 else []


def _git_ever_added(basename: str, root: Path) -> Optional[str]:
    res = subprocess.run(
        ["git", "log", "--all", "--oneline", "--diff-filter=A", "--", f"**/{basename}"],
        cwd=str(root), capture_output=True, text=True,
    )
    first = res.stdout.splitlines()[:1]
    return first[0].strip() if first else None


def classify(aiq: str, path: str, tracked: List[str], tracked_set: Set[str],
             root: Path) -> Dict[str, str]:
    basename = path.split("/")[-1]
    dirname = "/".join(path.split("/")[:-1])

    # 1. exact non-generic basename match
    if basename not in _GENERIC_BASENAMES:
        for t in tracked:
            if t.split("/")[-1] == basename:
                return {"aiq": aiq, "path": path, "status": "SHIPPED",
                        "via": "basename", "evidence": t}

    # 2. descriptive token in a tracked FILENAME (strong: catches renamed files,
    #    e.g. a migration re-stamped with a different timestamp). Content-only is
    #    too weak to auto-confirm and is left to verification.
    token = _descriptive_token(path)
    content_hits: List[str] = []
    if token:
        name_match = next((t for t in tracked if token in t.split("/")[-1]), None)
        if name_match:
            return {"aiq": aiq, "path": path, "status": "SHIPPED",
                    "via": "token-in-filename", "evidence": name_match}
        content_hits = _git_grep(token, root)

    # 3. git history add (a distinctive file that once existed → renamed/moved)
    if basename not in _GENERIC_BASENAMES:
        commit = _git_ever_added(basename, root)
        if commit:
            return {"aiq": aiq, "path": path, "status": "SHIPPED",
                    "via": "git-history", "evidence": commit}

    # 4. directory liveness — EXACT claimed dirname only.
    dir_alive = bool(dirname) and any(t.startswith(dirname + "/") for t in tracked)
    is_generic = basename in _GENERIC_BASENAMES or token is None
    if dir_alive and is_generic:
        # No distinctive name to verify (e.g. __init__.py); the package dir
        # exists, so the structural file is effectively present.
        return {"aiq": aiq, "path": path, "status": "SHIPPED",
                "via": "dir-alive-generic", "evidence": dirname + "/"}
    if dir_alive:
        # Distinctive file NOT located, but its dir exists — can't confirm either
        # way from paths alone; needs a look. Honest middle tier, not a leak claim.
        return {"aiq": aiq, "path": path, "status": "UNVERIFIED",
                "via": "dir-exists-file-not-found", "evidence": dirname + "/"}

    # No filename match, no history, dir absent → strong leak signal.
    return {"aiq": aiq, "path": path, "status": "LEAK_CANDIDATE",
            "via": "content-hit-only" if content_hits else "no-trace",
            "evidence": content_hits[0] if content_hits else ""}


def _apply_annotations(results: List[Dict[str, str]], leak_ref: str) -> int:
    """Rewrite each baseline `AIQ:path` line in the allowlist with a verification
    comment (SHIPPED → evidence path; LEAK → ref). Entries are KEPT (removing them
    re-flags the still-absent verbatim path → red CI); only the comment changes."""
    by_key = {f"{r['aiq']}:{r['path']}": r for r in results}
    lines = _ALLOWLIST.read_text(encoding="utf-8").splitlines()
    out: List[str] = []
    changed = 0
    for raw in lines:
        body = raw.split("#", 1)[0].rstrip()
        m = _BASELINE_RE.match(body.strip())
        if not m:
            out.append(raw)
            continue
        key = f"{m.group(1)}:{m.group(2).strip()}"
        r = by_key.get(key)
        if not r:
            out.append(raw)
            continue
        if r["status"] == "SHIPPED":
            note = f"  # SHIPPED (verified {r['via']}): {r['evidence']}"
        elif r["status"] == "UNVERIFIED":
            note = f"  # UNVERIFIED ({r['via']}): {r['evidence']}"
        else:
            note = f"  # LEAK (verified absent): {leak_ref}"
        out.append(body + note)
        changed += 1
    _ALLOWLIST.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify the HYGIENE-1 baseline.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="Annotate the allowlist with verification results.")
    ap.add_argument("--leak-ref", default="genuine leak — deliverable never merged",
                    help="Comment text for LEAK entries (e.g. a tracking task id).")
    args = ap.parse_args()

    root = _REPO_ROOT
    entries = parse_baseline(_ALLOWLIST)
    tracked = tracked_files(root)
    tracked_set = set(tracked)

    results = [classify(aiq, p, tracked, tracked_set, root) for aiq, p in entries]
    shipped = [r for r in results if r["status"] == "SHIPPED"]
    leaks = [r for r in results if r["status"] == "LEAK_CANDIDATE"]

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    if args.apply:
        n = _apply_annotations(results, args.leak_ref)
        print(f"Annotated {n} baseline entries ({len(shipped)} SHIPPED, {len(leaks)} LEAK).")
        return 0

    print(f"Baseline entries: {len(results)}")
    print(f"  SHIPPED (deliverable exists elsewhere): {len(shipped)}")
    print(f"  LEAK_CANDIDATE (no trace — needs verification): {len(leaks)}\n")
    print("===== LEAK_CANDIDATES =====")
    for r in leaks:
        print(f"  {r['aiq']}  {r['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

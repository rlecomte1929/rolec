#!/usr/bin/env python3
"""Guard: the delivery gate's loader mirror must not drift from the real loader.

``scripts/check_otto_batches.py`` hard-codes ``LOADER_FACT_TYPES`` and
``LOADER_DOMAIN_AREAS`` to mirror the sets in the deployed loader,
``supabase/functions/otto-loader/index.ts`` (``FACT_TYPES`` and ``ALLOWED_DOMAINS``).
The loader does not reject an out-of-set value — it silently rewrites it (``domain_area``
-> ``"other"``; ``fact_type`` -> ``"other"``). The gate exists to catch that *before*
load. But a gate that mirrors the loader by copy is only as good as the copy: if the
loader's allow-lists change and the gate's copies do not, the gate grades batches against
a stale taxonomy and reports green on a batch the loader would quietly mangle.

This guard parses both sets straight from source and fails when they diverge. It is the
same "a gate whose own config can drift while it is skipped reports green" reasoning the
CI ``corridor_facts`` / ``migrations`` path filters are built on.

stdlib only; no network or DB. Exit 0 in sync (or loader absent -> skipped), 1 on drift,
2 when the gate itself is missing / cannot be parsed.

    python scripts/check_gate_loader_sync.py
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_PATH = os.path.join(PROJECT_ROOT, "scripts", "check_otto_batches.py")
LOADER_PATH = os.path.join(PROJECT_ROOT, "supabase", "functions", "otto-loader", "index.ts")


def load_gate_sets():
    """Import the gate module and read its live constants (not a regex of its text)."""
    spec = importlib.util.spec_from_file_location("check_otto_batches", GATE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # safe: gate does its work under if __name__ == "__main__"
    return set(mod.LOADER_FACT_TYPES), set(mod.LOADER_DOMAIN_AREAS)


def parse_loader_set(src: str, name: str) -> set:
    """Extract the string members of ``const <name> = new Set([...])`` from the loader."""
    m = re.search(r"const\s+%s\s*=\s*new\s+Set\(\s*\[(.*?)\]\s*\)" % re.escape(name), src, re.S)
    if not m:
        raise ValueError("could not find `const %s = new Set([...])` in the loader" % name)
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def main() -> int:
    if not os.path.isfile(GATE_PATH):
        sys.stderr.write("gate not found: %s\n" % GATE_PATH)
        return 2
    if not os.path.isfile(LOADER_PATH):
        # The deployed loader can be absent from a clean checkout (CI, a fresh worktree)
        # when it is not yet tracked. This guard is a best-effort mirror: skip rather than
        # fail when there is nothing to compare against — it activates automatically once
        # supabase/functions/otto-loader/index.ts is committed. It still runs wherever the
        # loader is present (a local working tree, or any checkout that tracks it).
        print("[SKIP] loader not present at %s — drift check skipped "
              "(activates once the loader is tracked)"
              % os.path.relpath(LOADER_PATH, PROJECT_ROOT))
        return 0
    try:
        gate_ft, gate_da = load_gate_sets()
        src = open(LOADER_PATH, encoding="utf-8").read()
        loader_ft = parse_loader_set(src, "FACT_TYPES")
        loader_da = parse_loader_set(src, "ALLOWED_DOMAINS")
    except Exception as e:  # noqa: BLE001 - report any parse/import failure as a usage error
        sys.stderr.write("parse error: %s\n" % e)
        return 2

    ok = True
    for label, gate_set, loader_set in (
        ("fact_type   (gate LOADER_FACT_TYPES  vs loader FACT_TYPES)", gate_ft, loader_ft),
        ("domain_area (gate LOADER_DOMAIN_AREAS vs loader ALLOWED_DOMAINS)", gate_da, loader_da),
    ):
        if gate_set == loader_set:
            print("[OK]    %s - %d values match" % (label, len(gate_set)))
            continue
        ok = False
        print("[DRIFT] %s" % label)
        only_gate = sorted(gate_set - loader_set)
        only_loader = sorted(loader_set - gate_set)
        if only_gate:
            print("          in gate only   : %s" % only_gate)
        if only_loader:
            print("          in loader only : %s" % only_loader)

    if ok:
        print("\nVERDICT: PASS - gate mirrors the loader's allow-lists exactly")
        return 0
    print("\nVERDICT: FAIL - reconcile scripts/check_otto_batches.py with "
          "supabase/functions/otto-loader/index.ts")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""CI coverage for the Otto-batch gate's loader mirror.

Runs in the backend pytest lane (ci.yml collects scripts/tests). It asserts the delivery
gate's LOADER_FACT_TYPES / LOADER_DOMAIN_AREAS still equal the deployed loader's
FACT_TYPES / ALLOWED_DOMAINS, so the offline gate can never grade batches against a stale
taxonomy. The real logic lives in scripts/check_gate_loader_sync.py; this is the thin
wrapper that makes it gate a PR.
"""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gate_loader_allowlists_in_sync():
    sync = _load("check_gate_loader_sync", "scripts/check_gate_loader_sync.py")
    assert sync.main() == 0, (
        "gate<->loader allow-list drift: scripts/check_otto_batches.py no longer mirrors "
        "supabase/functions/otto-loader/index.ts. Run scripts/check_gate_loader_sync.py."
    )

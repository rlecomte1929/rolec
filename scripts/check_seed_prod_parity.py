#!/usr/bin/env python3
"""Seed/prod parity guard for form-fill field mappings (nightly).

Assert that ``public.form_field_mappings`` in PROD contains exactly the
``(field_kind, form_field_id)`` set each real government form is supposed to have,
per the declarative manifest at ``scripts/seed_prod_parity_manifest.json``.

Why this exists
---------------
Form-fill seed migrations are merged to the repo but applied to prod OUT-OF-BAND —
there is no apply-on-merge and the Supabase applier has been jammed since 2026-04-22.
Three merged form-fill migrations silently never reached prod for months: FR served
STALE fictional field ids (``nom``/``prenoms``/… from the original imm11 seed, which
the real-AcroForm re-seed was supposed to replace) and ES had no field mappings at all.
Nothing caught it — the fill tests run against committed PDF fixtures + in-code
``CHOICE_GROUPS`` (never prod), the ledger isn't reconciled for hand-applied migrations,
and a row-COUNT check passes happily on stale rows (FR had 12 rows, just the wrong ones).

The only way to catch "merged but never applied (or applied stale)" is to read PROD and
compare its actual field ids to the expected set. This guard does exactly that, failing
loudly on BOTH missing and stale rows. It runs nightly (not as a PR gate): a brand-new
form's rows are applied AFTER merge, so prod legitimately would not have them at PR time.

Exit codes
----------
  0 — every form matches the manifest, OR DATABASE_URL is not set (nothing to check).
  1 — DRIFT: at least one form is missing expected rows and/or carries stale/unexpected ones.
  2 — CONFIG/CONNECTION error (psycopg2 missing, cannot connect, manifest malformed).

Usage
-----
  DATABASE_URL=postgresql://<readonly>@host:5432/postgres python scripts/check_seed_prod_parity.py
  python scripts/check_seed_prod_parity.py --manifest scripts/seed_prod_parity_manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

TABLE = "public.form_field_mappings"
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "seed_prod_parity_manifest.json"

# Expected/actual shape: {form_id: {field_kind: {form_field_id, ...}}}
FormMap = Dict[str, Dict[str, Set[str]]]


def load_manifest(path: Path) -> FormMap:
    """Load the manifest's ``form_field_mappings`` block into sets.

    Raises ValueError on a malformed manifest so main() can turn it into exit 2 — a
    guard whose own config is broken must fail, never silently pass.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest {path}: {exc}") from exc
    forms = raw.get("form_field_mappings")
    if not isinstance(forms, dict) or not forms:
        raise ValueError(f"manifest {path} has no non-empty 'form_field_mappings' object")
    out: FormMap = {}
    for form_id, kinds in forms.items():
        if not isinstance(kinds, dict) or not kinds:
            raise ValueError(f"manifest form '{form_id}' must map field_kind -> [field_ids]")
        out[form_id] = {}
        for kind, ids in kinds.items():
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                raise ValueError(f"manifest {form_id}[{kind}] must be a list of strings")
            id_set = set(ids)
            if len(id_set) != len(ids):
                raise ValueError(f"manifest {form_id}[{kind}] has duplicate field ids")
            out[form_id][kind] = id_set
    return out


def diff_form(form_id: str, expected: Dict[str, Set[str]], actual: Dict[str, Set[str]]) -> List[str]:
    """Return a list of human-readable problems for one form. Empty list == in parity.

    Catches BOTH directions, which is the whole point:
      * MISSING  — an expected field id is absent in prod (a seed that never applied).
      * STALE    — prod carries a field id (of a kind we manage) that the manifest does
                   not list (a superseded row a re-seed should have replaced, e.g. FR's
                   old fictional ``nom``/``prenoms``).
    Only field_kinds named in the manifest for this form are policed, so unrelated rows
    a form may legitimately carry in other kinds are never flagged.
    """
    problems: List[str] = []
    for kind, exp_ids in sorted(expected.items()):
        act_ids = actual.get(kind, set())
        missing = exp_ids - act_ids
        stale = act_ids - exp_ids
        if missing:
            problems.append(f"{form_id} [{kind}]: MISSING {sorted(missing)}")
        if stale:
            problems.append(f"{form_id} [{kind}]: STALE/UNEXPECTED {sorted(stale)}")
    return problems


def check(manifest: FormMap, actual: FormMap) -> Tuple[int, str]:
    """Compare the whole manifest against fetched prod content. Pure; DB-free."""
    problems: List[str] = []
    for form_id, expected in sorted(manifest.items()):
        problems.extend(diff_form(form_id, expected, actual.get(form_id, {})))
    n_forms = len(manifest)
    if problems:
        body = "\n".join(f"  - {p}" for p in problems)
        return 1, (
            f"[seed-prod-parity] DRIFT — {len(problems)} problem(s) across {n_forms} form(s) "
            f"in {TABLE}:\n{body}\n\n"
            "A form is missing expected rows and/or carries stale ones. This usually means a "
            "form-fill seed migration was merged but never applied to prod (or a re-seed did not "
            "run). Apply the migration to prod and reconcile the ledger, then re-run. If the "
            "manifest itself is out of date after an intentional change, update "
            "scripts/seed_prod_parity_manifest.json in the same PR."
        )
    total_ids = sum(len(ids) for kinds in manifest.values() for ids in kinds.values())
    return 0, (
        f"[seed-prod-parity] OK — {n_forms} form(s), {total_ids} expected field mapping(s) "
        f"all present and current in {TABLE}."
    )


def fetch_actual(db_url: str, form_ids: List[str]) -> FormMap:
    """Read prod's actual (field_kind, form_field_id) sets for the given forms.

    Read-only. Raises RuntimeError on any driver/connection problem so main() maps it to
    exit 2 (a guard that cannot measure must not report green).
    """
    try:
        import psycopg2  # lazy: keeps DB-free unit tests import-clean
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "psycopg2 not installed — `pip install psycopg2-binary` or run from the backend venv"
        ) from exc
    actual: FormMap = {}
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:  # noqa: BLE001 - surface any connect failure as config error
        raise RuntimeError(f"could not connect to DATABASE_URL: {exc}") from exc
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT form_id, field_kind, form_field_id "
                "FROM public.form_field_mappings WHERE form_id = ANY(%s)",
                (form_ids,),
            )
            for form_id, field_kind, form_field_id in cur.fetchall():
                actual.setdefault(form_id, {}).setdefault(field_kind, set()).add(form_field_id)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"query against {TABLE} failed: {exc}") from exc
    finally:
        conn.close()
    return actual


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed/prod parity guard for form-fill mappings.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except ValueError as exc:
        print(f"[seed-prod-parity] CONFIG ERROR — {exc}", file=sys.stderr)
        return 2

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # No prod access -> nothing to measure. Skip loudly (exit 0). The nightly workflow
        # only runs this when vars.RLS_COVERAGE_DATABASE_URL_SET == 'true', so a real run
        # always has a URL; this branch is for local/fork runs.
        print(
            "[seed-prod-parity] SKIP — DATABASE_URL not set; nothing to check. "
            "(In CI this runs only when the read-only prod secret is configured.)"
        )
        return 0

    try:
        actual = fetch_actual(db_url, sorted(manifest.keys()))
    except RuntimeError as exc:
        print(f"[seed-prod-parity] CONFIG/CONNECTION ERROR — {exc}", file=sys.stderr)
        return 2

    code, report = check(manifest, actual)
    print(report, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

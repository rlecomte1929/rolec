#!/usr/bin/env python3
"""Orchestrate one Otto batch: confirm_quotes → verify_ledger → import_otto_facts → promote.

This is the chain an operator used to run by hand, minus the two ways that chain has bitten
us: (1) `--promote` implying `--apply` and writing `requirement_items`, (2) a promote that
collides with an already-approved row and rewrites it because the upsert key is
`(country_code, purpose, title)`.

THIS SCRIPT NEVER WRITES TO A DATABASE. `executor.promote` is called with `dry_run=True`
only. There is no `--apply` flag. `review_status` is not flipped. The append-only tripwire
(approved count + md5 over approved ids, plus the expert_verified count) is printed as a
preview so a later live apply can prove it did not move those rows.

    python scripts/import_pipeline.py ie-eu-eea-freemover-2026-08-22
    python scripts/import_pipeline.py --ledger docs/imports/ie-eu-eea-freemover-2026-08-22/facts.ndjson

`--no-fetch` is the default for verify_ledger (V2 liveness is a network call) and keeps
confirm_quotes off the wire: it classifies against an injected cache, which tests and the
offline sample run fill themselves. Pass `--fetch` to let confirm_quotes curl.

Exit codes
----------
  0  every step passed; promote dry-run report printed
  1  blocked (HOLD_* quotes, verify_ledger rejected the batch, parser rejections,
     permission content scoped to OWN_NATIONAL)
  2  the run could not happen (missing ledger, missing script, refused prod URL)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

HOLD_VERDICTS = frozenset({"HOLD_IMAGE_PDF", "HOLD_WRONG_SRC", "HOLD_ABSENT"})
SCRIPTS = REPO_ROOT / "scripts"
IMPORTS_ROOT = REPO_ROOT / "docs" / "imports"


@dataclass
class StepResult:
    name: str
    ok: bool
    blocked: bool = False
    detail: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineReport:
    batch_id: str
    ledger: str
    status: str  # pass | blocked | fail
    exit_code: int
    steps: List[StepResult] = field(default_factory=list)
    promote: Dict[str, Any] = field(default_factory=dict)
    tripwire: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "ledger": self.ledger,
            "status": self.status,
            "exit_code": self.exit_code,
            "steps": [
                {
                    "name": s.name,
                    "ok": s.ok,
                    "blocked": s.blocked,
                    "detail": s.detail,
                    **s.extra,
                }
                for s in self.steps
            ],
            "promote": self.promote,
            "tripwire": self.tripwire,
        }


def load_script(name: str) -> Any:
    """Load `scripts/<name>.py` as a module. Does not reimplement it."""
    path = SCRIPTS / f"{name}.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(f"import_pipeline_{name}", path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def looks_like_prod_database_url(url: str) -> bool:
    """Refuse the URLs this repo actually points at production with.

    A throwaway local postgres is fine; the pooler hostname and the Render flag are not.
    """
    if os.environ.get("RENDER") or os.environ.get("ENV") == "production":
        return True
    lowered = (url or "").lower()
    return "supabase.co" in lowered or "nsvefcvpvwwwhuqyuqmp" in lowered


def approved_fingerprint(ids: Sequence[str]) -> str:
    """md5 over sorted approved ids — the append-only tripwire.

    A later apply that rewrites an approved row changes this digest even if the count
    stays the same. Empty input is a real fingerprint (md5 of the empty string), not a
    skip: a tripwire that prints nothing proves nothing.
    """
    blob = "\n".join(sorted(ids))
    return hashlib.md5(blob.encode("utf-8")).hexdigest()


def format_tripwire(tripwire: Dict[str, Any]) -> str:
    queried = "queried" if tripwire.get("queried") else "offline — not queried"
    return (
        "append-only tripwire (preview — no writes):\n"
        f"  approved: {tripwire.get('approved_count', 0)}  "
        f"md5: {tripwire.get('approved_md5', approved_fingerprint(()))}\n"
        f"  expert_verified: {tripwire.get('expert_verified_count', 0)}\n"
        f"  ({queried})"
    )


def resolve_ledger(target: str) -> Path:
    """A batch id under docs/imports/, or a path to an NDJSON ledger."""
    given = Path(target)
    if given.is_file():
        return given.resolve()
    batch_dir = IMPORTS_ROOT / target
    for name in ("facts.ndjson", "clean.ndjson", "ledger.ndjson"):
        cand = batch_dir / name
        if cand.is_file():
            return cand.resolve()
    if given.suffix:
        return given.resolve()
    raise FileNotFoundError(
        f"no ledger for {target!r}; looked at {given} and {batch_dir}/{{facts,clean,ledger}}.ndjson"
    )


def _read_ndjson(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            rec = {"_bad_json": True, "lineno": lineno, "raw": line}
        rows.append(rec)
    return rows


def _offline_tripwire() -> Dict[str, Any]:
    return {
        "approved_count": 0,
        "approved_md5": approved_fingerprint(()),
        "expert_verified_count": 0,
        "queried": False,
    }


def query_tripwire(conn: Any) -> Dict[str, Any]:
    """Read-only snapshot of the rows a promote must not touch."""
    from sqlalchemy import text

    approved_ids = [
        str(r[0])
        for r in conn.execute(
            text(
                "SELECT id FROM public.requirement_items "
                "WHERE review_status = 'approved' ORDER BY id"
            )
        )
    ]
    expert = conn.execute(
        text(
            "SELECT count(*) FROM public.requirement_items "
            "WHERE verification_status = 'expert_verified'"
        )
    ).scalar()
    return {
        "approved_count": len(approved_ids),
        "approved_md5": approved_fingerprint(approved_ids),
        "expert_verified_count": int(expert or 0),
        "queried": True,
    }


def _promote_from_rows(fact_rows: Sequence[Any]) -> Any:
    """File-side promote preview: `mappings.resolve` over the ledger, no session.

    `executor.promote` reads `otto_staging` and needs a live connection. The pipeline's
    default is no connection, so the preview is what the file would become, using the
    same resolver the executor uses.
    """
    from backend.imports.otto.executor import PromoteResult
    from backend.imports.otto.mappings import Unmapped, resolve

    result = PromoteResult()
    groups: Dict[Any, List[Any]] = {}
    entities: Dict[Any, Any] = {}
    for row in fact_rows:
        key = (row.destination_country, row.entity_topic_key)
        groups.setdefault(key, []).append(row)
        entities[key] = SimpleNamespace(
            destination_country=row.destination_country,
            topic_key=row.entity_topic_key,
            title=getattr(row, "entity_title", None) or row.entity_topic_key,
            domain_area="immigration",
        )
    for key, facts in groups.items():
        preview = []
        for i, fact in enumerate(facts):
            # `resolve()` reads `.id` off staging rows; a file-side FactRow has none.
            preview.append(SimpleNamespace(**{**vars(fact), "id": f"preview-{i}"}))
        draft = resolve(entities[key], preview)
        if isinstance(draft, Unmapped):
            result.unmapped.append(f"{key[0]}/{draft.topic_key}: {draft.reason}")
            continue
        result.drafts.append(draft)
        result.promoted += 1
    return result


def run_pipeline(
    target: str,
    *,
    fetch: bool = False,
    classify_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    verify_fn: Optional[Callable[[Path], int]] = None,
    import_mod: Any = None,
    promote_fn: Optional[Callable[..., Any]] = None,
    tripwire_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    confirm_cache: Optional[Dict[str, bytes]] = None,
) -> PipelineReport:
    """Run the four steps. Injected callables are for tests; defaults load the real scripts."""
    try:
        ledger = resolve_ledger(target)
    except FileNotFoundError as exc:
        report = PipelineReport(
            batch_id=target, ledger="", status="fail", exit_code=2,
        )
        report.steps.append(StepResult("resolve", ok=False, detail=str(exc)))
        return report

    batch_id = ledger.parent.name if ledger.parent.name else ledger.stem
    report = PipelineReport(batch_id=batch_id, ledger=str(ledger), status="pass", exit_code=0)

    records = _read_ndjson(ledger)

    # ── 1. confirm_quotes ────────────────────────────────────────────────────
    try:
        classify = classify_fn or load_script("confirm_quotes").classify
    except FileNotFoundError as exc:
        report.status, report.exit_code = "fail", 2
        report.steps.append(StepResult("confirm_quotes", ok=False, detail=str(exc)))
        return report

    cache = confirm_cache if confirm_cache is not None else {}
    if not fetch and confirm_cache is None:
        # Offline: do not curl. An empty body is a stub, which classify maps to REVIEW_BROWSER
        # — tests that want CONFIRMED inject a cache or a classify_fn.
        cache = {str(r.get("source_url") or ""): b"" for r in records if not r.get("_bad_json")}

    quote_rows = []
    for rec in records:
        if rec.get("_bad_json"):
            continue
        rec.setdefault("_batch", batch_id)
        quote_rows.append(classify(rec, cache))
    holds = [r for r in quote_rows if r.get("verdict") in HOLD_VERDICTS]
    confirm_ok = not holds
    report.steps.append(
        StepResult(
            "confirm_quotes",
            ok=confirm_ok,
            blocked=bool(holds),
            detail=f"{len(quote_rows)} fact(s), {len(holds)} HOLD",
            extra={
                "holds": [r.get("verdict") for r in holds],
                "verdicts": [r.get("verdict") for r in quote_rows],
            },
        )
    )
    if holds:
        report.status, report.exit_code = "blocked", 1
        report.tripwire = _offline_tripwire()
        return report

    # ── 2. verify_ledger ─────────────────────────────────────────────────────
    def _default_verify(path: Path) -> int:
        return int(load_script("verify_ledger").main([str(path), "--no-fetch"]))

    try:
        verify_code = (verify_fn or _default_verify)(ledger)
    except FileNotFoundError as exc:
        report.status, report.exit_code = "fail", 2
        report.steps.append(StepResult("verify_ledger", ok=False, detail=str(exc)))
        return report

    if verify_code != 0:
        report.status = "blocked" if verify_code == 1 else "fail"
        report.exit_code = verify_code if verify_code in (1, 2) else 1
        report.steps.append(
            StepResult(
                "verify_ledger",
                ok=False,
                blocked=verify_code == 1,
                detail=f"exit {verify_code}",
            )
        )
        report.tripwire = _offline_tripwire()
        return report
    report.steps.append(StepResult("verify_ledger", ok=True, detail="exit 0"))

    # ── 3. import_otto_facts (read/validate only — never --apply) ────────────
    if import_mod is None:
        try:
            import_mod = load_script("import_otto_facts")
        except FileNotFoundError as exc:
            report.status, report.exit_code = "fail", 2
            report.steps.append(StepResult("import_otto_facts", ok=False, detail=str(exc)))
            return report

    try:
        rows, rejections = import_mod.read_jsonl(ledger, batch_id=batch_id)
    except Exception as exc:  # parsers.FactRowError included
        report.status, report.exit_code = "fail", 2
        report.steps.append(StepResult("import_otto_facts", ok=False, detail=str(exc)))
        report.tripwire = _offline_tripwire()
        return report

    if rejections:
        report.status, report.exit_code = "blocked", 1
        report.steps.append(
            StepResult(
                "import_otto_facts",
                ok=False,
                blocked=True,
                detail=f"{len(rejections)} rejection(s)",
                extra={"rejections": list(rejections)},
            )
        )
        report.tripwire = _offline_tripwire()
        return report

    destinations = import_mod.destinations_for(rows)
    report.steps.append(
        StepResult(
            "import_otto_facts",
            ok=True,
            detail=f"{len(rows)} row(s), destinations={destinations}",
            extra={"destinations": destinations, "apply": False},
        )
    )

    # ── 4. promote(dry_run=True) ─────────────────────────────────────────────
    if promote_fn is not None:
        promoted = promote_fn(rows, destinations)
        if getattr(promoted, "dry_run", True) is False:
            report.status, report.exit_code = "fail", 2
            report.steps.append(
                StepResult("promote", ok=False, detail="promote_fn returned dry_run=False")
            )
            return report
    else:
        promoted = _promote_from_rows(rows)

    from backend.imports.otto.executor import summarise_promotion

    try:
        ns_mod = load_script("check_nationality_scope")
    except FileNotFoundError as exc:
        report.status, report.exit_code = "fail", 2
        report.steps.append(StepResult("check_nationality_scope", ok=False, detail=str(exc)))
        return report

    ns_rows = []
    for draft in getattr(promoted, "drafts", ()) or ():
        payload = getattr(draft, "payload", {}) or {}
        ns_rows.append(
            {
                "country_code": payload.get("country_code") or getattr(draft, "country_code", ""),
                "title": payload.get("title") or getattr(draft, "title", ""),
                "applies_to_nationality_classes_json": payload.get(
                    "applies_to_nationality_classes_json"
                ),
            }
        )
    offenders = ns_mod.scan(ns_rows)
    if offenders:
        report.status, report.exit_code = "blocked", 1
        report.steps.append(
            StepResult(
                "check_nationality_scope",
                ok=False,
                blocked=True,
                detail=f"{len(offenders)} OWN_NATIONAL permission row(s)",
                extra={"offenders": [f"{c}: {t}" for c, t in offenders]},
            )
        )
        report.tripwire = (tripwire_fn or _offline_tripwire)()
        return report
    report.steps.append(StepResult("check_nationality_scope", ok=True, detail="clean"))

    report.promote = {
        "dry_run": True,
        "promoted": int(getattr(promoted, "promoted", 0) or 0),
        "skipped_verified": list(getattr(promoted, "skipped_verified", []) or []),
        "unmapped": list(getattr(promoted, "unmapped", []) or []),
        "review_status": "pending",  # what a live promote would write; not written here
        "summary": summarise_promotion(promoted),
    }
    report.steps.append(
        StepResult(
            "promote",
            ok=True,
            detail=f"dry_run=True, {report.promote['promoted']} requirement(s)",
            extra={"dry_run": True},
        )
    )

    report.tripwire = (tripwire_fn or _offline_tripwire)()
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("target", nargs="?", help="batch id under docs/imports/ or a ledger path")
    ap.add_argument("--ledger", help="explicit path to the NDJSON ledger")
    ap.add_argument(
        "--fetch",
        action="store_true",
        help="let confirm_quotes curl sources (default: offline cache / empty body)",
    )
    args = ap.parse_args(argv)

    target = args.ledger or args.target
    if not target:
        ap.error("pass a batch id or --ledger PATH")

    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and looks_like_prod_database_url(db_url):
        print("✖ refusing DATABASE_URL that looks like production — this CLI is dry-run only.")
        return 2

    report = run_pipeline(target, fetch=args.fetch)
    for step in report.steps:
        mark = "✔" if step.ok else ("◐" if step.blocked else "✖")
        print(f"{mark} {step.name}: {step.detail}")
    if report.promote:
        print()
        print(report.promote.get("summary") or f"promote dry-run: {report.promote}")
        print("  review_status would stay pending (not written)")
    print()
    print(format_tripwire(report.tripwire or _offline_tripwire()))
    print()
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False, default=str))
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

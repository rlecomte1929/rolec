#!/usr/bin/env python3
"""Resumable corridor-fact batch orchestrator.

Drives existing CLIs by subprocess and stops at a promote dry-run. It never
commits a promote, never flips status='ready' in a committed transaction, and
never acks the Otto bus. Default run writes nothing to the DB; ``--stage`` is
the single opt-in write (otto_staging, status='new').

    python scripts/corridor_harness.py run docs/imports/<batch>
    python scripts/corridor_harness.py run <…> --stage
    python scripts/corridor_harness.py resume <batch-id>
    python scripts/corridor_harness.py status <batch-id>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
IMPORTS_ROOT = REPO_ROOT / "docs" / "imports"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_GATE = 10
EXIT_PAUSE = 20
EXIT_SCOPE = 30

PARSERS_VOCAB_KEYS = ("entity_topic_key", "fact_key", "destination_country")
STAGE_DEFS: Tuple[Tuple[int, str], ...] = (
    (0, "ingest"),
    (1, "reconcile"),
    (2, "convert"),
    (3, "referee"),
    (4, "stage"),
    (5, "prepromote"),
    (6, "promote_dry"),
)

FINGERPRINT_SQL = """
SELECT count(*) FILTER (WHERE review_status='approved')                              AS approved,
       count(*) FILTER (WHERE verification_status IN ('verified','expert_verified')) AS human_verified,
       md5(string_agg(id||title||coalesce(description,'')||coalesce(verification_status,'')||coalesce(review_status,''),
                      '|' ORDER BY id)
           FILTER (WHERE review_status='approved'
                      OR verification_status IN ('verified','expert_verified')))     AS fp_protected
FROM public.requirement_items
WHERE country_code = :iso
"""

READY_FLIP_SQL = (
    "UPDATE otto_staging.immigration_fact_candidates SET status='ready' "
    "WHERE batch_id=:b AND destination_country=:iso AND status='new'"
)

READY_COUNT_SQL = (
    "SELECT count(*) FROM otto_staging.immigration_fact_candidates "
    "WHERE batch_id=:b AND destination_country=:iso AND status='ready'"
)

# Status values the serving path already understands. Anything else lands purpose='other'.
RECOGNISED_STATUS = {
    "employee",
    "professional",
    "worker",
    "self-employed",
    "self_employed",
    "student",
    "posted",
    "family",
    "dependent",
    "third_country",
    "eu_eea",
    "freelancer",
}

_PERMISSION_HINTS = (
    "registration",
    "permit",
    "residence card",
    "carte de sejour",
    "carte de séjour",
    "visa",
    "immigration",
)


class ToolRunner(Protocol):
    def run(self, argv: List[str]) -> subprocess.CompletedProcess[str]: ...


class Transport(Protocol):
    def get(self, url: str) -> bytes: ...


@dataclass
class Continue:
    notes: str = ""
    artifact: Optional[str] = None
    skipped: bool = False
    exit: int = 0
    stdout_tail: str = ""


@dataclass
class Gate:
    code: int
    msg: str
    exit: int = 0
    stdout_tail: str = ""
    artifact: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.exit:
            self.exit = self.code


@dataclass
class Pause:
    code: int
    worklist_path: str
    msg: str = ""
    stdout_tail: str = ""


StageOutcome = Continue | Gate | Pause


@dataclass
class PromoteResult:
    promoted: int = 0
    skipped_verified: List[str] = field(default_factory=list)
    unmapped: List[str] = field(default_factory=list)
    drafts: List[Any] = field(default_factory=list)


class SubprocessToolRunner:
    def run(self, argv: List[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )


class UrlLibTransport:
    def get(self, url: str) -> bytes:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme == "file":
            return Path(urllib.request.url2pathname(parsed.path)).read_bytes()
        with urllib.request.urlopen(url) as resp:  # noqa: S310 — operator CLI, URL is the target
            return resp.read()


class UsageError(Exception):
    def __init__(self, msg: str, code: int = EXIT_USAGE) -> None:
        super().__init__(msg)
        self.code = code


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stdout_tail(proc: subprocess.CompletedProcess[str], n: int = 2000) -> str:
    blob = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return blob[-n:]


def write_atomic(path: Path, text_body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text_body, encoding="utf-8")
    os.replace(tmp, path)


def write_json_atomic(path: Path, obj: Any) -> None:
    write_atomic(path, json.dumps(obj, indent=2, default=str) + "\n")


def script_basename(argv: Sequence[str]) -> str:
    for part in argv:
        name = Path(part).name
        if name.endswith(".py"):
            return name
    return argv[-1] if argv else ""


def empty_stages() -> List[Dict[str, Any]]:
    return [{"n": n, "name": name, "status": "pending"} for n, name in STAGE_DEFS]


def new_checkpoint(
    batch_id: str,
    entry: Dict[str, str],
    *,
    stage_write_enabled: bool,
    no_fetch: bool,
) -> Dict[str, Any]:
    ts = now_iso()
    return {
        "batch_id": batch_id,
        "entry": entry,
        "started_at": ts,
        "updated_at": ts,
        "stage_flag": {
            "stage_write_enabled": stage_write_enabled,
            "no_fetch": no_fetch,
        },
        "stages": empty_stages(),
        "harness_exit": None,
    }


def load_checkpoint(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, ckpt: Dict[str, Any]) -> None:
    ckpt["updated_at"] = now_iso()
    write_json_atomic(path, ckpt)


def first_incomplete(ckpt: Dict[str, Any]) -> Optional[int]:
    for stage in ckpt["stages"]:
        if stage.get("status") not in ("ok", "skipped"):
            return int(stage["n"])
    return None


def checkpoint_complete(ckpt: Dict[str, Any]) -> bool:
    return first_incomplete(ckpt) is None and ckpt.get("harness_exit") == EXIT_OK


def patch_stage(ckpt: Dict[str, Any], n: int, **fields: Any) -> None:
    ckpt["stages"][n].update(fields)


def manifest_records(manifest: Dict[str, Any]) -> int:
    files = manifest.get("files")
    if isinstance(files, dict) and files:
        total = 0
        for meta in files.values():
            if not isinstance(meta, dict) or "records" not in meta:
                raise UsageError("manifest files.* must include records")
            total += int(meta["records"])
        return total
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        total = 0
        for art in artifacts:
            if not isinstance(art, dict) or "record_count" not in art:
                raise UsageError("manifest artifacts[] must include record_count")
            total += int(art["record_count"])
        return total
    raise UsageError("manifest is neither shape A (files) nor shape B (artifacts)")


def manifest_ndjson_urls(manifest: Dict[str, Any], base_url: str) -> List[str]:
    base = base_url.rsplit("/", 1)[0] + "/"

    def resolve(path: str) -> str:
        if path.startswith("http://") or path.startswith("https://") or path.startswith("file:"):
            return path
        return urllib.parse.urljoin(base, path)

    files = manifest.get("files")
    if isinstance(files, dict) and files:
        return [resolve(name) for name in files]
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        urls = []
        for art in artifacts:
            if not isinstance(art, dict) or "path" not in art:
                raise UsageError("manifest artifacts[] must include path")
            urls.append(resolve(str(art["path"])))
        return urls
    raise UsageError("manifest is neither shape A (files) nor shape B (artifacts)")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_ndjson(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def ndjson_line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def batch_ndjson_files(batch_dir: Path) -> List[Path]:
    return sorted(
        p
        for p in batch_dir.glob("*.ndjson")
        if p.is_file() and "_harness" not in p.parts
    )


def is_parsers_vocab(path: Path) -> bool:
    rows = iter_ndjson(path)
    if not rows:
        return False
    return all(all(k in rec for k in PARSERS_VOCAB_KEYS) for rec in rows)


def primary_ndjson(batch_dir: Path) -> Optional[Path]:
    files = batch_ndjson_files(batch_dir)
    for name in ("facts.ndjson", "corridor_facts.ndjson"):
        cand = batch_dir / name
        if cand.is_file():
            return cand
    return files[0] if files else None


def quote_script_supports(script: Path, flag: str) -> bool:
    if not script.is_file():
        return False
    return flag in script.read_text(encoding="utf-8", errors="replace")


def row_scalar(result: Any) -> Any:
    if result is None:
        return None
    if hasattr(result, "mappings"):
        mapped = result.mappings().first()
        if mapped is None:
            first = result.first() if hasattr(result, "first") else None
            return first
        return mapped
    if hasattr(result, "first"):
        return result.first()
    if isinstance(result, (list, tuple)):
        return result[0] if result else None
    return result


def fingerprint(session: Any, iso: str) -> Tuple[Any, Any, Any]:
    raw = session.execute(text(FINGERPRINT_SQL), {"iso": iso})
    row = row_scalar(raw)
    if row is None:
        return (0, 0, None)
    if hasattr(row, "_mapping"):
        row = dict(row._mapping)
    if isinstance(row, dict):
        return (row.get("approved"), row.get("human_verified"), row.get("fp_protected"))
    return (row[0], row[1], row[2])


def execute_count(session: Any, sql: str, params: Dict[str, Any]) -> int:
    raw = session.execute(text(sql), params)
    row = row_scalar(raw)
    if row is None:
        return 0
    if isinstance(row, dict):
        return int(next(iter(row.values())))
    if isinstance(row, (list, tuple)):
        return int(row[0])
    if hasattr(row, "__getitem__"):
        try:
            return int(row[0])
        except Exception:
            return int(row)
    return int(row)


def draft_title(draft: Any) -> str:
    if draft is None:
        return ""
    if isinstance(draft, dict):
        return str(draft.get("title") or draft.get("entity_title") or "")
    return str(getattr(draft, "title", None) or getattr(draft, "entity_title", "") or draft)


def default_promote_fn(session: Any, *, country: Optional[str] = None, dry_run: bool = True) -> Any:
    from backend.imports.otto.executor import promote

    return promote(session, country=country, dry_run=dry_run)


def default_session_factory() -> Any:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise UsageError("DATABASE_URL is not set", EXIT_USAGE)
    engine = create_engine(url, future=True)
    return sessionmaker(bind=engine)()


@dataclass
class Ctx:
    batch_id: str
    batch_dir: Path
    harness_dir: Path
    entry: Dict[str, str]
    stage_write: bool
    no_fetch: bool
    python: str
    runner: ToolRunner
    transport: Transport
    session_factory: Callable[[], Any]
    promote_fn: Callable[..., Any]
    bus_resolve: Optional[Callable[[], str]] = None
    ckpt: Dict[str, Any] = field(default_factory=dict)

    @property
    def run_path(self) -> Path:
        return self.harness_dir / "run.json"


def tool_argv(ctx: Ctx, script: str, *args: str) -> List[str]:
    return [ctx.python, str(SCRIPTS / script), *args]


def record_tool(ctx: Ctx, proc: subprocess.CompletedProcess[str]) -> str:
    return stdout_tail(proc)


# --- stages ------------------------------------------------------------------


def stage_0_ingest(ctx: Ctx) -> StageOutcome:
    kind = ctx.entry.get("kind", "local")
    target = ctx.entry.get("value", "")
    if kind == "bus":
        if ctx.bus_resolve is None:
            return Gate(EXIT_USAGE, "--from-bus requires an injected bus resolver")
        target = ctx.bus_resolve()
        ctx.entry = {"kind": "bus", "value": target}
        kind = "url" if target.startswith(("http://", "https://", "file:")) else "local"

    if kind == "url":
        try:
            raw = ctx.transport.get(target)
            manifest = json.loads(raw.decode("utf-8"))
        except UsageError:
            raise
        except Exception as exc:  # noqa: BLE001
            return Gate(EXIT_USAGE, f"failed to fetch manifest: {exc}")
        try:
            urls = manifest_ndjson_urls(manifest, target)
            _ = manifest_records(manifest)
        except UsageError as exc:
            return Gate(exc.code, str(exc))
        batch_id = str(manifest.get("batch_id") or ctx.batch_id)
        ctx.batch_id = batch_id
        ctx.batch_dir.mkdir(parents=True, exist_ok=True)
        (ctx.batch_dir / "manifest.json").write_bytes(raw)
        for url in urls:
            name = Path(urllib.parse.urlparse(url).path).name or "facts.ndjson"
            try:
                body = ctx.transport.get(url)
            except Exception as exc:  # noqa: BLE001
                return Gate(EXIT_USAGE, f"failed to fetch {url}: {exc}")
            (ctx.batch_dir / name).write_bytes(body)
        ctx.ckpt["batch_id"] = ctx.batch_id
        ctx.ckpt["entry"] = ctx.entry

    manifest_path = ctx.batch_dir / "manifest.json"
    ndjsons = batch_ndjson_files(ctx.batch_dir)
    if not manifest_path.is_file() or not ndjsons:
        return Gate(EXIT_USAGE, "target must contain manifest.json and at least one .ndjson")
    try:
        man = load_json(manifest_path)
        manifest_records(man)
        ctx.batch_id = str(man.get("batch_id") or ctx.batch_dir.name)
    except UsageError as exc:
        return Gate(exc.code, str(exc))
    ctx.ckpt["batch_id"] = ctx.batch_id
    return Continue(notes=f"dir populated ({len(ndjsons)} ndjson)")


def stage_1_reconcile(ctx: Ctx) -> StageOutcome:
    out = ctx.harness_dir / "reconcile.json"
    proc = ctx.runner.run(
        tool_argv(ctx, "check_otto_batches.py", ctx.batch_id, "--json", str(out))
    )
    tail = record_tool(ctx, proc)
    if proc.returncode != 0:
        return Gate(EXIT_GATE, f"reconcile failed (exit {proc.returncode})", stdout_tail=tail)
    return Continue(artifact="_harness/reconcile.json", stdout_tail=tail)


def stage_2_convert(ctx: Ctx) -> StageOutcome:
    src = primary_ndjson(ctx.batch_dir)
    if src is None:
        return Gate(EXIT_GATE, "no ndjson fact stream in batch dir")
    dest = ctx.harness_dir / "clean-input.ndjson"
    if is_parsers_vocab(src):
        shutil.copyfile(src, dest)
        return Continue(notes="already parsers vocab", skipped=True, artifact="_harness/clean-input.ndjson")
    converter = SCRIPTS / "convert_otto_batch.py"
    if not converter.is_file():
        return Gate(
            EXIT_GATE,
            "input is not parsers vocab and scripts/convert_otto_batch.py is missing (Brief C)",
        )
    proc = ctx.runner.run(
        tool_argv(ctx, "convert_otto_batch.py", str(src), "--out", str(dest))
    )
    tail = record_tool(ctx, proc)
    if proc.returncode != 0:
        return Gate(EXIT_GATE, f"convert failed (exit {proc.returncode})", stdout_tail=tail)
    return Continue(artifact="_harness/clean-input.ndjson", stdout_tail=tail)


def _write_coarse_worklist(ctx: Ctx) -> Path:
    grounding = ctx.harness_dir / "grounding"
    grounding.mkdir(parents=True, exist_ok=True)
    src = ctx.harness_dir / "worklist.ndjson"
    rows: List[Any] = []
    if src.is_file():
        for line in src.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                rows.append(
                    {
                        "source_url": rec.get("source_url"),
                        "evidence_quote": rec.get("evidence_quote"),
                        "dedupe_key": rec.get("dedupe_key")
                        or rec.get("fact_key")
                        or rec.get("entity_topic_key"),
                        "status": "unreachable",
                    }
                )
    if not rows:
        rows = [{"source_url": None, "status": "unreachable", "note": "unconfirmed quotes present"}]
    dest = grounding / "worklist.json"
    write_json_atomic(dest, rows)
    return dest


def stage_3_referee(ctx: Ctx) -> StageOutcome:
    clean_input = ctx.harness_dir / "clean-input.ndjson"
    if not clean_input.is_file():
        return Gate(EXIT_GATE, "clean-input.ndjson missing")
    ledger_argv = tool_argv(
        ctx,
        "verify_ledger.py",
        str(clean_input),
        "--apply",
        "--out",
        str(ctx.harness_dir),
    )
    if ctx.no_fetch:
        ledger_argv.append("--no-fetch")
    proc = ctx.runner.run(ledger_argv)
    tail = record_tool(ctx, proc)
    if proc.returncode in (1, 2):
        return Gate(EXIT_GATE, f"verify_ledger failed (exit {proc.returncode})", stdout_tail=tail)
    if proc.returncode != 0:
        return Gate(EXIT_GATE, f"verify_ledger failed (exit {proc.returncode})", stdout_tail=tail)

    quote_script = SCRIPTS / "verify_batch_quotes.py"
    quote_argv = tool_argv(ctx, "verify_batch_quotes.py", str(ctx.batch_dir))
    report_path = ctx.harness_dir / "quotes-report.json"
    has_report = quote_script_supports(quote_script, "--report") or not quote_script.is_file()
    has_grounding = quote_script_supports(quote_script, "--grounding-dir") or not quote_script.is_file()
    if has_grounding:
        quote_argv.extend(["--grounding-dir", str(ctx.harness_dir / "grounding")])
    if has_report:
        quote_argv.extend(["--report", str(report_path)])
    qproc = ctx.runner.run(quote_argv)
    tail = (tail + "\n" + record_tool(ctx, qproc)).strip()

    if report_path.is_file():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("sources") or payload.get("rows") or []
        blocked = [r for r in rows if (r.get("status") in ("unreachable", "blocked"))]
        if blocked:
            dest = ctx.harness_dir / "grounding" / "worklist.json"
            write_json_atomic(dest, blocked)
            return Pause(EXIT_PAUSE, "_harness/grounding/worklist.json", stdout_tail=tail)

    if qproc.returncode != 0:
        dest = _write_coarse_worklist(ctx)
        return Pause(
            EXIT_PAUSE,
            "_harness/grounding/worklist.json",
            msg="unconfirmed quotes present",
            stdout_tail=tail,
        )
    return Continue(artifact="_harness/clean.ndjson", stdout_tail=tail)


def stage_4_stage(ctx: Ctx) -> StageOutcome:
    clean = ctx.harness_dir / "clean.ndjson"
    if not clean.is_file():
        return Gate(EXIT_GATE, "clean.ndjson missing")
    n = ndjson_line_count(clean)
    argv = tool_argv(
        ctx,
        "import_otto_facts.py",
        str(clean),
        "--expected",
        str(n),
        "--source-label",
        ctx.batch_id,
    )
    if ctx.stage_write:
        argv.append("--apply")
    proc = ctx.runner.run(argv)
    tail = record_tool(ctx, proc)
    if proc.returncode != 0:
        return Gate(EXIT_GATE, f"import_otto_facts failed (exit {proc.returncode})", stdout_tail=tail)
    return Continue(notes=f"{'staged' if ctx.stage_write else 'would-stage'} {n}", stdout_tail=tail)


def _lint_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    other_purpose: List[str] = []
    eea_unscoped: List[str] = []
    nationality_disagree: List[str] = []
    by_topic: Dict[str, set] = {}
    for rec in rows:
        topic = str(rec.get("entity_topic_key") or rec.get("topic_key") or "")
        applies = rec.get("applies_to") or {}
        if not isinstance(applies, dict):
            applies = {}
        status = applies.get("status")
        if status is None or str(status).strip() == "" or str(status).lower() not in RECOGNISED_STATUS:
            other_purpose.append(rec.get("fact_key") or topic)
        nat = applies.get("nationality")
        if isinstance(nat, list):
            nat_key = tuple(nat)
        else:
            nat_key = (nat,)
        by_topic.setdefault(topic, set()).add(nat_key)
        blob = " ".join(
            str(rec.get(k) or "")
            for k in ("entity_topic_key", "entity_title", "fact_key", "fact_text", "fact_type")
        ).lower()
        if any(h in blob for h in _PERMISSION_HINTS):
            nats = nat if isinstance(nat, list) else [nat]
            if nats != ["EU_EEA"] and nat != "EU_EEA":
                eea_unscoped.append(rec.get("fact_key") or topic)
    for topic, nats in by_topic.items():
        if None in nats or ("",) in nats or (None,) in nats:
            nationality_disagree.append(topic)
        elif len(nats) > 1:
            nationality_disagree.append(topic)
    return {
        "purpose_other": other_purpose,
        "eea_unscoped": eea_unscoped,
        "nationality_disagree": nationality_disagree,
    }


def stage_5_prepromote(ctx: Ctx) -> StageOutcome:
    clean = ctx.harness_dir / "clean.ndjson"
    rows = iter_ndjson(clean)
    findings = _lint_rows(rows)
    findings["this_batch_ready"] = []
    findings["other_batch_ready"] = []
    findings["check_nationality_scope_exit"] = None
    tail = ""
    if ctx.stage_write:
        proc = ctx.runner.run(tool_argv(ctx, "check_nationality_scope.py", "--db"))
        tail = record_tool(ctx, proc)
        findings["check_nationality_scope_exit"] = proc.returncode
        write_json_atomic(ctx.harness_dir / "prepromote.json", findings)
        if proc.returncode == 1:
            return Gate(
                EXIT_SCOPE,
                "nationality scope violations",
                stdout_tail=tail,
                artifact="_harness/prepromote.json",
            )
        if proc.returncode == 2:
            return Gate(EXIT_GATE, "check_nationality_scope could not run", stdout_tail=tail)
    else:
        write_json_atomic(ctx.harness_dir / "prepromote.json", findings)
    return Continue(artifact="_harness/prepromote.json", stdout_tail=tail)


def _destinations(rows: List[Dict[str, Any]]) -> List[str]:
    return sorted({str(r.get("destination_country") or "").upper() for r in rows if r.get("destination_country")})


def stage_6_promote_dry(ctx: Ctx) -> StageOutcome:
    rows = iter_ndjson(ctx.harness_dir / "clean.ndjson")
    destinations = _destinations(rows)
    if not destinations:
        destinations = ["XX"]
    preview: Dict[str, Any] = {}
    baseline: Dict[str, Any] = {}
    saw_rollback = False
    try:
        session_cm = ctx.session_factory()
    except UsageError as exc:
        return Gate(exc.code, str(exc))

    def _run_one(session: Any, iso: str) -> Optional[StageOutcome]:
        nonlocal saw_rollback
        if hasattr(session, "begin"):
            session.begin()
        base = fingerprint(session, iso)
        baseline[iso] = {
            "approved": base[0],
            "human_verified": base[1],
            "fp_protected": base[2],
        }
        session.execute(
            text(READY_FLIP_SQL),
            {"b": ctx.batch_id, "iso": iso},
        )
        this_n = sum(1 for r in rows if str(r.get("destination_country") or "").upper() == iso)
        try:
            counted = execute_count(
                session,
                READY_COUNT_SQL,
                {"b": ctx.batch_id, "iso": iso},
            )
            if counted:
                this_n = counted
        except Exception:
            pass
        result = ctx.promote_fn(session, country=iso, dry_run=True)
        after = fingerprint(session, iso)
        if after != base:
            if hasattr(session, "rollback"):
                session.rollback()
                saw_rollback = True
            return Gate(
                EXIT_SCOPE,
                f"fingerprint changed for {iso}: {base!r} -> {after!r}",
            )
        promoted = int(getattr(result, "promoted", 0) or 0)
        titles = [draft_title(d) for d in (getattr(result, "drafts", None) or [])]
        this_titles = titles[:this_n] if titles else [r.get("entity_title") or r.get("fact_key") for r in rows if str(r.get("destination_country") or "").upper() == iso]
        other_n = max(0, promoted - this_n)
        other_titles = titles[this_n:] if titles else []
        preview[iso] = {
            "would_promote_this_batch": this_n,
            "titles": this_titles,
            "already_ready_other_batches": other_n,
            "other_titles": other_titles,
            "skipped_verified": list(getattr(result, "skipped_verified", []) or []),
            "unmapped": list(getattr(result, "unmapped", []) or []),
        }
        if hasattr(session, "rollback"):
            session.rollback()
            saw_rollback = True
        return None

    # session_factory may return a live session or a context manager.
    gate: Optional[StageOutcome] = None
    if hasattr(session_cm, "__enter__"):
        with session_cm as session:
            for iso in destinations:
                gate = _run_one(session, iso)
                if gate is not None:
                    break
            if hasattr(session, "rollback") and not saw_rollback:
                session.rollback()
    else:
        session = session_cm
        try:
            for iso in destinations:
                gate = _run_one(session, iso)
                if gate is not None:
                    break
        finally:
            if hasattr(session, "rollback") and not saw_rollback:
                session.rollback()

    if gate is not None:
        write_json_atomic(ctx.harness_dir / "fingerprint.baseline.json", baseline)
        write_json_atomic(ctx.harness_dir / "promote_preview.json", preview)
        return gate

    write_json_atomic(ctx.harness_dir / "promote_preview.json", preview)
    write_json_atomic(ctx.harness_dir / "fingerprint.baseline.json", baseline)
    _write_report(ctx, preview, baseline)
    return Continue(artifact="_harness/promote_preview.json")


def _write_report(ctx: Ctx, preview: Dict[str, Any], baseline: Dict[str, Any]) -> None:
    rec = ctx.harness_dir / "reconcile.json"
    rec_ok = rec.is_file()
    n = ndjson_line_count(ctx.harness_dir / "clean.ndjson")
    lines = [
        f"# Corridor harness report — {ctx.batch_id}",
        "",
        f"batch_id: {ctx.batch_id}",
        f"countries: {', '.join(preview.keys()) or '(none)'}",
        f"reconcile: {'PASS' if rec_ok else 'unknown'}",
        f"{'staged' if ctx.stage_write else 'would-stage'}: {n}",
        "",
        "## Per-country would-promote",
        json.dumps(preview, indent=2, default=str),
        "",
        "## Append-only baseline",
        json.dumps(baseline, indent=2, default=str),
        "",
        "## Manual next commands",
        "```",
        f"-- flip ready scoped to batch {ctx.batch_id} (human gate, not this tool)",
        f"-- then real scoped promote for the destination countries above",
        "-- review at /admin/countries",
        "```",
        "",
    ]
    write_atomic(ctx.harness_dir / "report.md", "\n".join(lines) + "\n")


STAGES: Dict[int, Callable[[Ctx], StageOutcome]] = {
    0: stage_0_ingest,
    1: stage_1_reconcile,
    2: stage_2_convert,
    3: stage_3_referee,
    4: stage_4_stage,
    5: stage_5_prepromote,
    6: stage_6_promote_dry,
}


def apply_outcome(ckpt: Dict[str, Any], n: int, name: str, outcome: StageOutcome) -> int:
    ts = now_iso()
    if isinstance(outcome, Continue):
        patch_stage(
            ckpt,
            n,
            name=name,
            status="skipped" if outcome.skipped else "ok",
            exit=outcome.exit,
            at=ts,
            stdout_tail=outcome.stdout_tail,
            notes=outcome.notes,
            **({"artifact": outcome.artifact} if outcome.artifact else {}),
        )
        return EXIT_OK
    if isinstance(outcome, Pause):
        patch_stage(
            ckpt,
            n,
            name=name,
            status="paused",
            exit=outcome.code,
            at=ts,
            stdout_tail=outcome.stdout_tail,
            artifact=outcome.worklist_path,
            notes=outcome.msg,
        )
        ckpt["harness_exit"] = outcome.code
        return outcome.code
    patch_stage(
        ckpt,
        n,
        name=name,
        status="gated",
        exit=outcome.exit,
        at=ts,
        stdout_tail=outcome.stdout_tail,
        notes=outcome.msg,
        **({"artifact": outcome.artifact} if outcome.artifact else {}),
    )
    ckpt["harness_exit"] = outcome.exit
    return outcome.exit


def resolve_batch_dir(batch_id: str, out: Optional[Path]) -> Path:
    if out is not None:
        # tests pass --out as harness dir; batch dir is the parent unless it *is* the batch
        return IMPORTS_ROOT / batch_id
    return IMPORTS_ROOT / batch_id


def resolve_harness_dir(batch_dir: Path, out: Optional[Path]) -> Path:
    return out if out is not None else batch_dir / "_harness"


def build_ctx(
    *,
    batch_id: str,
    batch_dir: Path,
    harness_dir: Path,
    entry: Dict[str, str],
    stage_write: bool,
    no_fetch: bool,
    python: str,
    runner: Optional[ToolRunner],
    transport: Optional[Transport],
    session_factory: Optional[Callable[[], Any]],
    promote_fn: Optional[Callable[..., Any]],
    bus_resolve: Optional[Callable[[], str]],
    ckpt: Dict[str, Any],
) -> Ctx:
    return Ctx(
        batch_id=batch_id,
        batch_dir=batch_dir,
        harness_dir=harness_dir,
        entry=entry,
        stage_write=stage_write,
        no_fetch=no_fetch,
        python=python,
        runner=runner or SubprocessToolRunner(),
        transport=transport or UrlLibTransport(),
        session_factory=session_factory or default_session_factory,
        promote_fn=promote_fn or default_promote_fn,
        bus_resolve=bus_resolve,
        ckpt=ckpt,
    )


def drive(ctx: Ctx, *, start_at: int = 0) -> int:
    ctx.harness_dir.mkdir(parents=True, exist_ok=True)
    for n, name in STAGE_DEFS:
        if n < start_at:
            continue
        outcome = STAGES[n](ctx)
        code = apply_outcome(ctx.ckpt, n, name, outcome)
        save_checkpoint(ctx.run_path, ctx.ckpt)
        if code != EXIT_OK:
            return code
    ctx.ckpt["harness_exit"] = EXIT_OK
    save_checkpoint(ctx.run_path, ctx.ckpt)
    return EXIT_OK


def classify_target(target: str) -> Dict[str, str]:
    if target.startswith(("http://", "https://", "file:")):
        return {"kind": "url", "value": target}
    return {"kind": "local", "value": target}


def local_batch_dir(target: str) -> Path:
    given = Path(target)
    if given.is_dir():
        return given.resolve()
    cand = IMPORTS_ROOT / target
    if cand.is_dir():
        return cand.resolve()
    raise UsageError(f"not a local batch dir: {target}")


def run_harness(
    target: str,
    *,
    stage: bool = False,
    no_fetch: bool = False,
    out: Optional[Path] = None,
    from_bus: bool = False,
    python: Optional[str] = None,
    runner: Optional[ToolRunner] = None,
    transport: Optional[Transport] = None,
    session_factory: Optional[Callable[[], Any]] = None,
    promote_fn: Optional[Callable[..., Any]] = None,
    bus_resolve: Optional[Callable[[], str]] = None,
) -> int:
    if from_bus:
        entry = {"kind": "bus", "value": target}
        batch_dir = IMPORTS_ROOT / (Path(target).name if target else "bus-batch")
        if out is not None:
            batch_dir = out.parent
        batch_id = batch_dir.name
    else:
        entry = classify_target(target)
        if entry["kind"] == "local":
            batch_dir = local_batch_dir(target)
            man = batch_dir / "manifest.json"
            batch_id = batch_dir.name
            if man.is_file():
                try:
                    data = load_json(man)
                    batch_id = str(data.get("batch_id") or batch_dir.name)
                except json.JSONDecodeError as exc:
                    raise UsageError(f"invalid manifest.json: {exc}") from exc
        else:
            batch_id = Path(urllib.parse.urlparse(target).path).parent.name or "url-batch"
            batch_dir = (out.parent if out is not None else IMPORTS_ROOT / batch_id)
    harness_dir = resolve_harness_dir(batch_dir, out)
    existing = load_checkpoint(harness_dir / "run.json")
    if existing and checkpoint_complete(existing):
        print(json.dumps(existing, indent=2))
        return EXIT_OK
    ckpt = new_checkpoint(batch_id, entry, stage_write_enabled=stage, no_fetch=no_fetch)
    ctx = build_ctx(
        batch_id=batch_id,
        batch_dir=batch_dir,
        harness_dir=harness_dir,
        entry=entry,
        stage_write=stage,
        no_fetch=no_fetch,
        python=python or sys.executable,
        runner=runner,
        transport=transport,
        session_factory=session_factory,
        promote_fn=promote_fn,
        bus_resolve=bus_resolve,
        ckpt=ckpt,
    )
    return drive(ctx, start_at=0)


def resume_harness(
    batch_id: str,
    *,
    stage: bool = False,
    no_fetch: bool = False,
    out: Optional[Path] = None,
    python: Optional[str] = None,
    runner: Optional[ToolRunner] = None,
    transport: Optional[Transport] = None,
    session_factory: Optional[Callable[[], Any]] = None,
    promote_fn: Optional[Callable[..., Any]] = None,
) -> int:
    batch_dir = out.parent if out is not None else (IMPORTS_ROOT / batch_id)
    if out is None and not batch_dir.is_dir():
        # allow tests to pass batch_id with --out pointing at harness dir
        raise UsageError(f"no batch dir for {batch_id}")
    harness_dir = resolve_harness_dir(batch_dir, out)
    ckpt = load_checkpoint(harness_dir / "run.json")
    if ckpt is None:
        raise UsageError(f"no checkpoint at {harness_dir / 'run.json'}")
    start = first_incomplete(ckpt)
    if start is None:
        print(json.dumps(ckpt, indent=2))
        return int(ckpt.get("harness_exit") or EXIT_OK)
    ckpt["stage_flag"]["stage_write_enabled"] = stage
    ckpt["stage_flag"]["no_fetch"] = no_fetch
    ctx = build_ctx(
        batch_id=ckpt.get("batch_id") or batch_id,
        batch_dir=batch_dir if batch_dir.is_dir() else (IMPORTS_ROOT / batch_id),
        harness_dir=harness_dir,
        entry=ckpt.get("entry") or {"kind": "local", "value": str(batch_dir)},
        stage_write=stage,
        no_fetch=no_fetch,
        python=python or sys.executable,
        runner=runner,
        transport=transport,
        session_factory=session_factory,
        promote_fn=promote_fn,
        bus_resolve=None,
        ckpt=ckpt,
    )
    if not ctx.batch_dir.is_dir() and out is not None:
        ctx.batch_dir = out.parent
    return drive(ctx, start_at=start)


def status_harness(batch_id: str, *, out: Optional[Path] = None) -> int:
    batch_dir = out.parent if out is not None else (IMPORTS_ROOT / batch_id)
    harness_dir = resolve_harness_dir(batch_dir, out)
    ckpt = load_checkpoint(harness_dir / "run.json")
    if ckpt is None:
        raise UsageError(f"no checkpoint for {batch_id}")
    print(json.dumps(ckpt, indent=2))
    return int(ckpt.get("harness_exit") or EXIT_OK)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run the harness from ingest")
    run_p.add_argument("target", help="local docs/imports/<batch>/ dir, or https/file manifest URL")
    run_p.add_argument("--stage", action="store_true", help="write otto_staging (status='new')")
    run_p.add_argument("--no-fetch", action="store_true", help="skip verify_ledger liveness")
    run_p.add_argument("--out", type=Path, help="override _harness/ directory")
    run_p.add_argument("--from-bus", action="store_true", help="resolve target via injected bus transport")
    run_p.add_argument("--python", dest="python_path", help="interpreter for subprocess tools")

    res_p = sub.add_parser("resume", help="re-enter at the first non-ok stage")
    res_p.add_argument("batch_id")
    res_p.add_argument("--stage", action="store_true")
    res_p.add_argument("--no-fetch", action="store_true")
    res_p.add_argument("--out", type=Path)
    res_p.add_argument("--python", dest="python_path")

    st_p = sub.add_parser("status", help="print the checkpoint")
    st_p.add_argument("batch_id")
    st_p.add_argument("--out", type=Path)
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "run":
            return run_harness(
                args.target,
                stage=args.stage,
                no_fetch=args.no_fetch,
                out=args.out,
                from_bus=args.from_bus,
                python=args.python_path,
            )
        if args.cmd == "resume":
            return resume_harness(
                args.batch_id,
                stage=args.stage,
                no_fetch=args.no_fetch,
                out=args.out,
                python=args.python_path,
            )
        return status_harness(args.batch_id, out=args.out)
    except UsageError as exc:
        print(f"usage: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())

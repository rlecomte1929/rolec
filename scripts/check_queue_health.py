#!/usr/bin/env python3
"""
check_queue_health.py — read-only health report over the AI Work Queue.

WHY. The queue's dominant failure mode is not bad execution, it is a card that describes a
world which no longer exists. Measured 2026-08-23: of 11 cards in one review session, **5 had
premises that were wrong or half-wrong**. Two of them (AIQ-1981, AIQ-2117) described work that
had already shipped — one under a commit with no AIQ tag, so `git log --grep` could never have
found it.

THE CHEAP DETECTOR. A card's `Test Command` that **PASSES on clean main means the card's work
already exists** — true of a bug fix and a feature alike. That single rule would have caught
both, mechanically, before an agent spent a pass on either.

WHAT THIS IS NOT. It never writes to Notion. Auto-closing a card because a command passed would
destroy real work — see `Verdict.NON_DISCRIMINATING`, which exists precisely because
`npx tsc --noEmit` passes for every card in the queue and would otherwise flag a third of them
as "already shipped" on day one.

CHECKS
  stale-premise         Test Command that passes on clean main (opt-in `--execute`)
  vetted-no-verification  Definition of Ready = Vetted with neither evidence nor a test
  unvetted-noise        cards with no tier, no evidence and no test at all
  status-divergence     Execution Notes contradict Status (delegates to the sibling guard)
  trailer-coverage      how often the mandated PREMISE:/DUPLICATE:/OUTCOME: line is written

EXIT CODES
  0  measured, nothing that `--fail-on` names was violated
  1  measured, a `--fail-on` check fired
  2  usage error
  3  DID NOT MEASURE — no token, no access, unreachable, or a degenerate scan

Exit 3 is the point. `check_queue_status_hygiene.py` and `check_deliverable_integrity.py` spent
weeks reporting PASS while a 404 stopped them reading anything, because both collapsed "clean"
and "could not look" into 0.

Stdlib only. Mirrors the self-contained audit-script pattern of `check_route_auth.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_DEFAULT_DATABASE_ID = "3bc887c6-4d48-8089-8188-fcf2dc3edc1b"
_NOTION_VERSION = "2022-06-28"

#: Definition of Ready, verbatim. The dash is U+2014 EM DASH and it is written as an escape on
#: purpose: a copy-paste through a dash-normalising editor turns this into a string that matches
#: ZERO rows, and the check then reports "0 violations" — a vacuous pass that looks like health.
VETTED = "Vetted — ready"

#: Statuses a card can sit in while still being work someone might pick up.
ACTIONABLE = ("Ready for AI", "Otto ready", "To Do", "Blocked", "AI in Progress",
              "Needs Human Clarification")
CLOSED = ("Done", "Rejected", "Archived")

#: Non-degeneracy floor. The queue held ~2,140 rows on 2026-08-23.
MIN_EXPECTED_ROWS = 500

EXIT_OK, EXIT_VIOLATION, EXIT_USAGE, EXIT_NOT_MEASURED = 0, 1, 2, 3

CHECK_NAMES = ("stale-premise", "vetted-no-verification", "unvetted-noise",
               "status-divergence", "trailer-coverage")


# --------------------------------------------------------------------------- #
# Row model                                                                    #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Row:
    aiq: str
    url: str
    title: str
    status: str
    dor: str
    task_type: str
    product_area: str
    agent: str
    tier: str
    test_command: str
    failure_evidence: str
    notes: str
    dependencies: str
    last_edited: str


def _text(prop: object) -> str:
    """Flatten a Notion property to plain text (title / rich_text / select)."""
    if not isinstance(prop, dict):
        return ""
    for key in ("title", "rich_text"):
        if key in prop:
            return "".join(seg.get("plain_text", "") for seg in prop.get(key) or [])
    sel = prop.get("select")
    if isinstance(sel, dict):
        return sel.get("name", "") or ""
    return ""


def _unique_id(prop: object) -> str:
    """Render a Notion unique_id property as 'PREFIX-NUMBER' (e.g. AIQ-853)."""
    if isinstance(prop, dict) and isinstance(prop.get("unique_id"), dict):
        uid = prop["unique_id"]
        num = uid.get("number")
        if num is None:
            return ""
        prefix = uid.get("prefix") or ""
        return f"{prefix}-{num}" if prefix else str(num)
    return ""


def extract_row(page: Dict[str, Any]) -> Row:
    """Flatten one Notion page. PURE — this is where property-name drift is pinned.

    The title property of this database is `fable`. Reading "Task Title" (which does not
    exist) yields "" for every row, silently, and every downstream count becomes 0 — which is
    exactly how `check_queue_status_hygiene` came to report PASS on a queue it had not read.
    """
    p = page.get("properties", {})
    return Row(
        aiq=_unique_id(p.get("ID")) or _text(p.get("ID")),
        url=page.get("url", ""),
        title=_text(p.get("fable")),
        status=_text(p.get("Status")),
        dor=_text(p.get("Definition of Ready")),
        task_type=_text(p.get("Task Type")),
        product_area=_text(p.get("Product Area")),
        agent=_text(p.get("Assigned AI Agent")),
        tier=_text(p.get("Autonomy Tier")),
        test_command=_text(p.get("Test Command")),
        failure_evidence=_text(p.get("Failure Evidence")),
        notes=_text(p.get("Execution Notes")),
        dependencies=_text(p.get("Dependencies")),
        last_edited=page.get("last_edited_time", ""),
    )


# --------------------------------------------------------------------------- #
# Fetch                                                                        #
# --------------------------------------------------------------------------- #

class QueueUnavailable(RuntimeError):
    """The queue could not be measured. NEVER report this as a pass."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def resolve_token() -> Tuple[Optional[str], str]:
    """NOTION_TOKEN first (CI maps secrets.NOTION_QUEUE_TOKEN onto it), then the local name."""
    for name in ("NOTION_TOKEN", "NOTION_QUEUE_TOKEN"):
        val = os.environ.get(name)
        if val:
            return val, name
    return None, ""


def notion_query(token: str, database_id: str, filter_: Optional[dict] = None,
                 *, page_cap: int = 100) -> List[Dict[str, Any]]:
    """Paginated query. A page that fails after retries raises rather than returning short.

    A PARTIAL scan reported as a complete one is the same lie as a skipped scan reported as a
    pass: every count comes out low and reads as health.
    """
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": _NOTION_VERSION,
               "Content-Type": "application/json"}
    out: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    for _ in range(page_cap):
        body: Dict[str, Any] = {"page_size": 100}
        if filter_:
            body["filter"] = filter_
        if cursor:
            body["start_cursor"] = cursor
        payload = _post_with_retry(url, body, headers)
        out.extend(payload.get("results", []))
        if not payload.get("has_more"):
            return out
        cursor = payload.get("next_cursor")
    raise QueueUnavailable("unreachable",
                           f"pagination exceeded {page_cap} pages — probable cursor bug")


def _post_with_retry(url: str, body: dict, headers: dict, *, attempts: int = 3) -> dict:
    last: Optional[Exception] = None
    for i in range(attempts):
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404):
                raise QueueUnavailable("no-access", f"HTTP {exc.code} querying the queue.")
            if exc.code == 429 or exc.code >= 500:
                time.sleep(float(exc.headers.get("Retry-After", 2 ** i)))
                last = exc
                continue
            raise QueueUnavailable("unreachable", f"HTTP {exc.code}.")
        except urllib.error.URLError as exc:
            time.sleep(2 ** i)
            last = exc
    raise QueueUnavailable("unreachable", f"{attempts} attempts failed: {last}")


def assert_non_degenerate(rows: Sequence[Row]) -> None:
    """Refuse to call a degenerate scan clean.

    A renamed property does not raise. It yields "" for every row, every count becomes 0, and
    that is indistinguishable from a healthy queue. These assertions are what make that loud.
    """
    if len(rows) < MIN_EXPECTED_ROWS:
        raise QueueUnavailable("schema-drift",
                               f"only {len(rows)} row(s); expected >= {MIN_EXPECTED_ROWS}.")
    if not any(r.title.strip() for r in rows):
        raise QueueUnavailable("schema-drift",
                               f"{len(rows)} rows but NOT ONE had a title — the title property "
                               "has probably been renamed (it is `fable`).")
    if not any(r.status.strip() for r in rows):
        raise QueueUnavailable("schema-drift",
                               f"{len(rows)} rows but NOT ONE had a Status.")
    if not any(r.dor == VETTED for r in rows):
        raise QueueUnavailable("schema-drift",
                               f"{len(rows)} rows but NOT ONE reads {VETTED!r} — the em-dash "
                               "in that literal has probably been normalised.")


# --------------------------------------------------------------------------- #
# Check 1 — the safety model                                                   #
# --------------------------------------------------------------------------- #

class Verdict(str, Enum):
    STALE = "stale"                            # ran, exit 0 -> the work likely already exists
    LIVE = "live"                              # ran, non-zero -> the premise still holds
    INCONCLUSIVE = "inconclusive"              # ran, but the sandbox failed, not the assertion
    TIMEOUT = "timeout"
    NON_DISCRIMINATING = "non_discriminating"  # would pass on main regardless of this card
    REFUSED = "refused"                        # the safety model rejected it
    UNPARSEABLE = "unparseable"                # prose, placeholder, or not a command


@dataclass(frozen=True)
class Classification:
    verdict: Optional[Verdict]                 # None => runnable; execution decides
    segments: Tuple[Tuple[str, ...], ...] = ()
    kind: str = "process"                      # "process" | "http_get"
    url: Optional[str] = None
    reason: str = ""
    normalizations: Tuple[str, ...] = ()


#: Tokens that mean the command intends to WRITE. A premise test never needs to.
_DENY_FLAGS = ("--apply", "--promote", "--write", "--commit", "--push", "--delete",
               "--force", "--prod", "--production", "--seed", "--yes")

#: Binaries that can mutate a repo, a database or a remote. `npm`/`yarn`/`pnpm` are denied
#: wholesale because `npm run <x>` executes an arbitrary package.json script this classifier
#: cannot see.
_DENY_BINS = {"rm", "mv", "cp", "dd", "chmod", "chown", "sudo", "kill", "pkill", "docker",
              "psql", "supabase", "alembic", "npm", "pnpm", "yarn", "pip", "pip3", "make",
              "bash", "sh", "zsh", "eval", "exec", "ssh", "scp", "curl-config"}

#: An env-assignment prefix naming a credential. A command that wants a secret must not get one.
_CRED_ENV_RE = re.compile(
    r"^[A-Z_]*(DATABASE_URL|SERVICE_ROLE|_KEY|_SECRET|_TOKEN|_PASSWORD)[A-Z_]*=")

#: Shell metacharacters that chain or redirect. `&&` is handled separately.
_CHAIN_TOKENS = {";", "|", "||", ">", ">>", "<", "&"}

_PLACEHOLDER_RE = re.compile(r"<[a-zA-Z][\w-]*>|\{\{.*?\}\}|\$\{[A-Z_]+\}|\bYOUR_|\bPATH_TO\b")

_GIT_READ_SUBCOMMANDS = {"ls-files", "grep", "log", "show", "diff", "rev-parse", "cat-file",
                         "status"}

_CURL_OK_FLAGS = {"-s", "-S", "-f", "-i", "-L", "--silent", "--show-error", "--fail",
                  "--location", "--max-time", "-w", "-o"}

_CURL_OK_HOSTS = {"api.relopass.com", "relopass.com", "localhost", "127.0.0.1"}


def classify_command(raw: str) -> Classification:
    """Decide whether a Test Command may be executed, and how. PURE — no I/O, no subprocess.

    This function IS the safety model; everything downstream just obeys it. It is the thing the
    corpus test pins, and because it is pure that test can never execute anything.
    """
    text = (raw or "").strip()
    if not text:
        return Classification(Verdict.UNPARSEABLE, reason="empty")

    if _PLACEHOLDER_RE.search(text):
        m = _PLACEHOLDER_RE.search(text)
        return Classification(Verdict.UNPARSEABLE,
                              reason=f"placeholder {m.group(0)!r} — not a runnable command")
    if text.lower().startswith("n/a") or text.strip() == "...":
        return Classification(Verdict.UNPARSEABLE, reason="explicitly not a command")
    if "\n" in text:
        return Classification(Verdict.UNPARSEABLE, reason="multi-line")
    # Substitution is evaluated before anything else could inspect it.
    for bad in ("`", "$(", "${"):
        if bad in text:
            return Classification(Verdict.REFUSED, reason=f"command substitution {bad!r}")

    raw_segments = [s.strip() for s in text.split("&&")]
    if any(not s for s in raw_segments):
        return Classification(Verdict.UNPARSEABLE, reason="empty && segment")

    segments: List[Tuple[str, ...]] = []
    for seg in raw_segments:
        try:
            argv = tuple(shlex.split(seg, posix=True))
        except ValueError as exc:
            return Classification(Verdict.UNPARSEABLE, reason=f"unbalanced quoting: {exc}")
        if not argv:
            return Classification(Verdict.UNPARSEABLE, reason="empty segment")
        if any(tok in _CHAIN_TOKENS for tok in argv):
            bad = next(t for t in argv if t in _CHAIN_TOKENS)
            return Classification(Verdict.REFUSED,
                                  reason=f"chain/redirect operator {bad!r} — running only part "
                                         "of a chained command is a different command")
        deny = _denylist_reason(argv)
        if deny:
            return Classification(Verdict.REFUSED, reason=deny)
        head_bad = _head_allowlist_reason(argv)
        if head_bad:
            return Classification(Verdict.REFUSED, reason=head_bad)
        segments.append(argv)

    # curl is SAFE only because it is interpreted rather than executed, and that interpretation
    # only happens for a lone segment. In a chain it would fall through to subprocess with an
    # arbitrary host and no flag checking — `pytest && curl https://evil.example.com/x` was
    # accepted by an earlier version of this function, which the corpus test caught.
    if len(segments) > 1 and any(Path(a[0]).name == "curl" for a in segments):
        return Classification(Verdict.REFUSED,
                              reason="curl in a chained command — it is only ever interpreted "
                                     "as a host-allowlisted GET, never executed")

    # curl is interpreted, never executed.
    if len(segments) == 1 and Path(segments[0][0]).name == "curl":
        url, refusal = _curl_to_get(segments[0])
        if refusal:
            return Classification(Verdict.REFUSED, reason=refusal)
        return Classification(None, segments=tuple(segments), kind="http_get", url=url,
                              normalizations=("curl interpreted as a urllib GET; a non-2xx "
                                              "status counts as failure (bare curl exits 0 on "
                                              "a 404, which would read as 'already shipped')",))

    if not any(_is_discriminating(a) for a in segments):
        return Classification(Verdict.NON_DISCRIMINATING,
                              segments=tuple(segments),
                              reason="names no specific target — passes on main for every card, "
                                     "so it cannot tell this card's work from any other's")
    return Classification(None, segments=tuple(segments))


def _denylist_reason(argv: Tuple[str, ...]) -> str:
    for tok in argv:
        if tok in _DENY_FLAGS:
            return f"write-intent flag {tok!r}"
        if _CRED_ENV_RE.match(tok):
            return f"credential env prefix {tok.split('=')[0]!r} — the sandbox withholds secrets"
        if Path(tok).name in _DENY_BINS:
            return f"write-capable binary {Path(tok).name!r}"
    return ""


def _head_allowlist_reason(argv: Tuple[str, ...]) -> str:
    """The head allowlist. This doubles as the prose classifier.

    "Inspect the 'Detect changes' job log" has argv[0] == "Inspect", which is not a command, and
    is refused with a legible reason. A second NLP-ish prose detector would be a tunable that
    drifts toward "runnable"; the allowlist already answers the question.
    """
    head = Path(argv[0]).name
    if head == "pytest":
        return ""
    if head in ("python", "python3"):
        return "" if argv[1:3] == ("-m", "pytest") else \
            "python invoked with something other than -m pytest"
    if head == "npx":
        return "" if len(argv) > 1 and argv[1] in ("vitest", "tsc") else \
            "npx invoked with something other than vitest/tsc"
    if head in ("vitest", "tsc", "test", "grep", "rg", "jq", "cat", "head", "wc", "diff", "ls"):
        return ""
    if head == "git":
        return "" if len(argv) > 1 and argv[1] in _GIT_READ_SUBCOMMANDS else \
            f"git subcommand {argv[1] if len(argv) > 1 else '(none)'!r} is not read-only"
    if head == "curl":
        return ""
    return f"head-not-allowlisted: {head!r}"


def _is_discriminating(argv: Tuple[str, ...]) -> bool:
    """Does this command name a target specific enough to be about ONE card?

    `npx tsc --noEmit` passes on main for every card in the queue. Counting it as STALE would
    flag roughly a third of the queue on day one, the report would obviously be wrong, and it
    would be ignored inside a week.
    """
    head = Path(argv[0]).name
    if head in ("test", "grep", "rg", "jq", "cat", "head", "wc", "diff", "ls", "git", "curl"):
        return True
    for tok in argv[1:]:
        if tok in ("-k", "--", "-m"):
            continue
        if tok.startswith("-"):
            continue
        if "::" in tok or "/" in tok or tok.endswith((".py", ".ts", ".tsx", ".js")):
            return True
    return "-k" in argv


def _curl_to_get(argv: Tuple[str, ...]) -> Tuple[Optional[str], str]:
    """Extract the single URL from a curl invocation, refusing anything that is not a plain GET.

    Flags are allowlisted rather than denylisted: that refuses `-X POST`, `-d`, `-F`, `-T`,
    `-k`, `--proxy` and every future flag nobody thought of.
    """
    url: Optional[str] = None
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok in ("-H", "--header"):
            val = argv[i + 1] if i + 1 < len(argv) else ""
            if re.search(r"authorization|bearer|apikey|token", val, re.I):
                return None, "curl carries an auth header — a clean-main premise test needs none"
            i += 2
            continue
        if tok.startswith("-"):
            base = tok.split("=")[0]
            if base not in _CURL_OK_FLAGS:
                return None, f"curl flag {base!r} is not on the GET allowlist"
            if base in ("--max-time", "-w", "-o"):
                i += 2
                continue
            i += 1
            continue
        if url is not None:
            return None, "curl names more than one URL"
        url = tok
        i += 1
    if not url:
        return None, "curl names no URL"
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host not in _CURL_OK_HOSTS:
        return None, f"host {host!r} is not allowlisted"
    return url, ""


def sandbox_env() -> Dict[str, str]:
    """An allowlist, not os.environ.

    The single highest-value control here, and it is one dict literal. A command that needs
    DATABASE_URL, SUPABASE_*, NOTION_*, ANTHROPIC_API_KEY or GITHUB_TOKEN fails in the sandbox
    rather than reaching production with them.
    """
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update({"CI": "1", "NODE_ENV": "test", "PYTHONDONTWRITEBYTECODE": "1",
                "RELOPASS_DISABLE_RATE_LIMITS": "1", "DATABASE_URL": "sqlite:///./_qh_probe.db"})
    return env


_INCONCLUSIVE_MARKERS = ("modulenotfounderror", "command not found", "no such file",
                         "connection refused", "importerror", "cannot find module",
                         "econnrefused")


def run_classified(c: Classification, *, cwd: Path, timeout: int) -> Tuple[Verdict, str]:
    """Execute a classified command. Never a shell; never the ambient environment."""
    if c.kind == "http_get":
        try:
            req = urllib.request.Request(c.url or "", headers={"Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=min(timeout, 20)) as resp:
                return (Verdict.STALE if 200 <= resp.status < 300 else Verdict.LIVE,
                        f"HTTP {resp.status}")
        except urllib.error.HTTPError as exc:
            return Verdict.LIVE, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 — any transport failure is inconclusive
            return Verdict.INCONCLUSIVE, f"{type(exc).__name__}: {exc}"

    out_parts: List[str] = []
    for argv in c.segments:
        try:
            proc = subprocess.run(list(argv), cwd=str(cwd), env=sandbox_env(),
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=timeout, start_new_session=True, shell=False)
        except subprocess.TimeoutExpired:
            return Verdict.TIMEOUT, f"exceeded {timeout}s"
        except FileNotFoundError as exc:
            return Verdict.INCONCLUSIVE, f"not found: {exc}"
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
        out_parts.append(tail)
        if proc.returncode != 0:
            blob = tail.lower()
            if proc.returncode == 127 or any(m in blob for m in _INCONCLUSIVE_MARKERS):
                # The sandbox failed, not the assertion. Calling this LIVE would silently
                # understate staleness — and silence is the thing being fixed.
                return Verdict.INCONCLUSIVE, tail[-400:]
            return Verdict.LIVE, tail[-400:]
    return Verdict.STALE, "\n".join(out_parts)[-400:]


# --------------------------------------------------------------------------- #
# Checks                                                                       #
# --------------------------------------------------------------------------- #

@dataclass
class CheckResult:
    name: str
    findings: List[dict] = field(default_factory=list)
    considered: int = 0
    checked: int = 0
    skipped: Dict[str, int] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def incomplete(self) -> bool:
        return self.checked < self.considered


def check_stale_premise(rows: Sequence[Row], *, execute: bool, cwd: Path,
                        timeout: int, budget: int) -> CheckResult:
    ready = [r for r in rows if r.status == "Ready for AI"]
    with_cmd = [r for r in ready if r.test_command.strip()]
    res = CheckResult("stale-premise", considered=len(with_cmd))
    res.stats = {"ready_cards": len(ready), "without_test_command": len(ready) - len(with_cmd)}

    started = time.monotonic()
    for row in with_cmd:
        c = classify_command(row.test_command)
        if c.verdict is not None:
            res.skipped[c.verdict.value] = res.skipped.get(c.verdict.value, 0) + 1
            if c.verdict in (Verdict.REFUSED, Verdict.NON_DISCRIMINATING):
                res.findings.append({"aiq": row.aiq, "url": row.url, "verdict": c.verdict.value,
                                     "reason": c.reason, "command": row.test_command[:160]})
            continue
        if not execute:
            res.skipped["not_executed"] = res.skipped.get("not_executed", 0) + 1
            continue
        if time.monotonic() - started > budget:
            res.skipped["budget_exhausted"] = res.skipped.get("budget_exhausted", 0) + 1
            continue
        verdict, detail = run_classified(c, cwd=cwd, timeout=timeout)
        res.checked += 1
        res.skipped[verdict.value] = res.skipped.get(verdict.value, 0) + 1
        if verdict is Verdict.STALE:
            res.findings.append({"aiq": row.aiq, "url": row.url, "verdict": "stale",
                                 "reason": "Test Command PASSES on clean main — the work may "
                                           "already exist",
                                 "command": row.test_command[:160], "detail": detail[:200]})
    return res


def check_vetted_no_verification(rows: Sequence[Row]) -> CheckResult:
    """Cards claiming the Definition-of-Ready gate with neither a repro nor a way to prove done.

    Narrower than "vetted and no Failure Evidence" on purpose: a Research card has no failure
    evidence by nature, so that raw count is partly noise. Requiring BOTH to be blank is the
    high-signal set.
    """
    pool = [r for r in rows if r.status in ACTIONABLE]
    res = CheckResult("vetted-no-verification", considered=len(pool), checked=len(pool))
    for r in pool:
        if r.dor == VETTED and not r.failure_evidence.strip() and not r.test_command.strip():
            res.findings.append({"aiq": r.aiq, "url": r.url, "status": r.status,
                                 "title": r.title[:70],
                                 "reason": "Definition of Ready = Vetted, but no Failure "
                                           "Evidence and no Test Command"})
    return res


def check_unvetted_noise(rows: Sequence[Row]) -> CheckResult:
    """Cards with nothing at all: no tier, no evidence, no test, no Definition of Ready."""
    pool = [r for r in rows if r.status in ACTIONABLE]
    res = CheckResult("unvetted-noise", considered=len(pool), checked=len(pool))
    for r in pool:
        if (not r.test_command.strip() and not r.failure_evidence.strip()
                and not r.dor.strip() and not r.tier.strip()):
            res.findings.append({"aiq": r.aiq, "url": r.url, "status": r.status,
                                 "title": r.title[:70],
                                 "reason": "no tier, no evidence, no test, no Definition of "
                                           "Ready — not executable from the card alone"})
    return res


def check_status_divergence(rows: Sequence[Row]) -> CheckResult:
    """Execution Notes contradict Status.

    Delegates the blocked-marker regex to `check_queue_status_hygiene` rather than restating it:
    two scripts asserting one invariant differently gives two answers.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import check_queue_status_hygiene as hygiene  # noqa: WPS433
        has_blocked = hygiene.has_blocked_marker
    except Exception:  # pragma: no cover - the sibling should always be importable
        has_blocked = lambda notes: bool(re.search(r"(?im)^\s*#*\s*-?\s*blocked\b", notes or ""))

    pool = [r for r in rows if r.status in ("Ready for AI", "Otto ready")]
    res = CheckResult("status-divergence", considered=len(pool), checked=len(pool))
    for r in pool:
        reasons = []
        if has_blocked(r.notes):
            reasons.append("Execution Notes say 'Blocked'")
        for pat, label in ((r"superseded by", "notes say 'superseded by'"),
                           (r"already (shipped|merged|fixed|landed|done)",
                            "notes say the work already shipped")):
            if re.search(pat, r.notes or "", re.I):
                reasons.append(label)
        if reasons:
            res.findings.append({"aiq": r.aiq, "url": r.url, "status": r.status,
                                 "title": r.title[:70], "reason": "; ".join(reasons)})
    return res


@dataclass(frozen=True)
class Trailer:
    premise: Optional[str] = None
    duplicate: Optional[bool] = None
    outcome: Optional[str] = None
    source: Optional[str] = None

    @property
    def complete(self) -> bool:
        return bool(self.premise and self.duplicate is not None and self.outcome)


def parse_trailer(notes: str) -> Optional[Trailer]:
    """Parse the mandated closing line. Each key independently, last occurrence wins.

    A single conjunctive regex undercounts: notes get appended to over a card's life, and a
    partially-compliant trailer still carries the datum that matters.
    """
    if not notes:
        return None
    def last(pattern: str) -> Optional[str]:
        found = re.findall(pattern, notes, re.I)
        return found[-1] if found else None

    premise = last(r"PREMISE:\s*(Confirmed|Refuted|Partial)")
    dup = last(r"DUPLICATE:\s*(yes|no)")
    outcome = last(r"OUTCOME:\s*(code|docs|no-op)")
    source = last(r"SOURCE:\s*([\w.-]+)")
    if not any((premise, dup, outcome, source)):
        return None
    return Trailer(premise=premise.capitalize() if premise else None,
                   duplicate=(dup.lower() == "yes") if dup else None,
                   outcome=outcome.lower() if outcome else None,
                   source=source)


def check_trailer_coverage(rows: Sequence[Row], *, since: Optional[str]) -> CheckResult:
    """How often the mandated trailer is actually written, windowed.

    Un-windowed this is permanently ~6% (the mandate postdates most of the queue), which shows
    no trend and gets ignored.
    """
    pool = [r for r in rows if r.status in CLOSED
            and (not since or (r.last_edited or "") >= since)]
    res = CheckResult("trailer-coverage", considered=len(pool), checked=len(pool))
    full = premise_only = none = 0
    premises: Dict[str, int] = {}
    dups = 0
    by_agent: Dict[str, Dict[str, int]] = {}
    for r in pool:
        t = parse_trailer(r.notes)
        if t is None:
            none += 1
            continue
        if t.complete:
            full += 1
        else:
            premise_only += 1
        if t.premise:
            premises[t.premise] = premises.get(t.premise, 0) + 1
            slot = by_agent.setdefault(r.agent or "(unset)", {})
            slot[t.premise] = slot.get(t.premise, 0) + 1
        if t.duplicate:
            dups += 1
    reporting = full + premise_only
    failed = premises.get("Refuted", 0) + premises.get("Partial", 0)
    res.stats = {
        "closed_in_window": len(pool), "full": full, "premise_only": premise_only,
        "no_trailer": none, "duplicates": dups, "premises": premises,
        "premise_failure_rate": round(100 * failed / reporting, 1) if reporting else None,
        "by_executor": by_agent,
    }
    return res


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #

def render_text(results: Sequence[CheckResult], meta: Dict[str, Any]) -> str:
    lines = [f"AI Work Queue health — {meta['when']}",
             f"token: {meta['token_var']}   rows: {meta['rows']}   "
             f"window: {meta.get('since') or 'all'}   tree: {meta['tree']}", ""]
    for res in results:
        lines.append(f"[{res.name}]  considered {res.considered}   checked {res.checked}")
        if res.skipped:
            lines.append("    " + " · ".join(f"{k} {v}" for k, v in sorted(res.skipped.items())))
        for k, v in res.stats.items():
            lines.append(f"    {k}: {v}")
        if res.incomplete:
            lines.append(f"    >> checked {res.checked} of {res.considered} — "
                         "the rest were not measured; this is NOT a clean bill of health.")
        for f in res.findings[:25]:
            lines.append(f"      {f.get('aiq','?'):<9} {f.get('reason','')}")
            if f.get("command"):
                lines.append(f"                `{f['command']}`")
        if len(res.findings) > 25:
            lines.append(f"      … and {len(res.findings) - 25} more")
        lines.append("")
    return "\n".join(lines)


def _tree_state(cwd: Path) -> Tuple[bool, str]:
    def git(*a: str) -> str:
        try:
            return subprocess.run(["git", *a], cwd=str(cwd), capture_output=True,
                                  text=True, timeout=15).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""
    dirty = bool(git("status", "--porcelain"))
    head, main = git("rev-parse", "HEAD"), git("rev-parse", "origin/main")
    clean = (not dirty) and bool(head) and head == main
    return clean, ("clean @ origin/main " + head[:8]) if clean else (
        "DIRTY" if dirty else f"HEAD {head[:8]} != origin/main {main[:8]}")


def _not_measured(kind: str, detail: str) -> int:
    print(f"[SKIP:{kind}] {detail}")
    print("NOT A PASS — nothing was measured.")
    if kind == "no-access":
        print("  Fix: share the AI Work Queue database with this integration "
              "(Notion -> database -> ... -> Connections).")
    elif kind == "no-token":
        print("  Fix: export NOTION_TOKEN or NOTION_QUEUE_TOKEN.")
    return EXIT_NOT_MEASURED


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Read-only health report over the AI Work Queue.")
    p.add_argument("--database-id", default=_DEFAULT_DATABASE_ID)
    p.add_argument("--check", action="append", choices=CHECK_NAMES,
                   help="Run only these checks (repeatable). Default: all.")
    p.add_argument("--fail-on", action="append", choices=CHECK_NAMES, default=[],
                   help="Exit 1 if this check has findings (repeatable).")
    p.add_argument("--execute", action="store_true",
                   help="Actually run classified Test Commands. Off by default.")
    p.add_argument("--allow-dirty", action="store_true",
                   help="Permit --execute on a dirty tree; every result is stamped.")
    p.add_argument("--since", default="2026-07-01",
                   help="ISO date for trailer coverage (default: the mandate date).")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--budget", type=int, default=900)
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    cwd = Path(args.root).resolve()
    token, token_var = resolve_token()
    if not token:
        return _not_measured("no-token", "neither NOTION_TOKEN nor NOTION_QUEUE_TOKEN is set.")

    clean, tree = _tree_state(cwd)
    if args.execute and not clean and not args.allow_dirty:
        return _not_measured(
            "dirty-tree",
            f"--execute needs a clean tree at origin/main ({tree}); the claim under test is "
            "'this passes on clean main', and a dirty tree measures your WIP instead. "
            "Pass --allow-dirty to override.")

    try:
        pages = notion_query(token, args.database_id)
        rows = [extract_row(pg) for pg in pages]
        assert_non_degenerate(rows)
    except QueueUnavailable as exc:
        return _not_measured(exc.kind, exc.detail)

    wanted = args.check or list(CHECK_NAMES)
    results: List[CheckResult] = []
    if "stale-premise" in wanted:
        results.append(check_stale_premise(rows, execute=args.execute, cwd=cwd,
                                           timeout=args.timeout, budget=args.budget))
    if "vetted-no-verification" in wanted:
        results.append(check_vetted_no_verification(rows))
    if "unvetted-noise" in wanted:
        results.append(check_unvetted_noise(rows))
    if "status-divergence" in wanted:
        results.append(check_status_divergence(rows))
    if "trailer-coverage" in wanted:
        results.append(check_trailer_coverage(rows, since=args.since))

    meta = {"when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "token_var": token_var, "rows": len(rows), "since": args.since,
            "tree": tree + ("  [dirty-tree]" if args.execute and not clean else "")}
    if args.json:
        print(json.dumps({"meta": meta, "checks": [
            {"name": r.name, "considered": r.considered, "checked": r.checked,
             "skipped": r.skipped, "stats": r.stats, "findings": r.findings}
            for r in results]}, indent=2, default=str))
    else:
        print(render_text(results, meta))

    for res in results:
        if res.name not in args.fail_on:
            continue
        # "Nothing was checked" is a failure of the check, not a clean result.
        if res.name == "stale-premise" and args.execute and res.checked == 0:
            print(f"[FAIL] {res.name}: 0 of {res.considered} commands were actually executed.")
            return EXIT_VIOLATION
        if res.findings:
            print(f"[FAIL] {res.name}: {len(res.findings)} finding(s).")
            return EXIT_VIOLATION
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

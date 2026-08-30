"""Corridor Verifier — V0/V1/V2 checks over a generator's ledger, before the importer sees it.

WHAT THIS IS FOR
----------------
`import_otto_facts.py` is strict in exactly the right way and fragile in exactly one: a single
malformed line makes `parsers.read_jsonl` raise, and the whole batch stops. That is deliberate
("importing its readable half would report a partial batch as a complete one"), but it means one
bad record from the generator costs the other 199.

This module is the preprocessor that makes that never happen. It reads the ledger, decides per
record whether the importer would choke on it, and splits the file into a clean half the importer
can swallow whole and a worklist naming what was wrong with the rest. **It writes nothing to the
database and stages nothing** — the importer keeps sole ownership of `otto_staging`.

THE TWO SEVERITIES, AND WHY THE SECOND ONE EXISTS
-------------------------------------------------
`REJECT` — the importer would either raise (bad JSON, a missing required field, a malformed
`applies_to`) or reject (an unofficial publisher, a duplicate `dedupe_key`) on this record. The
two are different failures — a raise stops the batch, a rejection drops one row — but both mean
the record must not reach the clean file.

`WARN` — the importer accepts it happily, stages it, and then `mappings.resolve()` returns
`Unmapped` at promote time, so it never becomes a requirement and nobody finds out. That silence
is the expensive failure: the B3 batch staged 20 facts with no `applies_to.nationality` at all,
and the ES→IE batch's 19 Irish candidates sat in categories nothing serves. A warned record still
goes to the clean file — refusing it would be this module inventing a policy the importer does not
have — but it is counted and named, so a batch that will promote nothing says so up front instead
of six weeks later.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
No fuzzy matching, and no second evidence matcher. Quote grounding (V3) is
`backend/app/services/fact_evidence.py`, which is exact-modulo-normalisation plus ordered
recomposition and carries a `TRANSLATED` verdict so a translated fact is not filed as a suspect
one. A similarity threshold layered on top of that would make an existing stricter check weaker.

No LLM. Nothing here reaches a model, which keeps the serving/LLM isolation guard satisfied by
construction rather than by allowlist.

A dead-looking source is a WARNING, never a rejection. On 2026-08-22 a transient outage made a
live HSE URL read as dead, and it was newer than the pages proposed to replace it. Retiring a fact
on one failed GET is how good data gets deleted.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import yaml

from backend.app.services.requirements_country_key import iso_to_catalog_name
from backend.imports.otto.mappings import (
    CANONICAL_PILLARS,
    NATIONALITY_CLASSES,
    PILLAR_ALIASES,
    PURPOSES,
)
from backend.imports.otto.parsers import (
    CONFIDENCE_SCORES,
    KNOWN_FACT_TYPES,
    REQUIRED_FIELDS,
    UNOFFICIAL,
    classify_source,
    unspecific_citation_reason,
)

REJECT = "reject"
WARN = "warn"

DEFAULT_CONFIG = Path(__file__).with_name("verifier_config.yaml")

#: `domain_area` the importer's promote path accepts. `mappings.resolve()` refuses anything else
#: outright (mappings.py:281), so a ledger that ships 'registration' or 'tax' stages fine and then
#: promotes nothing.
PROMOTABLE_DOMAIN_AREA = "immigration"


@dataclass
class Finding:
    """One thing wrong with one record."""

    severity: str      # REJECT | WARN
    check: str         # V0 | V1 | V2
    code: str          # short machine-readable slug
    detail: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{self.severity.upper()}] {self.check}/{self.code}: {self.detail}"


@dataclass
class Verdict:
    """The outcome for one ledger line."""

    lineno: int
    dedupe_key: Optional[str]
    record: Optional[Dict[str, Any]]      # normalised; None when the line would not parse
    findings: List[Finding] = field(default_factory=list)
    source_rank: Optional[int] = None
    source_class: Optional[str] = None

    @property
    def rejected(self) -> bool:
        return any(f.severity == REJECT for f in self.findings)

    @property
    def warned(self) -> bool:
        return any(f.severity == WARN for f in self.findings)

    @property
    def clean(self) -> bool:
        return not self.rejected and not self.warned


# --------------------------------------------------------------------------- V0


_QUOTE_GARBLE = re.compile(r'(?:%22|%27|["\'“”‘’])')


def normalise_url(raw: Any) -> str:
    """Repair the URL garble the generator actually emits, and only that.

    Three observed defects, in order: a percent-encoded or literal quote glued to either end
    (`https://x.gov/a%22`), the same `#fragment` repeated, and a bare host with no scheme. Each
    is a transport artefact rather than a different page, so repairing them is not the same as
    inventing a source — the identity of the document is unchanged. Anything beyond these is left
    alone for a human, because a URL we cannot confidently repair is a research problem.
    """
    url = str(raw or "").strip()
    if not url:
        return ""
    url = _QUOTE_GARBLE.sub("", url).strip()
    # A duplicated fragment: `...#sec2#sec2` -> `...#sec2`. Keep the first.
    if url.count("#") > 1:
        head, _, rest = url.partition("#")
        url = head + "#" + rest.split("#", 1)[0]
    # A bare trailing `#` or `?` carries nothing. Stripped one character at a time on purpose:
    # rstrip("/#?") would also eat a trailing slash, which is a different path on some hosts.
    while url.endswith(("#", "?")):
        url = url[:-1]
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", url):
        url = "https://" + url.lstrip("/")
    return url


def derive_dedupe_key(rec: Dict[str, Any]) -> Optional[str]:
    """`NO|no.registration-d-number|you-cannot-apply` — the importer's own identity.

    Mirrors `parsers.FactRow.dedupe_key` exactly. It is derived, never read from the record: a
    generator-supplied key is a second source of truth for identity, and the two drifted six hours
    apart on 2026-08-13 (same company, two identities, 97 duplicate rows).
    """
    parts = [
        str(rec.get("destination_country") or "").strip().upper(),
        str(rec.get("entity_topic_key") or "").strip(),
        str(rec.get("fact_key") or "").strip(),
    ]
    if not all(parts):
        return None
    return "|".join(parts)


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().lstrip(".")
    except ValueError:
        return ""


# --------------------------------------------------------------------------- config


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    cfg = yaml.safe_load(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8")) or {}
    cfg.setdefault("settings", {})
    cfg.setdefault("hosts", {})
    return cfg


def authority_rank(url: str, hosts: Dict[str, int]) -> Optional[int]:
    """Longest-suffix match, so `www.skatteetaten.no` resolves from `skatteetaten.no`.

    Returns None for an unlisted host. None is a reportable gap, never a default rank — see the
    config file's header for why guessing here would defeat the point.
    """
    host = _host(url)
    if not host:
        return None
    best: Optional[Tuple[int, int]] = None
    for suffix, rank in hosts.items():
        s = str(suffix).lower()
        if host == s or host.endswith("." + s):
            if best is None or len(s) > best[0]:
                best = (len(s), int(rank))
    return best[1] if best else None


# --------------------------------------------------------------------------- V1 / V2


def check_record(rec: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[List[Finding], Optional[int], str]:
    """V1 + V2 for one already-normalised record. Returns (findings, source_rank, source_class)."""
    findings: List[Finding] = []

    # --- V1 structural: exactly what would make `parsers._to_row` raise ---
    missing = [k for k in REQUIRED_FIELDS if not str(rec.get(k) or "").strip()]
    if missing:
        findings.append(Finding(REJECT, "V1", "missing_required",
                                f"missing required field(s): {', '.join(missing)}"))

    applies_to = rec.get("applies_to")
    if applies_to is not None and not isinstance(applies_to, dict):
        findings.append(Finding(REJECT, "V1", "applies_to_shape",
                                f"applies_to must be an object, got {type(applies_to).__name__}"))
        applies_to = None

    country = str(rec.get("destination_country") or "").strip().upper()
    if country and not re.fullmatch(r"[A-Z]{2}", country):
        findings.append(Finding(REJECT, "V1", "country_shape",
                                f"destination_country {country!r} is not an ISO alpha-2 code"))

    # --- V1 vocabulary: accepted by the importer, refused at promote (silent) ---
    if country and re.fullmatch(r"[A-Z]{2}", country) and not iso_to_catalog_name(country):
        findings.append(Finding(
            WARN, "V1", "country_not_in_catalog",
            f"{country!r} has no requirement catalog coverage — mappings.resolve() will return "
            "Unmapped, so this stages and then never promotes"))

    domain_area = str(rec.get("domain_area") or "").strip().lower()
    if domain_area and domain_area != PROMOTABLE_DOMAIN_AREA:
        findings.append(Finding(
            WARN, "V1", "domain_area_not_promotable",
            f"domain_area {domain_area!r} is not {PROMOTABLE_DOMAIN_AREA!r}; resolve() refuses it"))

    fact_type = str(rec.get("fact_type") or "").strip().lower()
    if fact_type and fact_type not in KNOWN_FACT_TYPES:
        findings.append(Finding(WARN, "V1", "fact_type_unknown",
                                f"fact_type {fact_type!r} will be normalised to 'other'"))

    confidence = str(rec.get("confidence") or "").strip().lower()
    if confidence and confidence not in CONFIDENCE_SCORES:
        findings.append(Finding(WARN, "V1", "confidence_unknown",
                                f"confidence {confidence!r} is not one of "
                                f"{'/'.join(CONFIDENCE_SCORES)}; defaults to medium"))

    at = applies_to if isinstance(applies_to, dict) else {}
    nationality = str(at.get("nationality") or "").strip()
    if not nationality:
        findings.append(Finding(WARN, "V1", "no_nationality",
                                "applies_to.nationality absent — the audience is undefined and "
                                "resolve() refuses the topic"))
    elif nationality not in NATIONALITY_CLASSES:
        findings.append(Finding(WARN, "V1", "nationality_unknown",
                                f"applies_to.nationality {nationality!r} not in "
                                f"{'/'.join(NATIONALITY_CLASSES)}"))

    status = str(at.get("status") or "").strip()
    if not status:
        findings.append(Finding(WARN, "V1", "no_status",
                                "applies_to.status absent — resolve() refuses the topic"))
    elif status not in PURPOSES:
        findings.append(Finding(WARN, "V1", "status_unknown",
                                f"applies_to.status {status!r} not in {'/'.join(PURPOSES)}"))

    pillar = str(rec.get("pillar") or "").strip().upper()
    if pillar and pillar not in CANONICAL_PILLARS and pillar not in PILLAR_ALIASES:
        findings.append(Finding(WARN, "V1", "pillar_unknown",
                                f"pillar {pillar!r} is not a catalog pillar and has no alias"))

    # --- V2 source gate ---
    url = str(rec.get("source_url") or "").strip()
    rank = authority_rank(url, cfg.get("hosts", {}))
    source_class = classify_source(url) if url else UNOFFICIAL

    if url:
        if source_class == UNOFFICIAL:
            findings.append(Finding(
                REJECT, "V2", "unofficial_source",
                f"host {_host(url)!r} is not an official or public-agency publisher — the "
                "importer rejects this line"))
        if cfg.get("settings", {}).get("require_https", True) and not url.lower().startswith("https://"):
            findings.append(Finding(WARN, "V2", "not_https",
                                    f"source_url is not https: {url[:80]}"))
        reason = unspecific_citation_reason(url)
        if reason:
            findings.append(Finding(WARN, "V2", "unspecific_citation", reason))
        if rank is None:
            findings.append(Finding(
                WARN, "V2", "host_unranked",
                f"host {_host(url)!r} is not in the authority allowlist — no rank assigned"))

    return findings, rank, source_class


# --------------------------------------------------------------------------- driver


def verify_lines(lines: List[str], cfg: Dict[str, Any]) -> List[Verdict]:
    """V0 + V1 + V2 over the raw file. One Verdict per non-blank line, order preserved.

    Never raises on record content. That is the whole point: `read_jsonl` stops the batch on the
    first bad line, so if this function did too there would be nothing gained by running it.
    """
    verdicts: List[Verdict] = []
    seen: Dict[str, int] = {}

    for lineno, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue

        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as exc:
            verdicts.append(Verdict(lineno, None, None, [
                Finding(REJECT, "V0", "bad_json", f"not valid JSON — {exc}")]))
            continue
        if not isinstance(rec, dict):
            verdicts.append(Verdict(lineno, None, None, [
                Finding(REJECT, "V0", "not_an_object",
                        f"expected a JSON object, got {type(rec).__name__}")]))
            continue

        rec = dict(rec)
        if rec.get("source_url") is not None:
            rec["source_url"] = normalise_url(rec.get("source_url"))

        key = derive_dedupe_key(rec)
        findings, rank, source_class = check_record(rec, cfg)

        if key:
            if key in seen:
                findings.append(Finding(
                    REJECT, "V1", "duplicate_dedupe_key",
                    f"{key} already appeared on line {seen[key]} — both rows would collide on "
                    "the staging table's UNIQUE(dedupe_key), so the importer drops this one"))
            else:
                seen[key] = lineno

        verdicts.append(Verdict(lineno, key, rec, findings, rank, source_class))

    return verdicts


def summarise(verdicts: List[Verdict]) -> Dict[str, Any]:
    """Batch counts. `promotable` is the number that will actually become requirements."""
    kept = [v for v in verdicts if not v.rejected]

    # Rejected rows are counted by their REJECT reason only. Their incidental warnings are not
    # actionable — the row is not being imported — and folding them in inflates every warn count,
    # which is how a report stops being read.
    by_code: Dict[str, int] = {}
    for v in verdicts:
        for f in v.findings:
            if v.rejected and f.severity != REJECT:
                continue
            slug = f"{f.severity}:{f.check}/{f.code}"
            by_code[slug] = by_code.get(slug, 0) + 1

    ranks: Dict[str, int] = {}
    for v in kept:
        ranks[f"rank_{v.source_rank}" if v.source_rank else "rank_none"] = \
            ranks.get(f"rank_{v.source_rank}" if v.source_rank else "rank_none", 0) + 1

    return {
        "lines": len(verdicts),
        "clean": sum(1 for v in verdicts if v.clean),
        "warned": sum(1 for v in kept if v.warned),
        "rejected": sum(1 for v in verdicts if v.rejected),
        "promotable": sum(1 for v in kept if not v.warned),
        "findings_by_code": dict(sorted(by_code.items())),
        "source_rank_mix": dict(sorted(ranks.items())),
    }

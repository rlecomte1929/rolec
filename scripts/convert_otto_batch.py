#!/usr/bin/env python3
"""Convert an Otto corridor NDJSON stream into the dual parsers+loader vocabulary.

One output record carries both spellings, asserted equal, so
``import_otto_facts.py`` / ``parsers.read_jsonl`` and ``check_otto_batches.py``
can both read the same file. Nationality is taken from the artifact, never from
the corridor. ``applies_to.status`` is required (or ``--default-status`` batch-wide).

    python scripts/convert_otto_batch.py <in.ndjson> --out <clean-input.ndjson>
    python scripts/convert_otto_batch.py <in.ndjson> --check --out <committed.ndjson>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

KNOWN_FACT_TYPES = (
    "fee",
    "eligibility",
    "document",
    "deadline",
    "step",
    "where_to_apply",
    "other",
)
ALLOWED_DOMAINS = (
    "immigration",
    "registration",
    "tax",
    "social_security",
    "healthcare",
    "housing",
    "other",
    "vehicle",
    "vehicle_import",
    "domestic_move",
    "financial",
    "employer_compliance",
    "pet",
)
NATIONALITY_CLASSES = ("EU", "EEA", "non-EEA", "non-EU")
STATUS_TO_PURPOSE = {
    "professional": "employment",
    "student": "study",
    "family": "family",
    "any": "other",
}
SCORE = {"low": 0.3, "medium": 0.6, "high": 0.9}

# Artifact class names used by requirement_items batches → parsers vocab.
NATIONALITY_ALIASES = {
    "EU": "EU",
    "EEA": "EEA",
    "non-EEA": "non-EEA",
    "non-EU": "non-EU",
    "THIRD_COUNTRY": "non-EEA",
    "EU_EEA": "EEA",
    "OWN_NATIONAL": "EEA",
}

PROFILES = ("parsers", "requirement_items", "nested_entity", "beam")

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


class ConvertError(Exception):
    def __init__(self, msg: str, code: int = EXIT_FAIL) -> None:
        super().__init__(msg)
        self.code = code


def load_ndjson(path: Path) -> List[dict]:
    rows: List[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConvertError(f"line {i}: invalid JSON ({exc})") from exc
        if not isinstance(rec, dict):
            raise ConvertError(f"line {i}: expected a JSON object")
        rows.append(rec)
    return rows


def write_ndjson(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def detect_profile(first: dict) -> str:
    keys = set(first)
    if {"entity_topic_key", "fact_key", "destination_country"} <= keys:
        return "parsers"
    if "fact_uid" in keys or ("topic_key" in keys and "destination_country_code" in keys):
        return "requirement_items"
    if isinstance(first.get("entity"), dict):
        return "nested_entity"
    if any(k in keys for k in ("official_guidance", "actual_reality", "action_required", "category")):
        return "beam"
    raise ConvertError(
        "unknown profile; first-record keys: " + ", ".join(sorted(keys)),
        EXIT_USAGE,
    )


def _humanise(topic: str) -> str:
    return re.sub(r"[_\-]+", " ", str(topic)).strip().capitalize() or topic


def _as_applies(rec: dict) -> dict:
    applies = rec.get("applies_to")
    if isinstance(applies, dict):
        return dict(applies)
    return {}


def _map_nationality_token(raw: Any) -> Optional[str]:
    if raw is None or raw == "":
        return None
    text = str(raw).strip()
    if text in NATIONALITY_CLASSES:
        return text
    alias = NATIONALITY_ALIASES.get(text) or NATIONALITY_ALIASES.get(text.upper())
    if alias in NATIONALITY_CLASSES:
        return alias
    return None


def _pick_nationality(rec: dict, applies: dict) -> Optional[str]:
    candidates: List[Any] = []
    for src in (
        applies.get("nationality"),
        rec.get("applies_to_nationality_classes"),
        rec.get("nationality_classes"),
    ):
        if src is None or src == "":
            continue
        if isinstance(src, list):
            candidates.extend(src)
        else:
            candidates.append(src)
    mapped = []
    for raw in candidates:
        value = _map_nationality_token(raw)
        if value is not None and value not in mapped:
            mapped.append(value)
    if len(mapped) > 1:
        raise ConvertError(
            f"{_dedupe_key(rec)}: artifact nationality maps to multiple classes {mapped}"
        )
    if len(mapped) == 1:
        return mapped[0]
    return None


def _dedupe_key(rec: dict) -> str:
    if rec.get("dedupe_key"):
        return str(rec["dedupe_key"])
    dest = rec.get("destination_country") or rec.get("destination_country_code") or ""
    topic = rec.get("entity_topic_key") or rec.get("topic_key") or rec.get("category") or ""
    fact = rec.get("fact_key") or rec.get("fact_uid") or ""
    return f"{dest}|{topic}|{fact}"


def _destination(rec: dict, profile: str) -> str:
    raw = rec.get("destination_country") or rec.get("destination_country_code")
    if not raw and isinstance(rec.get("entity"), dict):
        raw = rec["entity"].get("destination_country")
    if not raw and rec.get("corridor"):
        # Artifact field (e.g. "NO->GB") — destination of the move, not a nationality class.
        _, _, dest = str(rec["corridor"]).partition("->")
        raw = dest.strip()
    if not raw:
        raise ConvertError(f"{_dedupe_key(rec)}: missing destination_country")
    return str(raw).strip().upper()


def _topic(rec: dict) -> str:
    if rec.get("entity_topic_key"):
        return str(rec["entity_topic_key"]).strip()
    if rec.get("topic_key"):
        return str(rec["topic_key"]).strip()
    if isinstance(rec.get("entity"), dict) and rec["entity"].get("topic_key"):
        return str(rec["entity"]["topic_key"]).strip()
    if rec.get("category"):
        return str(rec["category"]).strip()
    raise ConvertError(f"{_dedupe_key(rec)}: missing topic / entity_topic_key")


def _fact_key(rec: dict) -> str:
    if rec.get("fact_key"):
        return str(rec["fact_key"]).strip()
    if rec.get("fact_uid"):
        return str(rec["fact_uid"]).strip()
    raise ConvertError(f"{_dedupe_key(rec)}: missing fact_key/fact_uid")


def _title(rec: dict, topic: str) -> str:
    if rec.get("entity_title"):
        return str(rec["entity_title"])
    if rec.get("title"):
        return str(rec["title"])
    if isinstance(rec.get("entity"), dict) and rec["entity"].get("title"):
        return str(rec["entity"]["title"])
    return _humanise(topic)


def _fact_text(rec: dict) -> str:
    if rec.get("fact_text"):
        return str(rec["fact_text"])
    parts: List[str] = []
    for label, key in (
        ("Official guidance", "official_guidance"),
        ("Actual reality", "actual_reality"),
        ("Action required", "action_required"),
    ):
        val = rec.get(key)
        if val:
            parts.append(f"{label}: {str(val).strip()}")
    if parts:
        return "\n".join(parts)
    raise ConvertError(f"{_dedupe_key(rec)}: missing fact_text")


def _source_url(rec: dict) -> str:
    url = rec.get("source_url")
    if not url or not str(url).strip():
        raise ConvertError(f"{_dedupe_key(rec)}: missing source_url")
    return str(url).strip()


def _domain(rec: dict) -> Tuple[str, Optional[str]]:
    raw = rec.get("domain_area")
    if not raw and isinstance(rec.get("entity"), dict):
        raw = rec["entity"].get("domain_area")
    if not raw:
        return "other", None
    raw_s = str(raw).strip()
    if raw_s in ALLOWED_DOMAINS:
        return raw_s, None
    return "other", raw_s


def _fact_type(rec: dict, profile: str) -> Tuple[str, Optional[str]]:
    raw = rec.get("fact_type")
    if not raw and profile == "beam":
        raw = rec.get("category")
    if not raw:
        return "other", None
    raw_s = str(raw).strip()
    if raw_s == "timeline":
        return "deadline", "timeline"
    if raw_s in KNOWN_FACT_TYPES:
        return raw_s, None
    return "other", raw_s


def _confidence(rec: dict) -> Tuple[str, float]:
    label = rec.get("confidence")
    if label in SCORE:
        return str(label), SCORE[str(label)]
    return "medium", SCORE["medium"]


def flatten_profile(rec: dict, profile: str) -> dict:
    """Copy the input and lift profile-specific aliases onto parsers keys (in-memory)."""
    out = dict(rec)
    if profile == "requirement_items":
        if "fact_uid" in rec and "fact_key" not in rec:
            out["fact_key"] = rec["fact_uid"]
        if "topic_key" in rec and "entity_topic_key" not in rec:
            out["entity_topic_key"] = rec["topic_key"]
        if "destination_country_code" in rec and "destination_country" not in rec:
            out["destination_country"] = rec["destination_country_code"]
        if "title" in rec and "entity_title" not in rec:
            out["entity_title"] = rec["title"]
    elif profile == "nested_entity" and isinstance(rec.get("entity"), dict):
        ent = rec["entity"]
        out.setdefault("destination_country", ent.get("destination_country"))
        out.setdefault("entity_topic_key", ent.get("topic_key"))
        out.setdefault("entity_title", ent.get("title"))
        out.setdefault("domain_area", ent.get("domain_area"))
    elif profile == "beam":
        out.setdefault("entity_topic_key", rec.get("category"))
        if not out.get("fact_key") and rec.get("fact_uid"):
            out["fact_key"] = rec["fact_uid"]
    return out


def assert_paired(out: dict) -> None:
    topic = out["entity_topic_key"]
    dest = out["destination_country"]
    title = out["entity_title"]
    domain = out["domain_area"]
    entity = out["entity"]
    if out["topic_key"] != topic or entity["topic_key"] != topic:
        raise ConvertError(
            f"{out.get('fact_key')}: topic_key != entity_topic_key == entity.topic_key"
        )
    if entity["destination_country"] != dest:
        raise ConvertError(f"{out.get('fact_key')}: entity.destination_country mismatch")
    if entity["title"] != title:
        raise ConvertError(f"{out.get('fact_key')}: entity.title != entity_title")
    if entity["domain_area"] != domain or domain not in ALLOWED_DOMAINS:
        raise ConvertError(f"{out.get('fact_key')}: domain_area pairing failed")
    label = out["confidence"]
    score = out["confidence_score"]
    if SCORE.get(label) != score:
        raise ConvertError(f"{out.get('fact_key')}: confidence_score != SCORE[confidence]")
    if score is None or not (isinstance(score, (int, float)) and 0 < float(score) <= 1):
        raise ConvertError(f"{out.get('fact_key')}: confidence_score must be in (0, 1]")


def convert_record(
    rec: dict,
    profile: str,
    *,
    default_status: Optional[str],
    report: dict,
) -> dict:
    src = flatten_profile(rec, profile)
    dest = _destination(src, profile)
    topic = _topic(src)
    fact_key = _fact_key(src)
    title = _title(src, topic)
    fact_text = _fact_text(src)
    source_url = _source_url(src)
    fact_type, ft_down = _fact_type(src, profile)
    domain, dom_down = _domain(src)
    conf_label, score = _confidence(src)

    applies = _as_applies(src)
    status = applies.get("status") or default_status
    if not status:
        raise ConvertError(
            f"missing applies_to.status on {_dedupe_key(src)} (pass --default-status to stamp batch-wide)"
        )
    if status not in STATUS_TO_PURPOSE:
        raise ConvertError(
            f"{_dedupe_key(src)}: applies_to.status {status!r} not in {tuple(STATUS_TO_PURPOSE)}"
        )
    applies["status"] = status

    nat = _pick_nationality(src, applies)
    if nat is None:
        applies.pop("nationality", None)
        report["missing_nationality"].append(
            _dedupe_key(
                {
                    **src,
                    "destination_country": dest,
                    "entity_topic_key": topic,
                    "fact_key": fact_key,
                }
            )
        )
    else:
        applies["nationality"] = nat

    if src.get("pillar") is not None:
        applies["pillar"] = src["pillar"]

    if profile == "beam" or any(src.get(k) for k in ("official_guidance", "actual_reality", "action_required")):
        beam = {
            k: src.get(k)
            for k in ("official_guidance", "actual_reality", "action_required", "source")
            if src.get(k) is not None
        }
        if beam:
            applies["_beam"] = beam

    for opt in ("non_obvious", "timing"):
        if src.get(opt) is not None and opt not in applies:
            applies[opt] = src[opt]

    if ft_down is not None and ft_down != fact_type:
        report["downgrades"]["fact_type"].append({"fact_key": fact_key, "from": ft_down, "to": fact_type})
    if dom_down is not None:
        report["downgrades"]["domain_area"].append({"fact_key": fact_key, "from": dom_down, "to": domain})

    out = {
        "destination_country": dest,
        "entity_topic_key": topic,
        "entity_title": title,
        "fact_key": fact_key,
        "fact_text": fact_text,
        "source_url": source_url,
        "fact_type": fact_type,
        "confidence": conf_label,
        "confidence_score": score,
        "applies_to": applies,
        "target_table": "requirement_facts",
        "topic_key": topic,
        "domain_area": domain,
        "entity": {
            "destination_country": dest,
            "topic_key": topic,
            "domain_area": domain,
            "title": title,
        },
    }
    if src.get("evidence_quote") is not None:
        out["evidence_quote"] = src["evidence_quote"]
    if src.get("dedupe_key"):
        out["dedupe_key"] = src["dedupe_key"]
    assert_paired(out)
    return out


def convert_rows(
    rows: List[dict],
    *,
    profile: Optional[str] = None,
    default_status: Optional[str] = None,
) -> Tuple[List[dict], dict]:
    if not rows:
        raise ConvertError("empty input", EXIT_FAIL)
    detected = profile or detect_profile(rows[0])
    if detected not in PROFILES:
        raise ConvertError(f"unknown profile {detected!r}", EXIT_USAGE)
    report: dict = {
        "profile": detected,
        "records_in": len(rows),
        "records_out": 0,
        "downgrades": {"fact_type": [], "domain_area": []},
        "missing_nationality": [],
    }
    missing_status: List[str] = []
    converted: List[dict] = []
    errors: List[str] = []
    for rec in rows:
        try:
            converted.append(
                convert_record(rec, detected, default_status=default_status, report=report)
            )
        except ConvertError as exc:
            if "missing applies_to.status" in str(exc):
                missing_status.append(str(exc))
            else:
                errors.append(str(exc))
    if missing_status:
        raise ConvertError("missing applies_to.status: " + "; ".join(missing_status))
    if errors:
        raise ConvertError("; ".join(errors))
    if len(converted) != len(rows):
        raise ConvertError(f"dropped facts: in={len(rows)} out={len(converted)}")
    report["records_out"] = len(converted)
    return converted, report


def records_equal(a: List[dict], b: List[dict]) -> List[str]:
    diffs: List[str] = []
    if len(a) != len(b):
        diffs.append(f"length {len(a)} != {len(b)}")
        return diffs
    sa = sorted((json.dumps(r, sort_keys=True, ensure_ascii=False) for r in a))
    sb = sorted((json.dumps(r, sort_keys=True, ensure_ascii=False) for r in b))
    if sa != sb:
        for i, (x, y) in enumerate(zip(sa, sb)):
            if x != y:
                diffs.append(f"record {i} differs")
                break
        else:
            diffs.append("record set differs")
    return diffs


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ndjson", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--profile", choices=PROFILES, default=None)
    ap.add_argument("--default-status", choices=tuple(STATUS_TO_PURPOSE), default=None)
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    if not args.ndjson.is_file():
        print(f"usage: input not found: {args.ndjson}", file=sys.stderr)
        return EXIT_USAGE
    try:
        rows = load_ndjson(args.ndjson)
        converted, report = convert_rows(
            rows, profile=args.profile, default_status=args.default_status
        )
    except ConvertError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code

    if args.check:
        if not args.out.is_file():
            print(f"--check: committed file missing: {args.out}", file=sys.stderr)
            return EXIT_FAIL
        committed = load_ndjson(args.out)
        diffs = records_equal(converted, committed)
        if diffs:
            print("--check mismatch: " + "; ".join(diffs), file=sys.stderr)
            return EXIT_FAIL
        print(f"--check ok ({len(converted)} records, profile={report['profile']})")
        return EXIT_OK

    write_ndjson(args.out, converted)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"converted {report['records_in']} -> {report['records_out']} "
        f"profile={report['profile']}"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

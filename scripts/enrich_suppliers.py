#!/usr/bin/env python3
"""Fill-empty enrichment of existing suppliers from an Otto enrichment NDJSON.

The vendor HARVEST pipeline (`scripts/land_vendor_candidates.py` + `backend/imports/suppliers/`)
only CREATES suppliers — it matches an incoming row to an existing supplier by name, or mints a
new `vc-<uuid>`; there is no `supplier_id` inbound key. ENRICHMENT is the opposite operation:
take suppliers we already hold (keyed on `supplier_id`) and fill the fields the product actually
reads but the harvest left empty. So this is a separate, direct-UPDATE applier, modeled on
`scripts/backfill_supplier_base_country.py` (per-`supplier_id` UPDATE, dry-run default, `--apply`).

**The one invariant: fill-empty only.** A field is written ONLY when the prod column is empty and
Otto returned a sourced, confident value. A non-empty (curated/approved/human) value is NEVER
overwritten — this is enforced in Python (read-then-decide), not by trusting COALESCE alone, so
the dry run can prove "0 overwrites" before any write.

Fields written (the product-consumed set — see docs/imports plan; the ~17 columns no surface reads
are deliberately NOT touched):
  suppliers:                       contact_email, contact_phone, description, languages_supported
  supplier_service_capabilities:   specialization_tags, min_budget, max_budget, city_name
                                   (keyed on supplier_id + --category)

Otto NDJSON per line (keys echoed back verbatim from the exported target list):
  key, firm_name, status, notes,
  contact_email, contact_phone, description, languages_supported[], specialization_tags[],
  min_budget, max_budget, budget_currency, city,
  and, per populated field, a "<field>_source_url" and a "<field>_confidence" (or a row-level
  "confidence"). A field with no source_url, low confidence, or a not_found/unreachable row status
  is dropped (never guessed).

Usage:
    # preview (default) — decides everything, writes nothing
    python scripts/enrich_suppliers.py <enrich.ndjson> --category schools
    # with the SHA/count/target-membership gate re-checked inline
    python scripts/enrich_suppliers.py <enrich.ndjson> --category schools \
        --manifest <manifest.json> --target-keys <target.csv>
    # write
    python scripts/enrich_suppliers.py <enrich.ndjson> --category schools --apply

Reads DATABASE_URL. Dry run is the DEFAULT and takes the same decide path a real run does.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── field sets ────────────────────────────────────────────────────────────────
SUPPLIER_TEXT_FIELDS = ("contact_email", "contact_phone", "description")
SUPPLIER_JSON_FIELDS = ("languages_supported",)          # TEXT column holding a JSON array string
CAP_JSON_FIELDS = ("specialization_tags",)               # TEXT column holding a JSON array string
CAP_NUM_FIELDS = ("min_budget", "max_budget")
CAP_TEXT_FIELDS = ("city_name",)

# NDJSON key -> (table, column). "city" maps to the capability's city_name.
NDJSON_TO_COLUMN = {
    "contact_email": ("suppliers", "contact_email"),
    "contact_phone": ("suppliers", "contact_phone"),
    "description": ("suppliers", "description"),
    "languages_supported": ("suppliers", "languages_supported"),
    "specialization_tags": ("supplier_service_capabilities", "specialization_tags"),
    "min_budget": ("supplier_service_capabilities", "min_budget"),
    "max_budget": ("supplier_service_capabilities", "max_budget"),
    "city": ("supplier_service_capabilities", "city_name"),
}

_ACCEPT_STATUS = {"found", "partial"}
_CONF_RANK = {"low": 0, "med": 1, "medium": 1, "high": 2}
#: contact_email local-parts that are never a usable relocation contact (fraud / press / abuse).
_BAD_EMAIL_LOCAL = re.compile(r"^(?:security|fraud|abuse|phish|presse?|media|dpo|privacy)\b", re.I)
#: fields we require an explicit *_source_url for (identity/contact claims); descriptive
#: fields (tags/langs/city) are low-risk and allowed with just confidence.
_SOURCE_REQUIRED = {"contact_email", "contact_phone", "description"}


@dataclass
class FieldDecision:
    ndjson_field: str
    table: str
    column: str
    value: object
    outcome: str  # "fill" | "skip:already" | "skip:lowconf" | "skip:nosource" | "skip:honesty" | "skip:empty"


@dataclass
class RowDecision:
    key: str
    firm_name: str
    status: str
    fields: List[FieldDecision] = field(default_factory=list)
    row_skipped: Optional[str] = None  # reason if the whole row is dropped


# ── pure helpers (importable / testable) ───────────────────────────────────────
def is_empty_text(v: Optional[str]) -> bool:
    return v is None or str(v).strip() == ""


def is_empty_jsonarray(v: Optional[str]) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    return s in ("", "[]", "null", "{}")


def _conf_ok(row: dict, ndjson_field: str, floor: int) -> bool:
    raw = row.get(f"{ndjson_field}_confidence", row.get("confidence"))
    if raw is None:
        return True  # no confidence stated → don't block; source_url gate still applies
    return _CONF_RANK.get(str(raw).strip().lower(), 0) >= floor


def _normalise_value(ndjson_field: str, value):
    """Coerce an Otto value into the DB text/number shape; return None if unusable."""
    table, column = NDJSON_TO_COLUMN[ndjson_field]
    if value is None:
        return None
    if column in CAP_NUM_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if ndjson_field in SUPPLIER_JSON_FIELDS or ndjson_field in ("specialization_tags",):
        # store a JSON-array string, matching the existing '["en","zh"]' shape
        if isinstance(value, str):
            value = [value] if value.strip() else []
        if not isinstance(value, (list, tuple)):
            return None
        items = [str(x).strip() for x in value if str(x).strip()]
        return json.dumps(items, ensure_ascii=False) if items else None
    s = str(value).strip()
    return s or None


def decide_row(row: dict, current: Dict[Tuple[str, str], object], *, conf_floor: int) -> RowDecision:
    """Pure decision for one Otto row against the current prod values.

    `current` maps (table, column) -> current DB value for this supplier_id (capability row
    already filtered to the target category). Returns a RowDecision listing, per field, whether
    it is filled or the reason it is skipped. Never proposes overwriting a non-empty column.
    """
    key = str(row.get("key", "")).strip()
    dec = RowDecision(key=key, firm_name=str(row.get("firm_name", "") or key), status=str(row.get("status", "") or "").strip().lower())
    if dec.status and dec.status not in _ACCEPT_STATUS:
        dec.row_skipped = f"status={dec.status}"
        return dec

    for nf, (table, column) in NDJSON_TO_COLUMN.items():
        raw = row.get(nf)
        value = _normalise_value(nf, raw)
        if value is None:
            continue  # nothing offered for this field
        # source gate
        if nf in _SOURCE_REQUIRED and is_empty_text(row.get(f"{nf}_source_url")):
            dec.fields.append(FieldDecision(nf, table, column, value, "skip:nosource"))
            continue
        # confidence gate
        if not _conf_ok(row, nf, conf_floor):
            dec.fields.append(FieldDecision(nf, table, column, value, "skip:lowconf"))
            continue
        # honesty backstop for contact_email
        if nf == "contact_email":
            local = value.split("@", 1)[0]
            if _BAD_EMAIL_LOCAL.match(local):
                dec.fields.append(FieldDecision(nf, table, column, value, "skip:honesty"))
                continue
        # fill-empty gate — never overwrite a non-empty prod value
        cur = current.get((table, column))
        empty = is_empty_jsonarray(cur) if column in ("languages_supported", "specialization_tags") else \
            (cur is None if column in CAP_NUM_FIELDS else is_empty_text(cur))
        if not empty:
            dec.fields.append(FieldDecision(nf, table, column, value, "skip:already"))
            continue
        dec.fields.append(FieldDecision(nf, table, column, value, "fill"))
    return dec


# ── I/O ─────────────────────────────────────────────────────────────────────
def _read_ndjson(path: str) -> List[dict]:
    rows = []
    with open(path, "rb") as fh:
        raw = fh.read()
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows, raw


def _verify_manifest(ndjson_path: str, raw: bytes, rows: List[dict], manifest_path: str) -> None:
    man = json.load(open(manifest_path, encoding="utf-8"))
    want = man.get("sha256_ndjson") or man.get("sha256")
    got = hashlib.sha256(raw).hexdigest()
    if want and want != got:
        raise SystemExit(f"✖ sha256 mismatch: manifest {want} != file {got}")
    rc = man.get("record_count")
    if rc is not None and int(rc) != len(rows):
        raise SystemExit(f"✖ record_count mismatch: manifest {rc} != {len(rows)} lines")
    print(f"  manifest OK: sha256 {got[:12]}…, record_count {len(rows)}")


def _load_target_keys(path: str) -> set:
    keys = set()
    with open(path, encoding="utf-8") as fh:
        sniff = fh.read(2048)
        fh.seek(0)
        if "|" in sniff:
            for line in fh:
                line = line.strip()
                if line:
                    keys.add(line.split("|", 1)[0].strip())
        else:
            for r in csv.reader(fh):
                if r and r[0].strip() and r[0].strip().lower() not in ("key", "id"):
                    keys.add(r[0].strip())
    return keys


_TRIPWIRE = (
    "SELECT count(*), md5(string_agg("
    "id::text||platform_vetting_status||coalesce(service_category,''),'|' ORDER BY id::text)) "
    "FROM supplier_service_capabilities WHERE platform_vetting_status='approved'"
)


def _load_current(conn, keys: List[str], category: str) -> Dict[str, Dict[Tuple[str, str], object]]:
    from sqlalchemy import text
    out: Dict[str, Dict[Tuple[str, str], object]] = {k: {} for k in keys}
    for r in conn.execute(text(
        "SELECT id, contact_email, contact_phone, description, languages_supported "
        "FROM public.suppliers WHERE id = ANY(:keys)"
    ), {"keys": keys}).mappings():
        d = out.setdefault(r["id"], {})
        d[("suppliers", "contact_email")] = r["contact_email"]
        d[("suppliers", "contact_phone")] = r["contact_phone"]
        d[("suppliers", "description")] = r["description"]
        d[("suppliers", "languages_supported")] = r["languages_supported"]
    for r in conn.execute(text(
        "SELECT supplier_id, specialization_tags, min_budget, max_budget, city_name "
        "FROM public.supplier_service_capabilities "
        "WHERE supplier_id = ANY(:keys) AND service_category = :cat"
    ), {"keys": keys, "cat": category}).mappings():
        d = out.setdefault(r["supplier_id"], {})
        d[("supplier_service_capabilities", "specialization_tags")] = r["specialization_tags"]
        d[("supplier_service_capabilities", "min_budget")] = r["min_budget"]
        d[("supplier_service_capabilities", "max_budget")] = r["max_budget"]
        d[("supplier_service_capabilities", "city_name")] = r["city_name"]
    return out


def _apply_row(conn, dec: RowDecision, category: str) -> int:
    from sqlalchemy import text
    sup = {fd.column: fd.value for fd in dec.fields if fd.outcome == "fill" and fd.table == "suppliers"}
    cap = {fd.column: fd.value for fd in dec.fields if fd.outcome == "fill" and fd.table == "supplier_service_capabilities"}
    n = 0
    if sup:
        sets = ", ".join(f"{c} = :{c}" for c in sup)
        params = dict(sup); params["sid"] = dec.key
        conn.execute(text(f"UPDATE public.suppliers SET {sets}, updated_at = now() WHERE id = :sid"), params)
        n += len(sup)
    if cap:
        sets = ", ".join(f"{c} = :{c}" for c in cap)
        params = dict(cap); params["sid"] = dec.key; params["cat"] = category
        conn.execute(text(
            f"UPDATE public.supplier_service_capabilities SET {sets}, updated_at = now() "
            "WHERE supplier_id = :sid AND service_category = :cat"
        ), params)
        n += len(cap)
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ndjson", help="Otto enrichment NDJSON (one firm per line, keyed on supplier_id)")
    ap.add_argument("--category", required=True, help="capability service_category to enrich (e.g. schools)")
    ap.add_argument("--manifest", help="verify sha256_ndjson + record_count against this manifest before applying")
    ap.add_argument("--target-keys", help="assert every ndjson key is in this exported target list (KEY|... or CSV)")
    ap.add_argument("--min-confidence", default="med", choices=["low", "med", "high"], help="drop fields below this (default med)")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set"); return 2

    rows, raw = _read_ndjson(args.ndjson)
    print(f"read {len(rows)} enrichment row(s) from {args.ndjson}\n")
    if args.manifest:
        _verify_manifest(args.ndjson, raw, rows, args.manifest)
    keys = [str(r.get("key", "")).strip() for r in rows if str(r.get("key", "")).strip()]
    if len(keys) != len(rows):
        raise SystemExit("✖ a row is missing its key")
    if args.target_keys:
        allowed = _load_target_keys(args.target_keys)
        stray = sorted(set(keys) - allowed)
        if stray:
            raise SystemExit(f"✖ {len(stray)} key(s) not in the exported target set (rejecting batch): {stray[:5]}…")
        print(f"  target-keys OK: all {len(keys)} keys ∈ exported set of {len(allowed)}")

    conf_floor = _CONF_RANK[args.min_confidence]

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url, future=True)
    with engine.connect() as conn:
        # every key must resolve to a real supplier
        present = {r[0] for r in conn.execute(text("SELECT id FROM public.suppliers WHERE id = ANY(:k)"), {"k": keys})}
        missing = sorted(set(keys) - present)
        if missing:
            raise SystemExit(f"✖ {len(missing)} key(s) are not suppliers in prod: {missing[:5]}…")
        current = _load_current(conn, keys, args.category)

    decisions = [decide_row(r, current.get(str(r.get("key", "")).strip(), {}), conf_floor=conf_floor) for r in rows]

    # ── report ──
    fills = sum(1 for d in decisions for fd in d.fields if fd.outcome == "fill")
    overwrites = sum(1 for d in decisions for fd in d.fields if fd.outcome == "skip:already")  # never applied
    print(f"\ndecided: {fills} field-fill(s) across {sum(1 for d in decisions if any(f.outcome=='fill' for f in d.fields))} supplier(s)")
    print(f"  (skipped: {overwrites} already-filled, "
          f"{sum(1 for d in decisions for fd in d.fields if fd.outcome=='skip:lowconf')} low-confidence, "
          f"{sum(1 for d in decisions for fd in d.fields if fd.outcome=='skip:nosource')} no-source, "
          f"{sum(1 for d in decisions for fd in d.fields if fd.outcome=='skip:honesty')} honesty, "
          f"{sum(1 for d in decisions if d.row_skipped)} rows dropped by status)\n")
    for d in decisions:
        if d.row_skipped:
            print(f"  – {d.firm_name[:38]:38} ROW SKIP ({d.row_skipped})")
            continue
        for fd in d.fields:
            if fd.outcome == "fill":
                v = fd.value if len(str(fd.value)) <= 50 else str(fd.value)[:47] + "…"
                print(f"  ✎ {d.firm_name[:30]:30} {fd.column:20} = {v}")
    print("\nGUARANTEE: 0 non-empty fields overwritten (fill-empty is decided in Python; 'already-filled' rows are never written).")

    if not args.apply:
        print("\n  (preview — pass --apply to write)")
        return 0

    # ── apply, tripwire-guarded ──
    with engine.connect() as conn:
        before = conn.execute(text(_TRIPWIRE)).one()
    written = 0
    with engine.begin() as conn:
        for d in decisions:
            if not d.row_skipped:
                written += _apply_row(conn, d, args.category)
        after = conn.execute(text(_TRIPWIRE)).one()
        if tuple(after) != tuple(before):
            raise SystemExit(f"✖ append-only tripwire MOVED (approved {before} → {after}) — rolling back")
    print(f"\nwritten: {written} field(s). Tripwire approved-capabilities UNCHANGED: {before[0]} | {before[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

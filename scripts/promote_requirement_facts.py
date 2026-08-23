#!/usr/bin/env python3
"""Emit the SQL that promotes a committed corridor batch into `public.requirement_facts`.

GENERATES SQL. DOES NOT CONNECT TO A DATABASE. The output is reviewed, then applied by an
operator. That is deliberate: promotion is a human-gated step, and a script holding production
credentials makes "dry run by default" a promise rather than a property.

WHY THIS EXISTS AT ALL. Two requirement pipelines exist and they do not meet.
`backend/imports/otto/executor.promote()` writes `public.requirement_items`, which feeds the
public corridor endpoint and the rules engine. The employee dossier reads a *different* table —
`requirement_facts JOIN requirement_entities`, via `backend/db/policies.py`
`list_approved_requirement_facts`. So the existing `--promote` tooling cannot land a batch where
a mover would see it, and until now nothing could.

WHY NOT `ON CONFLICT`. Verified against production 2026-08-23: `requirement_facts`,
`requirement_entities` and `knowledge_docs` each carry a PRIMARY KEY on a `gen_random_uuid()`
`id` and NO other unique constraint. There is nothing to conflict on, so a naive re-run inserts
every row again, silently. Idempotency therefore comes from a DETERMINISTIC id — uuid5 over the
natural key — plus a `WHERE NOT EXISTS` guard on that id. Re-running is a no-op, and the guard is
what makes it one; the id alone would raise instead.

THREE INVARIANTS, each enforced by construction rather than by care:
  * INSERT only. No UPDATE is emitted anywhere, so the 25 IE rows that already carry a
    `reviewed_by` cannot be touched.
  * `status = 'pending'`, written explicitly. `list_approved_requirement_facts` serves only
    `'approved'`, so pending IS the gate — nothing here reaches a mover until a human flips it.
  * `evidence_verified` left NULL. NULL means "never checked", which the dossier renders as
    "Source — not independently verified". Writing TRUE would claim a check nobody ran, and that
    is how 705 live facts came to cite text that is not in their document.

SOURCE TEXT. `knowledge_docs.text_content` is NOT NULL and a placeholder there is worse than a
missing row: production holds 222 documents whose entire text is "Otto bridge capture,
unverified — see source_url", carrying 705 unverifiable quotes. This emitter refuses to run
unless the batch's `sources/` directory holds real extracted text for every cited URL, and it
re-checks each quote against that text before emitting a single line.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://relopass.com/ns/requirement_facts")

#: `knowledge_packs.domain` is CHECK-constrained to
#: immigration | registration | payroll | housing | tax | other.
#: Only `immigration`, `registration`, `tax` and `other` are in use today, but `payroll` exists
#: and is the honest home for a PPSN document. `healthcare` has no pack domain at all, so it
#: files under `other`. The alternative — putting every document in the one existing IE
#: immigration pack — would mislabel tax and health sources as immigration.
PACK_DOMAIN = {
    "immigration": "immigration",
    "registration": "registration",
    "tax": "tax",
    "social_security": "payroll",
    "healthcare": "other",
}


def _norm_module():
    spec = importlib.util.spec_from_file_location("v", REPO / "scripts/verify_batch_quotes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pdf_title(text: str) -> str | None:
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    first = re.sub(r"^DOC TITLE:\s*", "", first, flags=re.I).strip()
    return first[:120] or None


def _title_from_url(url: str) -> str:
    """Title from the URL path, not from the page text.

    The extracted text of several of these pages opens with a cookie banner, so the first N
    characters make a title like "Critical Skills Employment Permit - DETE Our website uses
    cookies to enhance your browsing…". The last meaningful path segment is both cleaner and
    deterministic, which matters because the id is derived and the row is written once.
    """
    generic = {"index", "files", "home", "default", "en", "ie"}
    parts = [p for p in url.rstrip("/").split("/")[3:] if p and not p.isdigit()]
    parts = [re.sub(r"\.(aspx|html?|php)$", "", p) for p in parts]
    meaningful = [p for p in parts if p.lower() not in generic]
    slug = meaningful[-1] if meaningful else (parts[-1] if parts else url.split("/")[2])
    return re.sub(r"[-_]+", " ", slug).strip().title()[:120] or url[:120]


def q(value) -> str:
    """SQL literal. None -> NULL; everything else single-quoted with doubled quotes."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_dir", type=Path)
    ap.add_argument("--out", type=Path, help="write SQL here instead of stdout")
    args = ap.parse_args()

    v = _norm_module()
    batch = args.batch_dir if args.batch_dir.is_absolute() else REPO / args.batch_dir
    stream = next(p for p in sorted(batch.glob("*.ndjson")) if ".flat." not in p.name)
    rows = [json.loads(l) for l in stream.read_text().splitlines() if l.strip()]

    index_path = batch / "sources" / "index.json"
    if not index_path.exists():
        raise SystemExit(f"no captured source text at {index_path} — run verify_batch_quotes.py first")
    index = json.loads(index_path.read_text())
    texts = {u: (batch / "sources" / m["file"]).read_text() for u, m in index.items()}
    pages = {u: v.norm(t) for u, t in texts.items()}

    # Refuse rather than promote an unverifiable quote.
    missing_src = sorted({r["source_url"] for r in rows} - set(texts))
    if missing_src:
        raise SystemExit("no captured text for: " + ", ".join(missing_src))
    unverified = [r["fact_key"] for r in rows
                  if v.norm(r["evidence_quote"] or "") not in pages[r["source_url"]]]
    if unverified:
        raise SystemExit(f"{len(unverified)} quote(s) do not appear on their cited page: {unverified}")

    dest = rows[0]["destination_country"]
    packs, docs, entities, facts = {}, {}, {}, []

    for r in rows:
        ent = r["entity"]
        domain = PACK_DOMAIN[ent["domain_area"]]
        pack_id = str(uuid.uuid5(NS, f"pack:{dest}:{domain}"))
        packs[(dest, domain)] = pack_id

        url = r["source_url"]
        if url not in docs:
            text = texts[url]
            docs[url] = {
                "id": str(uuid.uuid5(NS, f"doc:{url}")),
                "pack_id": pack_id,
                # A PDF names itself on its first line; a web page's extracted text opens
                # with navigation, so only the PDF branch trusts the document.
                "title": (_pdf_title(text) if index[url].get("is_pdf") else None)
                         or _title_from_url(url),
                "publisher": re.sub(r"^www\d*\.", "", url.split("/")[2]),
                "source_url": url,
                "text_content": text,
                "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "is_pdf": index[url].get("is_pdf", False),
            }

        ent_id = str(uuid.uuid5(NS, f"entity:{dest}:{ent['topic_key']}"))
        entities[ent["topic_key"]] = {
            "id": ent_id, "destination_country": dest,
            "domain_area": ent["domain_area"], "topic_key": ent["topic_key"],
            # CHECK-constrained to pending | approved | rejected. An entity arrives unreviewed
            # like its facts; 'active' is the knowledge_packs vocabulary, not this one.
            "title": ent.get("title") or ent["topic_key"], "status": "pending",
        }
        facts.append({
            "id": str(uuid.uuid5(NS, f"fact:{dest}:{ent['topic_key']}:{r['fact_key']}")),
            "entity_id": ent_id, "source_doc_id": docs[url]["id"],
            "fact_type": r["fact_type"], "fact_key": r["fact_key"],
            "fact_text": r["fact_text"], "applies_to": r.get("applies_to") or {},
            "required_fields": r.get("required_fields") or [],
            "source_url": url, "evidence_quote": r["evidence_quote"],
            "confidence": r.get("confidence") or "medium",
        })

    out = [
        "-- Generated by scripts/promote_requirement_facts.py — DO NOT hand-edit.",
        f"-- batch: {stream.name}   records: {len(rows)}",
        f"-- packs: {len(packs)}  knowledge_docs: {len(docs)}  entities: {len(entities)}  facts: {len(facts)}",
        "-- Every quote was re-checked against the captured source text before emitting.",
        "-- INSERT-only, guarded by NOT EXISTS on a deterministic uuid5 id: re-running is a no-op.",
        "BEGIN;",
        "",
    ]

    for (d, domain), pid in sorted(packs.items(), key=lambda kv: kv[0][1]):
        out.append(
            f"INSERT INTO public.knowledge_packs (id, destination_country, domain, version, status)\n"
            f"SELECT {q(pid)}::uuid, {q(d)}, {q(domain)}, 1, 'active'\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM public.knowledge_packs WHERE id = {q(pid)}::uuid);")
    out.append("")

    for doc in docs.values():
        note = "  -- PDF, extracted with pypdf" if doc["is_pdf"] else ""
        out.append(
            f"INSERT INTO public.knowledge_docs (id, pack_id, title, publisher, source_url,\n"
            f"                                   text_content, content_sha256, fetch_status, fetched_at)\n"
            f"SELECT {q(doc['id'])}::uuid, {q(doc['pack_id'])}::uuid, {q(doc['title'])},\n"
            f"       {q(doc['publisher'])}, {q(doc['source_url'])},\n"
            f"       {q(doc['text_content'])}, {q(doc['content_sha256'])}, 'fetched', now()\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM public.knowledge_docs WHERE id = {q(doc['id'])}::uuid);{note}")
    out.append("")

    for ent in entities.values():
        out.append(
            f"INSERT INTO public.requirement_entities (id, destination_country, domain_area, topic_key, title, status)\n"
            f"SELECT {q(ent['id'])}::uuid, {q(ent['destination_country'])}, {q(ent['domain_area'])},\n"
            f"       {q(ent['topic_key'])}, {q(ent['title'])}, {q(ent['status'])}\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM public.requirement_entities WHERE id = {q(ent['id'])}::uuid);")
    out.append("")

    for f in facts:
        out.append(
            f"INSERT INTO public.requirement_facts (id, entity_id, source_doc_id, fact_type, fact_key,\n"
            f"                                      fact_text, applies_to, required_fields, source_url,\n"
            f"                                      evidence_quote, confidence, status, evidence_verified)\n"
            f"SELECT {q(f['id'])}::uuid, {q(f['entity_id'])}::uuid, {q(f['source_doc_id'])}::uuid,\n"
            f"       {q(f['fact_type'])}, {q(f['fact_key'])}, {q(f['fact_text'])},\n"
            f"       {q(f['applies_to'])}, {q(f['required_fields'])}, {q(f['source_url'])},\n"
            f"       {q(f['evidence_quote'])}, {q(f['confidence'])}, 'pending', NULL\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM public.requirement_facts WHERE id = {q(f['id'])}::uuid);")

    out += ["", "COMMIT;"]
    sql = "\n".join(out) + "\n"
    if args.out:
        (args.out if args.out.is_absolute() else REPO / args.out).write_text(sql)
        print(f"wrote {args.out}  ({len(packs)} packs, {len(docs)} docs, {len(entities)} entities, {len(facts)} facts)")
    else:
        print(sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

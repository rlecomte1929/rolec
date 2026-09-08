#!/usr/bin/env python3
"""Build a resources-import bundle from harvested city-services NDJSON.

The Auto/Cursor batch wrote one NDJSON line per city under
`docs/imports/relopass-city-services-2026-08-31/`. ReloPass consumes
`backend/imports/resources/` bundles. This reshapes one into the other.

Rules (same as B3, same reason):
- Derive, never invent. A `source_missing` block is dropped, not filled.
- Every resource names a source the bundle also declares. `country_resources`
  stores `source_id`, not `source_url`; an undeclared citation lands NULL.
- Draft and invisible. Serving is a separate human step.
- Categories used here that production may not have (`schools_childcare`) are
  declared in the bundle, copied from `fixtures/categories.csv`.

Run from the repo root:

    python scripts/gen_city_services_bundles.py
    python scripts/gen_city_services_bundles.py --check
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from urllib.parse import urlsplit

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HARVEST = REPO_ROOT / "docs" / "imports" / "relopass-city-services-2026-08-31"
OUT = REPO_ROOT / "backend" / "imports" / "resources" / "fixtures" / "bundle_city_services_2026_08_31.json"

URL_RE = re.compile(r"https?://[^\s\"<>]+", re.I)

TOPIC_MAP = {
    "housing": ("housing", "Housing"),
    "banking": ("admin_essentials", "Banking"),
    "schools": ("schools_childcare", "Schools"),
    "legal_admin": ("admin_essentials", "Arrival registration"),
    "tax_finance": ("admin_essentials", "Tax ID"),
    "transport": ("transport", "Transport"),
}

CATEGORIES = {
    "admin_essentials": {
        "key": "admin_essentials",
        "label": "Administrative Essentials",
        "description": "Residence registration, tax, ID, bank, mobile",
        "icon_name": "admin",
        "sort_order": 1,
        "is_active": True,
    },
    "housing": {
        "key": "housing",
        "label": "Housing",
        "description": "Guides, neighborhoods, rental platforms",
        "icon_name": "housing",
        "sort_order": 2,
        "is_active": True,
    },
    "schools_childcare": {
        "key": "schools_childcare",
        "label": "Schools & Childcare",
        "description": "Public, international, kindergartens",
        "icon_name": "schools",
        "sort_order": 3,
        "is_active": True,
    },
    "healthcare": {
        "key": "healthcare",
        "label": "Healthcare",
        "description": "Registration, clinics, emergency",
        "icon_name": "healthcare",
        "sort_order": 4,
        "is_active": True,
    },
    "transport": {
        "key": "transport",
        "label": "Transportation",
        "description": "Public transport, apps, driving",
        "icon_name": "transport",
        "sort_order": 5,
        "is_active": True,
    },
}


def _url_ok(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s]+$", url.strip(), re.I))


def _citation_url(value) -> str | None:
    """Otto sometimes stores source_url as a list of pages it opened.

    Take the first https URL. Do not invent one.
    """
    candidates: list[str] = []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = [c for c in value if isinstance(c, str)]
    for raw in candidates:
        url = raw.strip()
        if _url_ok(url):
            return url
    return None


def _first_url(text: str) -> str | None:
    m = URL_RE.search(text or "")
    if not m:
        return None
    url = m.group(0).rstrip(").,;")
    return url if _url_ok(url) else None


def _classify_host(host: str) -> tuple[str, str]:
    """Conservative: government-shaped hosts are official/T0; everything else commercial/T2.

    Publisher names are not invented — the host is the publisher label.
    """
    h = host.lower()
    official_bits = (
        ".gov", ".gouv.", ".gob.", ".go.jp", ".govt.", ".admin.ch",
        ".kommune.", "skatteetaten.", "skat.dk", "borger.dk", "uscis.gov",
        "irs.gov", "ato.gov.", "abf.gov.", "nt.gov.", "vic.gov.",
        "servicesaustralia.gov.", "helsenorge.", "vegvesen.", "sua.no",
    )
    if any(bit in h or h.endswith(bit.rstrip(".")) for bit in official_bits):
        return "official", "T0"
    if h.endswith(".edu") or ".edu." in h:
        return "institutional", "T1"
    return "commercial", "T2"


def _grounded(block: dict | None) -> bool:
    if not isinstance(block, dict):
        return False
    if block.get("source_missing") is True:
        return False
    url = _citation_url(block.get("source_url"))
    summary = block.get("summary")
    if not isinstance(summary, str):
        return False
    return bool(url and summary.strip())


def _slug(path: pathlib.Path) -> str:
    return path.parent.name


def _resource(
    *,
    iso2: str,
    country: str,
    city: str,
    slug: str,
    topic: str,
    category: str,
    label: str,
    body: str,
    source_url: str,
) -> dict:
    return {
        "country_code": iso2,
        "country_name": country,
        "city_name": city,
        "category_key": category,
        "title": f"{city} — {label}",
        "body": body.strip(),
        "resource_type": "guide",
        "audience_type": "all",
        "source_url": source_url,
        "source_name": source_url,
        "status": "draft",
        "is_visible_to_end_users": False,
        "external_key": f"citysvc-20260831-{iso2.lower()}-{slug}-{topic}",
    }


def iter_city_files() -> list[pathlib.Path]:
    return sorted(HARVEST.rglob("city-*.ndjson"))


def _load_ndjson_record(path: pathlib.Path) -> dict:
    raw = path.read_bytes()
    # Otto sometimes stores a stray 0xa2 where the closing quote of tax_id_name
    # should be. Keep harvest files byte-identical; repair only for parse.
    raw = raw.replace(b"(NN/RRN)\xa2,", b'(NN/RRN)",')
    return json.loads(raw.decode("utf-8", errors="replace").strip().splitlines()[0])


def city_to_resources(ndjson_path: pathlib.Path) -> tuple[list[dict], str]:
    rec = _load_ndjson_record(ndjson_path)
    man_path = ndjson_path.parent / ndjson_path.name.replace("city-", "manifest-").replace(
        ".ndjson", ".json"
    )
    retrieved = ""
    if man_path.exists():
        retrieved = (json.loads(man_path.read_text()).get("generated_at") or "").strip()
    iso2 = rec["iso2"].strip().upper()
    country = rec["country"].strip()
    city = rec["city"].strip()
    slug = _slug(ndjson_path)
    services = rec.get("services") or {}
    rows: list[dict] = []
    for topic, (category, label) in TOPIC_MAP.items():
        block = services.get(topic)
        if not _grounded(block):
            continue
        rows.append(_resource(
            iso2=iso2,
            country=country,
            city=city,
            slug=slug,
            topic=topic,
            category=category,
            label=label,
            body=block["summary"],
            source_url=_citation_url(block.get("source_url")) or "",
        ))
        if topic == "transport":
            health = (block.get("healthcare_registration") or "").strip()
            health_url = _first_url(health)
            # Only emit healthcare when the block itself names a URL. Do not
            # reuse the transport citation — that would mis-attribute Helsenorge
            # to Ruter (or equivalent).
            if health and health_url:
                rows.append(_resource(
                    iso2=iso2,
                    country=country,
                    city=city,
                    slug=slug,
                    topic="healthcare",
                    category="healthcare",
                    label="Healthcare registration",
                    body=health,
                    source_url=health_url,
                ))
    return rows, retrieved


def to_sources(resources: list[dict], retrieved_by_url: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for r in resources:
        url = r["source_url"]
        if url in seen:
            continue
        seen.add(url)
        host = (urlsplit(url).hostname or "").lower()
        source_type, trust_tier = _classify_host(host)
        out.append({
            "source_name": url,
            "publisher": host,
            "source_type": source_type,
            "url": url,
            "trust_tier": trust_tier,
            "retrieved_at": retrieved_by_url.get(url) or None,
        })
    return out


def build() -> dict:
    resources: list[dict] = []
    retrieved_by_url: dict[str, str] = {}
    skipped_cities = 0
    for path in iter_city_files():
        rows, retrieved = city_to_resources(path)
        if not rows:
            skipped_cities += 1
            continue
        for r in rows:
            # The city's manifest date is when that page was read. A healthcare
            # URL extracted from transport text still belongs to this city-read.
            if retrieved and r["source_url"] not in retrieved_by_url:
                retrieved_by_url[r["source_url"]] = retrieved
        resources.extend(rows)
    used_cats = sorted({r["category_key"] for r in resources})
    return {
        "categories": [CATEGORIES[k] for k in used_cats],
        "tags": [],
        "sources": to_sources(resources, retrieved_by_url),
        "resources": resources,
        "events": [],
        "_meta": {
            "cities_in_harvest": len(iter_city_files()),
            "cities_with_no_grounded_service": skipped_cities,
            "resource_count": len(resources),
        },
    }


def bundle_for_disk(raw: dict) -> dict:
    return {k: v for k, v in raw.items() if k != "_meta"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    raw = build()
    body = json.dumps(bundle_for_disk(raw), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not OUT.exists() or OUT.read_text() != body:
            print(f"FAIL {OUT.name} missing or stale", flush=True)
            return 1
        print(
            f"OK   {OUT.name} ({raw['_meta']['resource_count']} resources, "
            f"{raw['_meta']['cities_in_harvest']} cities)",
            flush=True,
        )
        return 0
    OUT.write_text(body)
    meta = raw["_meta"]
    print(
        f"wrote {OUT.relative_to(REPO_ROOT)}  {meta['resource_count']} resources "
        f"from {meta['cities_in_harvest']} cities "
        f"({meta['cities_with_no_grounded_service']} cities had nothing grounded)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

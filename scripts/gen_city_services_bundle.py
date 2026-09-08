#!/usr/bin/env python3
"""Build a resource-import bundle from Otto's *nested* per-city "city services" NDJSON.

Otto's 2026-08/09 city-services deliverables are ONE record per city:

    {country, iso2, city, rank, population, services: {
        housing: {summary, rent_1br_center, deposit_months, source_url, source_missing, ...},
        banking, schools, legal_admin, tax_finance, transport: {...}
    }}

This is a different shape from the flat 8-key §3B format `gen_b3_city_bundles.py` handles, so it
gets its own converter. Output is the same bundle `backend/imports/resources/` consumes
(`categories/tags/sources/resources/events`), loaded with
`import_resources.py --bundle <out> --mode draft_only` → `country_resources` (draft, invisible).

Derives, never invents:
  * `body` is the service `summary` verbatim; the structured fields are already narrated in it.
  * A service with `source_missing: true` (or no `source_url`) lands with NO source — no invented
    citation — so its `country_resources.source_id` is left NULL. The `source_missing` flag is honoured.
  * All six service categories map to categories that ALREADY EXIST in production, so nothing new
    is declared. `retrieved_at` is absent from this format, so sources omit it rather than fake a date.

Run from the repo root:
    python scripts/gen_city_services_bundle.py --src-dir docs/imports/<batch>/src --out <batch>/bundle.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from urllib.parse import urlsplit

#: Otto service key -> `resource_categories.key` (all seven exist in production).
CATEGORY_BY_SERVICE = {
    "housing": "housing",
    "banking": "admin_essentials",
    "schools": "schools_childcare",
    "legal_admin": "admin_essentials",
    "tax_finance": "admin_essentials",
    "transport": "transport",
    "healthcare": "healthcare",
    "cost_of_living": "cost_of_living",
}

#: Human label for the resource title, e.g. "Registration & admin — Waterford".
LABEL_BY_SERVICE = {
    "housing": "Housing",
    "banking": "Banking",
    "schools": "Schools & childcare",
    "legal_admin": "Registration & admin",
    "tax_finance": "Tax & finance",
    "transport": "Transport",
    "healthcare": "Healthcare",
    "cost_of_living": "Cost of living",
}

#: Minimal, cautious publisher classification (mirrors gen_b3_city_bundles). Official state hosts
#: get T0/T1; everything else falls to commercial/T2, the honest cautious end. Extend as needed.
OFFICIAL_HINTS = ("gov.ie", "citizensinformation.ie", "revenue.ie", ".gov.", ".gov ", "gov.uk",
                  "europa.eu", "admin.ch", "skatteetaten.no", "borger.dk")


def classify(url: str) -> tuple[str, str, str]:
    host = (urlsplit(url).hostname or "").lower()
    if any(h in host for h in OFFICIAL_HINTS):
        return ("official", "T1", host)
    return ("commercial", "T2", host)


def to_resources_and_sources(rec: dict) -> tuple[list[dict], list[dict]]:
    iso2 = (rec.get("iso2") or "").strip().upper()
    country_name = (rec.get("country") or "").strip()
    city = (rec.get("city") or "").strip()
    resources: list[dict] = []
    sources: dict[str, dict] = {}
    for svc, payload in (rec.get("services") or {}).items():
        if not isinstance(payload, dict):
            continue
        summary = (payload.get("summary") or "").strip()
        if not summary:
            continue  # a service with no narrative is nothing to publish
        category = CATEGORY_BY_SERVICE.get(svc)
        if category is None:
            raise ValueError(f"{city}: no category mapped for service {svc!r}")
        url_raw = payload.get("source_url")
        if isinstance(url_raw, list):  # some gap-fill cities (e.g. AU/wollongong) cite a list
            url_raw = next((u for u in url_raw if u), "")
        url = (url_raw or "").strip() if isinstance(url_raw, str) else ""
        has_src = bool(url) and not payload.get("source_missing")
        res = {
            "country_code": iso2,
            "country_name": country_name,
            "city_name": city,
            "category_key": category,
            "title": f"{LABEL_BY_SERVICE.get(svc, svc.title())} — {city}",
            "body": summary,
            "resource_type": "guide",
            "audience_type": "all",
            "status": "draft",
            "is_visible_to_end_users": False,
            "external_key": f"citysvc-{iso2}-{city}-{svc}".lower().replace(" ", "-"),
        }
        if has_src:
            source_type, trust_tier, host = classify(url)
            res["source_url"] = url
            res["source_name"] = host  # no per-service source_name in this format; host is the stable id
            sources.setdefault(host, {
                "source_name": host,
                "publisher": host,
                "source_type": source_type,
                "url": url,
                "trust_tier": trust_tier,
            })
        resources.append(res)
    return resources, list(sources.values())


def build(src_dir: pathlib.Path) -> dict:
    resources: list[dict] = []
    sources: dict[str, dict] = {}
    for f in sorted(src_dir.glob("*.ndjson")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            r, s = to_resources_and_sources(rec)
            resources.extend(r)
            for src in s:
                sources.setdefault(src["source_name"], src)
    return {"categories": [], "tags": [], "sources": list(sources.values()),
            "resources": resources, "events": []}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-dir", type=pathlib.Path, required=True, help="dir of per-city *.ndjson")
    ap.add_argument("--out", type=pathlib.Path, required=True, help="bundle JSON output path")
    args = ap.parse_args()
    bundle = build(args.src_dir)
    args.out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cats = sorted({r["category_key"] for r in bundle["resources"]})
    print(f"wrote {args.out}  {len(bundle['resources'])} resources, "
          f"{len(bundle['sources'])} sources, categories {cats}")
    no_src = [r["external_key"] for r in bundle["resources"] if "source_url" not in r]
    if no_src:
        print(f"  {len(no_src)} resource(s) with source_missing (source_id will be NULL): {no_src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build resource-import bundles from the B3 city-enrichment artifacts.

B3 (`docs/imports/B3-facts-enrichment.md`) delivered destination content for Stavanger and
Copenhagen as NDJSON with eight keys. `backend/imports/resources/` consumes a bundle, so this
reshapes one into the other.

Derives, never invents. The B3 records carry no coordinates, no district, no budget tier, no
price range and no trust tier, so those columns are left unset rather than filled — the
batch's stated policy is that an absent field stays absent.

`schools_childcare` is DECLARED in the bundle rather than assumed. Production holds only six
resource categories (`admin_essentials`, `housing`, `healthcare`, `daily_life`, `transport`,
`cost_of_living`), and the schools category the fixture CSV defines was never seeded — so a
schools record would fail validation against an unknown category key. Declaring it in the
bundle is what makes the import self-sufficient; the definition is copied from
`backend/imports/resources/fixtures/categories.csv` rather than made up here.

**Sources are declared too, and that is not optional.** `country_resources` stores provenance
as `source_id`, a FK into `resource_sources` — it has no `source_url` column. The executor
resolves that FK by looking the resource's `source_name`/`source_url` up among rows that
ALREADY EXIST, so a bundle that names a source it never declares links to nothing and the row
lands with `source_id NULL`. The first run of this import did exactly that: 13 rows, zero
citations, silently. For a batch whose entire claim is that every record is source-cited, that
is the one failure that matters, and it is invisible unless you go and count.

Run from the repo root:

    python scripts/gen_b3_city_bundles.py            # write both bundles
    python scripts/gen_b3_city_bundles.py --check    # verify the committed bundles match
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from urllib.parse import urlsplit

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "docs" / "imports" / "data" / "B3"
FIXTURES = REPO_ROOT / "backend" / "imports" / "resources" / "fixtures"

#: B3 `topic` -> `resource_categories.key`. Every value is a category that exists in
#: production, except `schools_childcare`, which the bundle declares (see module docstring).
CATEGORY_BY_TOPIC = {
    "neighborhoods": "housing",
    "transport": "transport",
    "schools": "schools_childcare",
    "banking": "admin_essentials",
    "healthcare": "healthcare",
    "cost_of_living": "cost_of_living",
    # "Practicalities" is the batch's catch-all — emergency numbers, seasonal advice, the
    # small operational things. `daily_life` is the closest existing category. This is the
    # one judgement call in the mapping and is called out in the PR rather than buried.
    "practicalities": "daily_life",
}

#: Copied verbatim from `fixtures/categories.csv`, so the declared category matches the one
#: the repo already describes rather than inventing a second definition of the same thing.
SCHOOLS_CATEGORY = {
    "key": "schools_childcare",
    "label": "Schools & Childcare",
    "description": "Public, international, kindergartens",
    "icon_name": "schools",
    "sort_order": 3,
    "is_active": True,
}

#: Publisher classification for the cited pages, against the vocabulary in
#: `schemas.SOURCE_TYPES` / `TRUST_TIERS`. `official` is a state body, `institutional` a
#: public agency, operator or school publishing about itself, `commercial` a business.
#: Keyed by hostname; anything unlisted falls to commercial/T2, which is the cautious end.
SOURCE_CLASS_BY_HOST = {
    # State bodies — the citizen portal and the tax administration.
    "lifeindenmark.borger.dk": ("official", "T0", "Agency for Digital Government (Denmark)"),
    "www.skatteetaten.no": ("official", "T0", "Norwegian Tax Administration"),
    # Operators and institutions: authoritative about their own service, not the state.
    "www.kolumbus.no": ("institutional", "T0", "Kolumbus AS (Rogaland county)"),
    "www.rejsekort.dk": ("institutional", "T0", "Rejsekort & Rejseplan A/S"),
    "www.copenhageninternational.school": ("institutional", "T1", "Copenhagen International School"),
    "www.isstavanger.no": ("institutional", "T1", "International School of Stavanger"),
    "international.au.dk": ("institutional", "T1", "Aarhus University"),
    # Commercial relocation publisher. Kept, but tiered honestly — and note the batch's own
    # honesty note that its Copenhagen areas page returned HTTP 403 and was not relied on.
    "www.expatarrivals.com": ("commercial", "T2", "Expat Arrivals"),
}

CITIES = {
    "city_stavanger.ndjson": ("Stavanger", "NO", "Norway", "bundle_stavanger.json"),
    "city_copenhagen.ndjson": ("Copenhagen", "DK", "Denmark", "bundle_copenhagen.json"),
}


def to_resource(rec: dict, country_name: str) -> dict:
    topic = rec["topic"].strip()
    category = CATEGORY_BY_TOPIC.get(topic)
    if category is None:
        raise ValueError(f"no category mapped for topic {topic!r}")
    return {
        "country_code": rec["country"].strip().upper(),
        "country_name": country_name,
        "city_name": rec["city"].strip(),
        "category_key": category,
        "title": rec["title"].strip(),
        "body": rec["body"].strip(),
        "resource_type": "guide",
        "audience_type": "all",
        "source_url": rec["source_url"].strip(),
        "source_name": rec["source_name"].strip(),
        # Draft and invisible. Promotion to published is a separate human step.
        "status": "draft",
        "is_visible_to_end_users": False,
        # Stable across re-runs, so a second import updates rather than duplicates.
        "external_key": f"b3-{rec['country'].strip().lower()}-"
                        f"{rec['city'].strip().lower()}-{topic}",
    }


def to_sources(rows: list[dict]) -> list[dict]:
    """One `resource_sources` row per distinct cited page.

    Per page, not per publisher: the citation a reviewer needs to re-check is the exact URL
    that was read, and borger.dk alone supplies three different pages here.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for r in rows:
        url = r["source_url"].strip()
        name = r["source_name"].strip()
        if name in seen:
            continue
        seen.add(name)
        host = (urlsplit(url).hostname or "").lower()
        source_type, trust_tier, publisher = SOURCE_CLASS_BY_HOST.get(
            host, ("commercial", "T2", host)
        )
        out.append({
            "source_name": name,
            "publisher": publisher,
            "source_type": source_type,
            "url": url,
            "trust_tier": trust_tier,
            # Verbatim from the artifact — the date the page was actually read.
            "retrieved_at": r["retrieved_at"].strip(),
        })
    return out


def build() -> dict[str, dict]:
    bundles: dict[str, dict] = {}
    for fname, (city, cc, country_name, out_name) in CITIES.items():
        rows = [json.loads(l) for l in (DATA / fname).read_text().splitlines() if l.strip()]
        resources = [to_resource(r, country_name) for r in rows]
        needs_schools = any(r["category_key"] == "schools_childcare" for r in resources)
        bundles[out_name] = {
            "categories": [SCHOOLS_CATEGORY] if needs_schools else [],
            "tags": [],
            # Declared, not assumed — see the module docstring. Without these the resources
            # link to no source and the batch loses the citations that are its whole point.
            "sources": to_sources(rows),
            "resources": resources,
            "events": [],
        }
    return bundles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    ok = True
    for out_name, bundle in build().items():
        path = FIXTURES / out_name
        body = json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"
        if args.check:
            if not path.exists() or path.read_text() != body:
                print(f"FAIL {out_name} missing or stale", file=sys.stderr)
                ok = False
            else:
                print(f"OK   {out_name} ({len(bundle['resources'])} resources)")
        else:
            path.write_text(body)
            cats = {r["category_key"] for r in bundle["resources"]}
            print(f"wrote {path.relative_to(REPO_ROOT)}  "
                  f"{len(bundle['resources'])} resources, categories {sorted(cats)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Pilot seed: Norway / Oslo. Imports categories, tags, sources, resources, events.
Run from project root:
  python scripts/seed_resources_oslo.py

Uses draft_only mode by default. Resources and events are imported as draft.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.imports.resources.executor import execute_bundle
from backend.imports.resources.parsers import (
    parse_csv_categories,
    parse_csv_events,
    parse_csv_resources,
    parse_csv_sources,
    parse_csv_tags,
)
from backend.imports.resources.report import ImportReport
from backend.imports.resources.schemas import ImportBundle
from backend.imports.resources.validators import validate_bundle


def main() -> int:
    fixtures = Path(__file__).resolve().parent.parent / "backend" / "imports" / "resources" / "fixtures"
    if not fixtures.exists():
        print(f"Fixtures not found: {fixtures}")
        return 1

    bundle = ImportBundle(
        categories=parse_csv_categories(fixtures / "categories.csv"),
        tags=parse_csv_tags(fixtures / "tags.csv"),
        sources=parse_csv_sources(fixtures / "sources.csv"),
        resources=parse_csv_resources(fixtures / "oslo_resources.csv"),
        events=parse_csv_events(fixtures / "oslo_events.csv"),
    )

    # Validation
    try:
        from backend.services.supabase_client import get_supabase_admin_client
        supabase = get_supabase_admin_client()
        cat_r = supabase.table("resource_categories").select("key").execute()
        tag_r = supabase.table("resource_tags").select("key").execute()
        cat_keys = {r["key"] for r in (cat_r.data or [])}
        tag_keys = {r["key"] for r in (tag_r.data or [])}
    except Exception:
        cat_keys, tag_keys = set(), set()

    errors = validate_bundle(bundle, cat_keys, tag_keys, mode="draft_only", allow_published=False)
    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  {e['entity_type']} row {e['row_num']}: {e['message']}")
        return 1

    report = execute_bundle(
        bundle,
        user_id=None,
        mode="draft_only",
        allow_published=False,
        file_name="seed_resources_oslo",
    )
    print(report.to_console())
    return 0 if all(r.failed == 0 for r in report.entity_reports) else 1


if __name__ == "__main__":
    sys.exit(main())

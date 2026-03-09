#!/usr/bin/env python3
"""
Resources import CLI. Run from project root:
  python scripts/import_resources.py --bundle backend/imports/resources/fixtures/bundle_oslo.json
  python scripts/import_resources.py --categories backend/imports/resources/fixtures/categories.csv
  python scripts/import_resources.py --tags backend/imports/resources/fixtures/tags.csv
  python scripts/import_resources.py --sources backend/imports/resources/fixtures/sources.csv
  python scripts/import_resources.py --resources backend/imports/resources/fixtures/oslo_resources.csv
  python scripts/import_resources.py --events backend/imports/resources/fixtures/oslo_events.csv

Modes: draft_only (default), preserve_status, allow_published
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root for backend imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.imports.resources.executor import execute_bundle
from backend.imports.resources.parsers import (
    parse_csv_categories,
    parse_csv_events,
    parse_csv_resources,
    parse_csv_sources,
    parse_csv_tags,
    parse_json_bundle,
)
from backend.imports.resources.report import ImportReport
from backend.imports.resources.schemas import ImportBundle
from backend.imports.resources.validators import validate_bundle


def _load_existing_keys():
    """Load existing category/tag keys from DB for validation."""
    from backend.services.supabase_client import get_supabase_admin_client
    supabase = get_supabase_admin_client()
    cat_r = supabase.table("resource_categories").select("key").execute()
    tag_r = supabase.table("resource_tags").select("key").execute()
    return (
        {r["key"] for r in (cat_r.data or [])},
        {r["key"] for r in (tag_r.data or [])},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Resources (categories, tags, sources, resources, events)")
    parser.add_argument("--bundle", type=Path, help="JSON bundle path")
    parser.add_argument("--categories", type=Path, help="Categories CSV")
    parser.add_argument("--tags", type=Path, help="Tags CSV")
    parser.add_argument("--sources", type=Path, help="Sources CSV")
    parser.add_argument("--resources", type=Path, help="Resources CSV")
    parser.add_argument("--events", type=Path, help="Events CSV")
    parser.add_argument("--mode", choices=["draft_only", "preserve_status", "allow_published"], default="draft_only")
    parser.add_argument("--allow-published", action="store_true", help="Allow published status (only with allow_published mode)")
    parser.add_argument("--output", type=Path, help="Write JSON report to file")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, do not import")
    args = parser.parse_args()

    bundle = ImportBundle()
    file_name = ""

    if args.bundle:
        bundle = parse_json_bundle(args.bundle)
        file_name = str(args.bundle)
    else:
        if args.categories:
            bundle.categories = parse_csv_categories(args.categories)
            file_name = file_name or str(args.categories)
        if args.tags:
            bundle.tags = parse_csv_tags(args.tags)
            file_name = file_name or str(args.tags)
        if args.sources:
            bundle.sources = parse_csv_sources(args.sources)
            file_name = file_name or str(args.sources)
        if args.resources:
            bundle.resources = parse_csv_resources(args.resources)
            file_name = file_name or str(args.resources)
        if args.events:
            bundle.events = parse_csv_events(args.events)
            file_name = file_name or str(args.events)

    if not any([bundle.categories, bundle.tags, bundle.sources, bundle.resources, bundle.events]):
        print("No input specified. Use --bundle or individual --categories/--tags/--sources/--resources/--events")
        return 1

    # Validation
    try:
        cat_keys, tag_keys = _load_existing_keys()
    except Exception as e:
        print(f"Warning: could not load existing keys: {e}. Using empty sets.")
        cat_keys, tag_keys = set(), set()

    errors = validate_bundle(
        bundle,
        existing_category_keys=cat_keys,
        existing_tag_keys=tag_keys,
        mode=args.mode,
        allow_published=args.allow_published,
    )
    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  {e['entity_type']} row {e['row_num']} [{e['field']}]: {e['message']}")
        if not args.validate_only:
            return 1

    if args.validate_only:
        print("Validation passed. Use without --validate-only to import.")
        return 0

    # Execute
    report = execute_bundle(
        bundle,
        user_id=None,
        mode=args.mode,
        allow_published=args.allow_published,
        file_name=file_name,
    )

    print(report.to_console())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report.write_json(args.output)
        print(f"Report written to {args.output}")

    return 0 if report.entity_reports and all(r.failed == 0 for r in report.entity_reports) else 1


if __name__ == "__main__":
    sys.exit(main())

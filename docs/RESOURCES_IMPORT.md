# Resources Import Pipeline

Import and seed tooling for the ReloPass Resources module (categories, tags, sources, country resources, events).

## Overview

- **Admin-only**: Imports mutate data; only admin-controlled processes should run them.
- **CSV and JSON**: Supports both formats.
- **Idempotent**: Repeated imports upsert by natural key; no uncontrolled duplicates.
- **Workflow-aware**: Default `draft_only` mode imports as draft; `allow_published` enables published imports.

## Supported Entity Types

| Entity    | Idempotency Key      | Required Fields                           |
|-----------|----------------------|-------------------------------------------|
| Categories| `key`                | key, label                                |
| Tags      | `key`                | key, label                                |
| Sources   | `source_name`        | source_name                               |
| Resources | external_key or (country_code, city_name, category_id, title) | country_code, category_key, title |
| Events    | external_key or (country_code, city_name, title, start_datetime) | country_code, city_name, title, start_datetime, event_type |

## File Formats

### Categories CSV
```
key,label,description,icon_name,sort_order,is_active
admin_essentials,Administrative Essentials,Description,admin,1,true
```

### Tags CSV
```
key,label,tag_group
family_friendly,Family-friendly,family_type
```

### Sources CSV
```
source_name,publisher,source_type,url,trust_tier
Skatteetaten,Norwegian Tax Administration,official,https://...,T0
```

### Resources CSV
Required: `country_code`, `category_key`, `title`. Optional: summary, body, resource_type, audience_type, tags (comma/pipe/JSON array), external_url, etc.

### Events CSV
Required: `country_code`, `city_name`, `title`, `start_datetime`, `event_type`. Optional: end_datetime, venue_name, price_text, is_free, etc.

### JSON Bundle
```json
{
  "categories": [...],
  "tags": [...],
  "sources": [...],
  "resources": [...],
  "events": [...]
}
```

## Import Order

The pipeline executes in dependency order:
1. Categories
2. Tags
3. Sources
4. Resources (with tag mappings)
5. Events (with tag mappings)

## Modes

| Mode             | New records | Existing records | Published import |
|------------------|-------------|------------------|------------------|
| `draft_only`     | draft       | update content   | not allowed      |
| `preserve_status`| draft       | preserve status  | if --allow-published |
| `allow_published`| from file   | from file        | if --allow-published |

## CLI Usage

From project root:

```bash
# Import full bundle
python scripts/import_resources.py --bundle backend/imports/resources/fixtures/bundle_oslo.json

# Import individual files
python scripts/import_resources.py --categories backend/imports/resources/fixtures/categories.csv
python scripts/import_resources.py --tags backend/imports/resources/fixtures/tags.csv
python scripts/import_resources.py --sources backend/imports/resources/fixtures/sources.csv
python scripts/import_resources.py --resources backend/imports/resources/fixtures/oslo_resources.csv
python scripts/import_resources.py --events backend/imports/resources/fixtures/oslo_events.csv

# With options
python scripts/import_resources.py --bundle bundle.json --mode preserve_status --allow-published
python scripts/import_resources.py --bundle bundle.json --output report.json
python scripts/import_resources.py --bundle bundle.json --validate-only
```

## Pilot Seed

```bash
python scripts/seed_resources_oslo.py
```

Imports Norway/Oslo pilot data (categories, tags, sources, ~16 resources, ~7 events) as draft.

## Environment

- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (or equivalent) for DB access.
- Backend uses `get_supabase_admin_client()` for admin-level writes.

## Assumptions

- Categories/tags/sources use `key` or `source_name` as unique constraint.
- Resources and events use `external_key` when provided; otherwise natural key lookup.
- Tag references in resources/events are by tag `key`; resolution happens at execution.
- Source references use `source_url` (preferred) or `source_name`.

## Next Steps

1. Admin upload/import UI
2. Import run history and error review UI
3. Crawler/extraction pipeline integration
4. Diff/review mode before publishing

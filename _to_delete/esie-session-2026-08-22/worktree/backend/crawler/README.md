# Crawler & Extraction Pipeline

Ingestion pipeline for trusted relocation content. Fetches from configured sources, parses, chunks, extracts candidates, and writes to **staging tables**. No direct publish — admin review required before content reaches live resources.

## Architecture

```
Trusted source → fetch → raw snapshot → parse → chunk → extract → dedupe → staging tables
                                                                              ↓
                                                                    admin review
                                                                              ↓
                                                                    publish workflow
```

## Pipeline Stages

1. **Source registry** — JSON config (`config/fixtures/sources_oslo_pilot.json`)
2. **Fetch** — HTTP with retry, timeout, content hashing
3. **Parse** — BeautifulSoup; extract title, main text, headings, links
4. **Chunk** — Size-based segmentation with heading context
5. **Extract** — Rule-based resource/event candidates
6. **Dedupe** — Against staged and live tables
7. **Stage** — Write to `staged_resource_candidates`, `staged_event_candidates`

## Staging Tables

- `crawl_runs` — Run metadata
- `crawled_source_documents` — Fetched pages
- `crawled_source_chunks` — Chunked units
- `staged_resource_candidates` — Extracted resources (status: new, needs_review, etc.)
- `staged_event_candidates` — Extracted events

## CLI

```bash
# Dry run (no DB writes)
python scripts/crawl_resources.py --dry-run

# Crawl Norway/Oslo (requires Supabase)
python scripts/crawl_resources.py --country NO --city Oslo

# Single source
python scripts/crawl_resources.py --source oslo_kommune_newcomer

# Custom config
python scripts/crawl_resources.py --config path/to/sources.json
```

## Requirements

- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for staging writes
- Run `supabase db push` or apply migration `20260309000000_crawler_staging_tables.sql`

## Pilot (Norway/Oslo)

Fixture sources:

- `oslo_kommune_newcomer` — Oslo city newcomer guidance
- `ruter_transport` — Oslo public transport
- `visitoslo_events` — Oslo tourism/events

## Next Steps

1. Admin staging review UI
2. Approve/merge-to-live workflow
3. Scheduled re-crawl jobs
4. Optional LLM extraction layer for complex pages

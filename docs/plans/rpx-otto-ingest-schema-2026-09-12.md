# Otto ingest schema + resilient extract fetch

> Cursor-side follow-up to the CS50 lecture JSON (`RLP-PY-*`). Do not implement a parallel `lib/` stack. Do not write facts to WorkspaceDB.

**Goal:** Keep the existing Otto → `otto_staging` → `requirement_items` pipeline, add typed ingest validation in place, and stop the LLM extractor from aborting a run on a government 403.

**Architecture:** `scripts/import_otto_facts.py` stays the only CLI (`dry-run` / `--apply` / `--promote`). Pydantic validates JSONL records before `FactRow` is built. The immigration seed fetcher already returns `FetchedDoc` without raising; the LLM extractor reuses that HTML fetch, then still parses with `immigration_page_parser` (markdown), so AIQ-1821 is not undone.

**Tech stack:** Python 3.11, Pydantic 2.5, existing `requests` fetcher, pytest.

**Spec:** this file. Lecture pack mapping is in the “Archive” section below.

## Global constraints

- Facts the product serves live in Supabase `public.requirement_items`, never Audos WorkspaceDB.
- No `lawyer_signed` field. Review uses `accuracy_tier` / `review_status`; promote lands `pending`, never `expert_verified`.
- `source_url` is a string, not `HttpUrl` — some live citations are `source_records` UUIDs.
- Serving engines must not import this path. Extractor remains authoring-only.
- No new `lib/`, `scripts/corridor_tool.py`, or second archive tree.

---

## Archive: lecture IDs → existing code (do not re-ticket)

| Lecture | Status | Real home |
|---|---|---|
| RLP-PY-01 parser pipeline | Done | `backend/imports/otto/parsers.py` + `executor.py` |
| RLP-PY-02 Pydantic schema | This PR | `FactIngestRecord` in `parsers.py` (Otto JSONL fields only) |
| RLP-PY-03 httpx FetchResult | Partial → this PR | Seed: `immigration/fetcher.py` `FetchedDoc`. Extractor: reuse `fetch_html`, do not `raise_for_status` |
| RLP-PY-04 dict knowledge graph | Research only | Audos / Otto 5-pass. Not a repo module |
| RLP-PY-05 dry-run / apply / promote | Done | `scripts/import_otto_facts.py` |
| RLP-PY-06 per-fact isolation | Done | `FactRowError` vs unofficial rejection list |
| RLP-PY-07 Counter dashboard | Skip | `coverage_service.py`; no CLAUDE.md dump |
| RLP-PY-08 pathlib manifest | Done | `docs/imports/<batch>/manifest.json`, `corridor_harness.py` |

**Tool split after this PR:** more corridor facts → Audos. Landing JSONL and promoting → this Cursor / Claude Code. Title judgment at promote → Otto-delegated Cursor (no SQL). Prod verify → Cowork.

---

## Files

- `docs/plans/rpx-otto-ingest-schema-2026-09-12.md` — this plan (RPX-01)
- `backend/imports/otto/parsers.py` — `FactIngestRecord` at ingest (RPX-02)
- `backend/tests/test_otto_fact_ingest.py` — ingest schema tests
- `backend/imports/immigration/fetcher.py` — `HtmlFetch` + `fetch_html` (never raises)
- `backend/tests/test_immigration_html_fetch.py` — 403 / timeout never raise
- `backend/app/services/requirement_fact_extractor.py` — fetch via `fetch_html`; skip LLM on empty body
- `backend/tests/services/test_requirement_fact_extractor.py` — 403 does not call the LLM

## Out of scope

- Makefile corridor targets
- PostHog coverage events
- In-memory Ziegler graph
- Any migration

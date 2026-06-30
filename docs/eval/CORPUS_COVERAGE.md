# Immigration corpus coverage

**What this is:** a launch-readiness map of which relocation corridors render a
**real, corridor-specific roadmap** (grounded in authoritative immigration rules)
versus which fall back to a **generic deterministic seed**. It exists so we know
exactly where authoritative content is still missing — and so we never ship fake
legal guidance to fill the gap.

> **Provenance rule (hard):** we do **not** fabricate or seed synthetic
> immigration rules into the live corpus. An uncovered corridor is reported
> honestly as "generic seed (needs content)" and is fixed only by sourcing
> **authoritative** rules (Tier-1 government sources). See the checklist below.

## Why the gap exists

The roadmap pipeline is corridor-scoped:

```
POST submit
  → case_roadmap_profile.generate_ai_roadmap_for_case
  → rag_pipeline.generate_roadmap
  → immigration_retriever.retrieve_for_profile(...)   # corridor-scoped retrieval
```

`retrieve_for_profile` queries `immigration_corpus_chunks` filtered by corridor
(`FR_NO`, `US_FR`, …). The behaviour splits on whether that corridor has chunks:

| Retrieval result | Generator | Employee sees |
| --- | --- | --- |
| ≥1 corridor chunk | grounded roadmap | **corridor-specific** steps, cited to real sources |
| empty (no chunks) | `RULE_NOT_FOUND` | **generic deterministic seed** — populated, but not authoritative |

The seed is intentionally fail-safe (the page is never blank), but it is *not*
corridor-specific legal guidance. The covered/uncovered split is therefore the
single most important readiness signal for the immigration feature.

## The report

`backend/scripts/report_corpus_coverage.py` is a **read-only diagnostic**. It
never writes to the corpus and never invents content.

```bash
# Auto: DB mode if DATABASE_URL is set, else offline over the committed corpus.
python backend/scripts/report_corpus_coverage.py

# Force offline (CI-safe, no DB), machine-readable:
python backend/scripts/report_corpus_coverage.py --offline --json
```

It always writes a dated pair `audit/corpus_coverage_<YYYYMMDD>.{md,json}`.

**Two modes:**

- **DB mode** (`DATABASE_URL` set) — one grouped `SELECT` over the live
  `immigration_corpus_chunks` table. This is the authoritative answer: it
  reflects exactly what the prod retriever can surface.
- **Offline mode** (no DB / `--offline`) — a proxy over the **committed corpus
  JSON** (`corpus/*_corridor.json` plus the eval fixtures), run through the
  indexer's own `build_chunks`. It answers "which corridors have authored corpus
  content in the repo", which is the in-repo precursor to a DB-covered corridor.
  Offline is what runs in CI.

**Corridor universe** = the union of (a) the configured corridor registry
(`corridors/<id>/corridor.yaml`) and (b) every corridor that has corpus content
(DB rows in DB mode; corpus files in offline mode). A corridor that is in the
registry but has **no** corpus content is the headline gap — configured, but
served by the generic seed.

## Current coverage (offline, 2026-06-30)

8 covered / 6 generic-seed of 14 known corridors.

**Covered (corridor-specific roadmap):** `BR_PT`, `CA_DE`, `FR_NO`, `IN_DE`,
`UK_DE`, `UK_FR`, `US_FR`, `US_NL`.

**Generic seed — needs authoritative content (priority list):**

| Corridor | Configured (registry) | Status |
| --- | :---: | --- |
| `DE_NO` | yes | generic seed — no corpus content |
| `ES_NL` | yes | generic seed — no corpus content |
| `FR_CH` | yes | generic seed — no corpus content |
| `FR_DE` | yes | generic seed — no corpus content |
| `FR_ES` | yes | generic seed — no corpus content |
| `FR_NL` | yes | generic seed — no corpus content |

These six corridors are configured in the corridor registry (the product is set
up to handle them) but have no immigration corpus, so they currently render the
generic seed. They are the priority targets for sourcing authoritative rules.

Re-run the report after any ingestion to refresh these numbers; the offline view
is a proxy, and **DB mode is authoritative** for what prod actually serves.

## Ingestion path — how a corridor becomes covered

The live retriever-feeding table `immigration_corpus_chunks` is populated by the
**Immigration corpus indexer** GitHub Actions workflow
(`.github/workflows/immigration-indexer.yml`, `workflow_dispatch`):

```
crawled_immigration_documents   (authoritative source pages, crawled + extracted)
  → backend/app/services/immigration_chunk_indexer   (chunk + embed)
  → immigration_corpus_chunks                         (what the retriever reads)
```

The workflow runs with the prod `OPENAI_API_KEY` (embeddings must match the
retriever's model — `text-embedding-3-small`, 1536-dim) and `DATABASE_URL` as
repo secrets. It is idempotent. See `docs/runbooks/immigration-rag-landing.md`
for the full land + verify sequence.

Authored corridor source content lives in-repo at:
- `corpus/<from>_<to>_corridor.json` — curated corridor corpus (schema 1.0.0).
- `corridors/<ID>/corridor.yaml` — corridor registry (retrieval scope, prompt,
  intake, SLA config).

## Checklist — adding a corridor's real rules

> No synthetic content. Every step below sources **authoritative** rules.

1. **Identify Tier-1 sources** — the destination country's official immigration
   / labour-migration authority pages for each relevant pathway (work permit,
   EU/EEA free movement, family reunification, etc.). Record exact URLs.
2. **Crawl the sources** into `crawled_immigration_documents` for the corridor
   (`immigration_crawl_job --corridor <KEY>`; it respects robots.txt and the
   per-source `crawl_interval_days`). Confirm `extracted_text` is populated and
   `crawl_error IS NULL`.
3. **(Optional) author the curated corpus JSON** at
   `corpus/<from>_<to>_corridor.json` (schema 1.0.0) if the corridor needs a
   hand-structured corpus in addition to the crawl, and add a
   `corridors/<ID>/corridor.yaml` entry for retrieval scope.
4. **Index** — run the Immigration corpus indexer workflow with the corridor
   key (`workflow_dispatch` → `corridor: <KEY>`), or
   `python -m backend.app.services.immigration_chunk_indexer --corridor <KEY>`
   in an environment with `OPENAI_API_KEY` + `DATABASE_URL`. Idempotent.
5. **Verify in DB**:
   ```sql
   SELECT corridor, count(*) FROM immigration_corpus_chunks
   WHERE is_active GROUP BY corridor;   -- the corridor should now be > 0
   ```
6. **Verify retrieval** — `POST /api/immigration/retrieve` for a profile in that
   corridor should return non-empty chunks (`corpus_empty=false`).
7. **Re-run this report** (DB mode) and confirm the corridor flips to
   `covered (corridor-specific roadmap)`.

## Related

- `backend/scripts/report_corpus_coverage.py` — the report.
- `backend/tests/test_corpus_coverage_report.py` — its tests.
- `backend/app/services/immigration_retriever.py` — corridor-scoped retrieval.
- `docs/runbooks/immigration-rag-landing.md` — RAG land + prod-ops runbook.

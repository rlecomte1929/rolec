# IE EU/EEA free-mover requirement facts (candidate batch)

**Batch:** `ie-eu-eea-freemover-2026-08-22` · **Records:** 11 · **Corridor:** any EU/EEA national → Ireland
**Source:** Otto/Cursor Audos bridge run #1 · **AIQ-2028** (load as candidates)

Covers the free-mover settle-in set that Ireland's THIRD_COUNTRY permit track does not:
entry with no visa/work-permit, residence with no immigration registration, entry documents,
retained-worker status, single-state social security (Reg 883/2004), and PPSN/bank
proof-of-address. Flat schema, `applies_to.nationality=EEA`, `applies_to.status=professional`.

This is **not** the Andrea / CSEP (Venezuela) track. Do not upsert over the six live
IRELAND EU/EEA payroll titles (PPSN, PRSI, USC, income tax, health, A1-from-Spain).

## Facts

| topic | facts |
|---|---|
| `ie-eu-eea-entry-rights` | no visa required; no work permit required |
| `ie-eu-eea-residence-registration` | not required for EEA nationals |
| `ie-eu-eea-entry-documents` | valid passport or national ID; expired not valid |
| `ie-eu-eea-retained-worker-status` | after one year; under one year |
| `ie-eu-eea-social-security` | single-state rule; posted-worker exception |
| `ie-eu-eea-proof-of-address` | PPSN proof of address; bank proof of address (flagged) |

## Verdict (see `VERIFICATION-2026-08-30.md`)

Schema (V0–V2): **PASS**, 11/11 structurally importable. Evidence (V3): **10/11** quotes
verbatim-verified after grounding; `ie-eu-eea-bank-account-proof-of-address-required` still
needs a cleaner source. Measured 2026-09-12: the public ES→IE EU_EEA employment response
already includes these entity titles (entry rights, residence registration, entry documents,
retained-worker status). Staging again is idempotent; do **not** `--promote` over approved
rows.

## Load contract

`review_status='pending'` on any *new* `requirement_items` row; never `approved`/`verified`.
The importer is destination-only (`country_code=IRELAND`).

```bash
# dry-run (default). Batch id resolves to this directory's facts.ndjson.
./.venv311/bin/python scripts/import_otto_facts.py ie-eu-eea-freemover-2026-08-22 --expected 11

# stage into otto_staging only
./.venv311/bin/python scripts/import_otto_facts.py ie-eu-eea-freemover-2026-08-22 --apply --expected 11
```

`--promote` is a separate human gate. The bank-proof fact stays `needs_lawyer_review`.
`batch_id` is the directory name, not the file stem `facts`.

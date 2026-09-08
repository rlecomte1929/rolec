# Otto vendor candidates — 2026-09-08 harvest

Full inventory reference: [`docs/imports/OTTO_BACKLOG.md`](../OTTO_BACKLOG.md) §A2.

## What this is

The six Otto "flywheel" vendor-candidate batches, fetched from GCS (public-read, permanent),
verified, converted to the import CSV, and measured against the tier gate. **Nothing here has
been written to the database.** The import is held on a founder decision (below).

| Batch | Cities | Records |
|---|---|---|
| B1 | Paris / Oslo | 44 |
| B2 | Madrid / Dublin | 43 |
| B3 | Stavanger / Aberdeen | 45 |
| B4 | Stockholm / Copenhagen | 42 |
| B5 | Helsinki / Berlin | 36 |
| A2a | Frankfurt / Milan (clean only) | 40 |
| **Total** | | **250** |

All counts reconcile exactly against Otto's own per-batch manifests (`verify_batch.py`).

## The finding — 15 of 250 pass, 235 reject (measured, not estimated)

Running the repo's **own** `vendor_harvester.validate()` over every converted row:

- **15 pass** (6%) — cite a genuine registry per-entity page (11 FIDI FAIM movers, 2 IBO
  schools, 1 Finanstilsynet NO estate-agency register, 1 EuRA). See
  [`passing_set.md`](passing_set.md).
- **235 reject** (94%) — **every one** for the same reason: `source_url` is the vendor's own
  site or an aggregator (Wikipedia ×7, northdata ×5, moverdb, easymilano, mumabroad, expat.com,
  paginegialle, plus each firm's own domain), which is **SELF_DECLARED tier-3** and never
  sufficient on its own. See [`rejects_worklist.md`](rejects_worklist.md).

This is the tier gate doing exactly its job — the moat is provenance, and a row backed only by
its own marketing page cannot answer an HR buyer's "where did this supplier come from?". The
235 are **not junk**: they are real vendor identities that need re-sourcing to a register, which
is what the worklist is for. Note A2a's manifest claims "source_url on a different domain from
website", and it is — but that different domain is `northdata.com` (a commercial company-data
aggregator) and Wikipedia, neither of which is a statutory/professional register, so A2a rejects
too. The `_DOMAIN_TO_SOURCE` allowlist is hosts of registers on purpose.

## The decision (founder) — DECIDED 2026-09-08: **Option B**

**Founder chose to route everything back to Otto first — stage nothing yet.** All cities go
back to Otto with a corrected "cite the register, not your own site" instruction, then the
re-sourced batch imports in one pass. The precise per-city × category register targets (with
the exact URL shape the gate requires) are in
[`otto_resourcing_brief.md`](otto_resourcing_brief.md): **53 pairs are harvestable now**, **17
are registry-gaps** (no register wired for that country/category — needs a `registry_sources.py`
entry added first, a ReloPass code task, not Otto), and **2 are unharvestable** (register known
but login-gated / no public search). Otto is scoped to the 53 harvestable pairs only.

The options as originally framed (this is a product quality-bar call, not the applier's to make):

- **(A) Import the 15 registry-evidenced rows now.** Honest and shippable today; small.
  `land_vendor_candidates.py vendor_candidates_all.csv --apply` stages exactly those 15
  (rejections are never staged); add `--promote` to put them in `/admin/vetting-queue`.
- **(B) Route the 235 back to Otto for registry evidence.** Re-run these cities with "cite the
  register's per-entity URL (or the register + licence/roll number for a permalink-less
  statutory register), not the provider's own site". Highest value; needs an Otto round-trip
  (blocked on activating an Audos session). `rejects_worklist.md` is the ready worklist.
- **(C) Reconsider the tier gate.** *Not recommended.* CLAUDE.md and the module docstrings are
  explicit that tier-3 is never sufficient and that this is the enterprise-trust story. The
  sanctioned relaxation (PUBLIC_REGISTER tier-2 for permalink-less statutory registers) already
  exists and is reached through (B), not by weakening the gate.

**Applier recommendation: A now + B for the rest.** A ships 15 verified suppliers behind the
human gate and loses nothing; B turns the 235 into a corrected re-research pass. C is off the
table unless the founder explicitly changes the quality bar.

## Pipeline (how to run it once decided)

```bash
PY=.venv311/bin/python

# 1. (already done) fetch GCS -> src/, convert -> vendor_candidates_all.csv
$PY scripts/convert_vendor_ndjson_to_csv.py \
    docs/imports/vendor-candidates-2026-09-08/vendor_candidates_all.csv \
    docs/imports/vendor-candidates-2026-09-08/src/*_combined.ndjson \
    docs/imports/vendor-candidates-2026-09-08/src/a2a_*_clean.ndjson

# 2. batch gate (hashes + counts + tier split)
$PY docs/imports/vendor-candidates-2026-09-08/verify_batch.py

# 3. OPTION A — stage the 15 to vendor_candidates (pending), then scoped-promote
#    to the vetting queue. NEVER the bare import_supplier_candidates.py --promote
#    (that promotes every abandoned row in the table — unscoped landmine).
$PY scripts/land_vendor_candidates.py \
    docs/imports/vendor-candidates-2026-09-08/vendor_candidates_all.csv \
    --apply --promote \
    --worklist docs/imports/vendor-candidates-2026-09-08/rejects_worklist.md
```

Guardrails: candidate/pending only; the approve-to-serve gate is the human at
`/admin/vetting-queue` (`marketplace` and `test_drive` filter on `'approved'`). Staging is
idempotent on the dedupe key; scoped promote never reaches beyond the runs it just staged.

## Files

- `src/` — the 13 fetched GCS artifacts (7 NDJSON + 6 manifests), hash-pinned in `manifest.json`.
- `vendor_candidates_all.csv` — 250 rows in `EXPECTED_HEADER` shape (converter output).
- `passing_set.md` / `rejects_worklist.md` — the 15 / 235 split, reproducible from `validate()`.
- `manifest.json` — per-file sha256 + count reconciliation + the tier-gate result.
- `verify_batch.py` — the gate that re-checks all of the above.

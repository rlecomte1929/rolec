# ie-isd-visa-required-source-2026-08-22 — ISD-sourced visa-required map

**Landed by Claude Code, 2026-08-22.** Otto-researched, ISD-sourced. Reference data only.

> **`target_table` is deliberately NULL.** This is not requirement-fact data and must never be
> promoted into `public.requirement_items`. It is a lookup table.

## Why this exists alongside `ie-isd-visa-required-2026-08-22`

The in-repo batch `docs/imports/ie-isd-visa-required-2026-08-22/` (commit `3bd79083`,
AIQ-2027 dependency A3) was transcribed from **Citizens Information**, and its own manifest
says why, and what it needed next:

> "ISD (irishimmigration.ie) publishes the same list through a JavaScript table (Ninja Tables
> id 19077) that does not survive HTML fetching, which is why the readable source was used.
> **Corroborate against ISD before this is treated as anything better than representative.**"

**This batch is that corroboration.** Otto reached the Ninja Tables AJAX endpoint directly
(`admin-ajax.php?...table_id=19077`) and captured the authoritative ISD table — the source the
earlier batch could not fetch. It is the Department of Justice's own instrument; Citizens
Information is the Citizens Information Board's public-facing restatement of it.

The two are **not competing datasets.** This one is the authoritative source; the other is the
shipped lookup that a service and tests are already bound to. They are kept separate so the
corroboration is auditable and the shipped lookup is not destabilised by a schema swap.

## Corroboration result — 0 disagreements across 199 determinations

The shipped lookup's own logic (`backend/app/services/isd_visa_required.py`: the 45-entry
`visa_free_nationalities` allowlist, plus the hardcoded `_EEA_UK_CH` frozenset, closed-world
otherwise) was replayed against all **199** ISO-mapped ISD determinations in this batch:

| check | result |
|---|---|
| ISD determinations compared | **199** |
| shipped answer ≠ ISD answer | **0** |
| committed says visa-free, ISD says visa-required | **0** |
| committed visa-free ISO absent from ISD map | **0** |
| ISD visa-free omitted by committed allowlist | 31 — **all** EU/EEA/CH, covered by the `eea_uk_swiss_citizen` structural exemption, not a gap |

The shipped lookup answers identically to ISD for every nationality ISD maps. The weaker
source did not produce a weaker answer. `VE` (Andrea's nationality) = visa-**required** in
both.

## What this batch adds that the shipped lookup does not carry

- **Both directions enumerated** — 123 visa-required + 76 visa-free, rather than a 45-entry
  allowlist with a closed-world assumption. The closed world happens to be correct today; it
  is not self-evidencing, and this file is what evidences it.
- **The 7 non-ISO rows** as structured records rather than prose notes: five British passport
  classes (Dependent Citizen / National (overseas) / Overseas citizen / **Protected Person —
  the one that IS visa-required** / Subject), the Hong Kong Document of Identity, and
  Refugee-or-Stateless.
- **A time-limited determination, correctly refused an expiry.** The Refugee-or-Stateless row
  carries `determination_is_temporary: true` and a `temporary_provision` object recording
  ISD's exact wording ("As of 12 noon on 19 July … for a period of 12 months"),
  `effective_year_stated_on_page: false` and `expiry_determinable_from_source: false`. ISD
  names a day and a month but **no year**; the linked Department of Justice release (14 July
  2023) records the suspension as introduced July 2022 and renewed on rolling 12-month review.
  An expiry was **not** inferred. This is the correct handling and the reason the row is not
  persisted as a standing rule.

## Batch id

Otto authored this as `ie-isd-visa-required-2026-08-22`. It was renamed to
`ie-isd-visa-required-source-2026-08-22` on landing, because that directory name is already
held by the Citizens-Information-sourced lookup this batch corroborates (`3bd79083`), and
the CI delivery gate requires `manifest.batch_id` to equal the directory name.

`isd_visa_required_map.json` keeps Otto's original `dataset_id` unchanged — it is covered by
the manifest's sha256 and was not touched. `manifest.corroborates_batch_id` records the link.

## Provenance and integrity

- Source: `https://www.irishimmigration.ie/visa-non-visa-required-nationalities/`
  (table via Ninja Tables endpoint, id 19077). Page `last updated: March 14, 2025`.
- `retrieved_at` 2026-08-21T21:50:02Z · `schema_version` 1.1 · `revision` 2
- Re-verified 2026-08-22T07:19:17Z — result **unchanged** (suspension notice still present,
  refugee row still "Yes", 206 rows, still no year and no end date published).
- No `gov.ie` URL appears in the data; the irishimmigration.ie-only rule holds.

Gate: `python3 docs/imports/ie-isd-visa-required-source-2026-08-22/gate.py`

| gate check | result |
|---|---|
| sha256 + byte length, both declared files | PASS |
| `isd_rows_total` 206 = mapped 199 + unmapped 7 | PASS |
| `entries_mapped_to_iso2` 199 | PASS |
| `visa_required_true` 123 / `visa_required_false` 76 | PASS |
| every determination is a real bool | PASS |

## Open items (not decided here)

1. **Whether the service re-points at this artifact.** It would replace a correct-by-luck
   closed world with an enumerated one and pick up the 7 travel-document classes. That is a
   change to `backend/app/services/isd_visa_required.py` and its tests, which belong to the
   AIQ-2027 branch — not to this docs-only batch.
2. **Scheduled re-verification.** The manifest's `monitoring` block records Audos scheduler
   registration as *blocked*. See the branch discussion; a GitHub Actions cron in this repo is
   the cheaper route.

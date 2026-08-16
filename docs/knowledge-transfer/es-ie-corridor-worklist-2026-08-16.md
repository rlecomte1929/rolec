# ES→IE corridor — state, cleanup log, and research worklist

Prepared 2026-08-16. Supersedes the brief's reference to
`stage0-es-ie-no-fr-evaluation-2026-08-16.md`, **which does not exist** in the working tree or
anywhere in git history. The only file in this directory is `frno-integration-evaluation-2026-08-15.md`,
and that itself lives only in unpushed local commit `564261a9`.

## 1. Where the Ireland content actually lives

The brief measured the wrong table. `import_otto_facts.py --promote` builds `requirement_items`
from `_PROMOTABLE` (`backend/imports/otto/executor.py:313-326`), which reads **`otto_staging`**
and never reads `public.requirement_entities` / `public.requirement_facts`:

| table | IE rows (2026-08-16) |
|---|---|
| `public.requirement_entities` | 34 |
| `public.requirement_facts` | 130 |
| `otto_staging.immigration_entities` | 14 |
| `otto_staging.immigration_fact_candidates` (`status='ready'`) | 14 → **9 after cleanup** |

So the promotable set was never 34.

## 2. Cleanup applied (2026-08-16)

`otto_staging` held **two IE batches** that had collided under different key conventions:

| batch | keys | facts | first seen |
|---|---|--:|---|
| `IE-immig-test-2026-08-12` | snake_case | 6 | 06:00:10 |
| `IE-persona-immig-2026-08-12` | kebab-case | 8 | 09:35:29 |

Five test-batch rows duplicated a later persona row and were set `status='superseded'`
(**not deleted** — the rows are intact and recoverable; `_PROMOTABLE` filters on `'ready'`).
`csep_eligibility` was **kept**: it is not a duplicate.

| superseded key | superseded by | why |
|---|---|---|
| `csep_application_fee` | `csep-application-fee` + `gep-application-fee` | test row conflated CSEP and GEP fees into one fact; persona splits them correctly, same source |
| `gep_labour_market_test` | `gep-lmnt` | persona names EURES + 28 consecutive days, cites the dedicated LMNT page |
| `csep_salary_threshold` | `csep-salary-threshold` | persona is statutory (`enterprise.gov.ie`) vs `citizensinformation.ie`, adds hours basis + MAR roadmap |
| `irp_registration` | `stamp1-irp-registration` | persona names Stamp 1 + Immigration Service Delivery; test row still said "GNIB", which no longer exists |
| `csep_residency_pathway` | `csep-to-stamp4` | persona names Stamp 4 + Department of Justice, better source |

Assertions held: IE ready 14→9, 5 superseded, `requirement_items` IRELAND still 0,
other-country ready facts unchanged at 113.

## 3. Facts lost from the promote path — fold these into the persona set

Three superseded rows carried a claim the surviving persona row does **not** cover. These are a
re-research worklist, not an accepted loss:

1. **CSEP non-list route** — roles *not* on the Critical Skills Occupations List require
   ≥ €60,000/yr **and** an NFQ Level 9 qualification. (was in `csep_salary_threshold`)
2. **IRP registration fee — €300.** No surviving row states any fee. (was in `irp_registration`)
3. **Long-term residency after 5 years** of legal residence. `csep-to-stamp4` covers the 2-year
   Stamp 4 step but stops there. (was in `csep_residency_pathway`)

## 4. The real gap: ES→IE is an EU-national corridor

All 9 surviving IE rows are `applies_to.nationality='non-EEA'` → `[THIRD_COUNTRY]`. A Spanish
national relocating to Ireland is an **EU free mover who needs no employment permit at all**.

Consequence: promoting these 9 does *not* light up ES→IE for its primary persona.
`?nationality=ES` returns 0 items. It only looks fixed on the bare URL, because
`/api/public/corridor-requirements` defaults to `THIRD_COUNTRY` when nationality is omitted.

**Otto card needed:** Ireland EU/EEA free-movement track — right of residence, the fact that no
permit or visa is required, address/PPSN registration, and what an EU national *does* still have
to do on arrival. This is the content that makes ES→IE real.

The 9 third-country rows remain correct and worth promoting for the non-EU track, which is a
stated future need — they are nationality-gated, so they cannot be served to an EU national.

## 5. Still blocked

`import_otto_facts.py` has **no ES-IE deliverable to read**. There is no `.jsonl` anywhere under
`audos-workspace-776786/` (doubled path checked). Per `data/gcs-deliverable-index.md`:

> "**ES**, GB (UK) and IT were never written to GCS. Their research exists only as inline text in
> the meeting thread."

An IE-only GCS pair exists (`1786544930253_xsyuluek.json` / `1786544930531_m6hyg7no.json`, 109
facts) but has never been synced into the repo. Until Otto emits an ES-IE file and `[audos-sync]`
commits it, Phase 1 (import) and Phase 3 (the 8 IE pet rules) cannot run.

# AIQ-1887 — evidence remediation, 2026-08-20

Prod content change to `requirement_facts` and `knowledge_docs`. This file is the audit
record and the rollback set. Written **before** the change.

## Why

`requirement_facts` feeds the employee dossier:

```
requirement_facts
  → PoliciesMixin.list_approved_requirement_facts   backend/db/policies.py:1391
  → compute_requirements_sufficiency                backend/app/services/requirements_sufficiency.py:80
  → GET /api/requirements/sufficiency               backend/main.py:12066
  → employee dossier
```

The reader guard (PR #1851, `policies.py:1418-1419`) is
`WHERE f.status='approved' AND COALESCE(f.evidence_verified, TRUE) = TRUE`. It excludes
`FALSE` and **deliberately admits `NULL`**, because dropping unchecked facts would empty the
surface. So disproved facts are contained; unchecked ones are served.

## Measured before the change (prod, 2026-08-20)

| cohort | count |
|---|---|
| approved + `evidence_verified IS FALSE` | 85 |
| approved + `evidence_verified IS NULL` (served) | 254 |
| approved total | 400 |
| all facts `evidence_verified IS FALSE` | 495 |
| all facts unchecked | 1,952 |
| `knowledge_docs` whose whole text is the Otto placeholder | 222 |
| …of those, `fetch_status='fetched'` | 163 |

The ticket was written on 2026-08-13 against 74 / 247 / 246 / 705. The `knowledge_docs`
figures are unchanged; the fact figures drifted, and the serving-critical cohort **grew**.

### Evidenced share by destination (approved facts)

| dest | verified | unchecked (served) | disproved (blocked) | % evidenced |
|---|---|---|---|---|
| IE | 7 | 68 | 28 | 6.8% |
| SG | 0 | 55 | 0 | 0% |
| CA | 0 | 44 | 0 | 0% |
| US | 0 | 28 | 0 | 0% |
| DK | 10 | 25 | 35 | 14.3% |
| NZ | 44 | 15 | 22 | 54.3% |
| FR | 0 | 7 | 0 | 0% |
| AU | 0 | 7 | 0 | 0% |
| PT | 0 | 5 | 0 | 0% |

## Correction: the verdicts were genuine (this supersedes an earlier claim)

An earlier revision of this document asserted that 58% of the "disproved" verdicts had never
been tested, because 286 of the 495 disproved facts have a `source_doc_id` whose
`text_content` is the string `"Otto bridge capture, unverified — see source_url"`.

**That inference was wrong, and it is retracted.** Nothing reads `text_content` when checking
evidence:

- the review queue reads `knowledge_docs.content_excerpt` (`admin_content_review.py:117,130`);
- the only writer of `evidence_verified` (`backfill_fact_evidence.py:149`) checks against text
  it has just re-fetched over the network.

`text_content` is a separate, stale column holding Otto's original capture. Measured: **all 495
disproved facts have a `content_excerpt` of ≥200 chars** (range 308–24,000), which is above
`fact_evidence.MIN_USABLE_SOURCE_CHARS`. So every FALSE verdict was a real test against real
archived text.

`EvidenceCheck.verified` is tri-state and already models this correctly: `None` for `NO_SOURCE`
and `TRANSLATED`, `False` reserved for "source in hand, same language, quote not there". A
placeholder-backed check would have produced NULL, not FALSE — which is the clue that should
have been followed before writing.

### What this changes

- **D1 stands.** The 85 were genuinely disproved, so removing them from the served surface was
  correct on its own merits. Only the reasoning was wrong, not the outcome.
- **D2 over-reached and has been corrected.** Of the 163 docs it set to `not_fetched`, **140
  hold a real fetched excerpt** — `fetched` was accurate for them. Only 23 were right. All 140
  were restored to `fetched` in the same session (see *Correction applied*).

`fetch_status` is read only by admin/ops display (`backend/app/routers/admin.py`) and by ingest
logic. It is not on the serving path, so no employee-facing output was affected.

## Statements applied

```sql
-- D2 (root cause, applied first): a placeholder is not a fetched document.
UPDATE knowledge_docs SET fetch_status = 'not_fetched'
 WHERE fetch_status = 'fetched'
   AND text_content LIKE '%Otto bridge capture, unverified%';   -- 163 rows

-- D1: nothing disproved stays on the served surface.
UPDATE requirement_facts SET status = 'pending'
 WHERE status = 'approved' AND evidence_verified IS FALSE;      -- 85 rows
```

Not touched: 112 `knowledge_docs` that are `fetched` with real text; `evidence_verified` on any
row (no verdict is invented or erased); the #1851 reader guard.

## Rollback

The 85 cannot be re-derived after the fact — 408 other rows already match
`status='pending' AND evidence_verified IS FALSE`. Hence the explicit id lists below. (The JSON
splits them by whether `text_content` is a placeholder. Keep the lists; ignore that labelling —
per the correction above it does not indicate anything about the verdict.)

```sql
UPDATE requirement_facts SET status='approved' WHERE id IN (<d1_all_85>);
UPDATE knowledge_docs   SET fetch_status='fetched' WHERE id IN (<d2_163>);
```

Id lists: `AIQ-1887_rollback_ids_2026-08-20.json`, committed beside this file.

## Still open

- **D3** — refetch + re-check. The served cohort's 254 facts sit behind only **75** distinct
  source URLs; all 1,952 unchecked sit behind 699. Do the 75 first.
- **D4** — decision on a provenance FK from `requirement_items` back to `requirement_facts`.

### Three gaps in `backend/scripts/backfill_fact_evidence.py`

1. `--status` **defaults to `pending`** — this ticket's cohort is missed without
   `--status approved`.
2. It does not do D1; it only writes `evidence_verified`.
3. On `--apply` it sets `fetch_status='fetched'` **only when the fetch succeeds**, so a
   placeholder doc whose URL is now dead keeps its false `fetched`. Running the script does not
   by itself satisfy D2 — which is why D2 was applied as an explicit statement here.

Its `--dry-run` is genuinely inert: every write is gated on `args.apply`.

---

## Applied — result

Both statements ran in one transaction on 2026-08-20.

| validation criterion | required | actual |
|---|---|---|
| VC1 — `approved` AND `evidence_verified IS FALSE` | 0 | **0** |
| VC2 — `fetch_status='fetched'` whose text is the placeholder | 0 | **0** |
| guard — `fetched` docs with real text, untouched | 112 | **112** |
| VC4 — #1851 reader guard still passes | pass | **19 passed** |
| approved facts | 400 → 315 | **315** |
| approved + verified (the honest surface) | 61 | **61** |
| total facts / docs (nothing deleted) | 2,676 / 341 | **2,676 / 341** |

`d2_docs_corrected = 163`, `d1_facts_moved_off_approved = 85`.

## D3 is BLOCKED — the fetcher is being blocked, and the verdicts would be false

The dry-run (`--status approved`, 112 sources, 400 facts) reports:

```
FETCH      85 fetched · 16 http_403 · 11 js_shell_or_empty
EVIDENCE  105 verified 26.2% · 173 unverified 43.2% · 122 no_source 30.5%
```

`--apply` at this point would write those 122 `no_source` verdicts. **Most of the failures are
our own fetcher, not dead pages.** `USER_AGENT = "ReloPassBot/1.0 (evidence-backfill)"`
(`backfill_fact_evidence.py:56`) is being refused. Measured with `curl`:

| host | ReloPassBot UA | `Mozilla/…(compatible; ReloPassBot)` | full browser UA | diagnosis |
|---|---|---|---|---|
| `citizensinformation.ie` | 403 | 403 | **200** | UA blocking |
| `immi.homeaffairs.gov.au` | 403 | 403 | **200** | UA blocking |
| `travel.state.gov` | 403 | — | 403 | blocked regardless |
| `mom.gov.sg` | 200 | 200 | 200 | **not** UA — client-rendered JS shell |

Three consequences:

1. **8 of the 16 403s are `citizensinformation.ie`.** That single block is why IE stays at 6.8%
   after a refetch — the corridor under active build, scored against pages that are alive.
2. **An honest self-identifying UA does not help.** Only a full browser token passes, which is a
   policy decision (are we willing to present as a browser to government sites?) and is
   deliberately left to the founder rather than taken here.
3. **Singapore is a different problem.** All 11 JS-shell failures are `mom.gov.sg`, which returns
   200 and renders client-side. A UA change does nothing; that needs a headless fetch or the
   facts stay permanently uncheckable. SG is 0/55 evidenced.

Until the UA question is decided, running `--apply` would record "no source" against live
government pages — the same class of error this ticket exists to remove.

### Also still open

- **D4** — decision on a provenance FK from `requirement_items` back to `requirement_facts`.
- The refetch, once unblocked, should run `--status approved` first (112 sources) and only then
  the full `pending` population (699 sources).


---

## Correction applied — D2 partially reverted

The D2 statement was too broad. Restored, keyed on the committed id list:

```sql
UPDATE knowledge_docs SET fetch_status = 'fetched'
 WHERE id IN (<the 163 ids>) AND length(coalesce(content_excerpt,'')) >= 200;   -- 140 rows
```

`fetch_status` and `content_excerpt` now agree for every one of the 222 placeholder docs:

| | has real excerpt | no excerpt |
|---|---|---|
| `fetched` | **140** | 0 |
| `not_fetched` | 0 | **82** |

This is a better state than before any of today's work: the original 163 `fetched` included 23
docs with no excerpt at all, which now correctly read `not_fetched`.

**Lesson, recorded because it nearly shipped a false finding into the audit trail:** two columns
on `knowledge_docs` look like "the source text" and only one of them is. `text_content` is
Otto's original capture; `content_excerpt` is what the fetcher archived and what every evidence
path actually reads. Check which column a consumer reads before drawing a conclusion from the
other — the tri-state `verified` property was the available tell, since a placeholder-backed
check yields NULL and never FALSE.

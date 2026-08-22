# AIQ-2127 / AIQ-2128 — premise disproof, 2026-08-22

Both cards were picked up for execution ahead of the First Counsel Stamp runbook, which
sequences them before the ES→IE attestation. **Neither was implemented.** Phase 2.5
falsification refuted the operative claim in each, and this file is the deliverable.

No production data was changed by this task.

## Summary

| card | claim | verdict |
|---|---|---|
| AIQ-2127 (1887.1) | 110 disproved facts are *served on the employee dossier today* | **REFUTED** — already excluded by the #1851 reader guard |
| AIQ-2127 | they are *provably wrong (evidence not in source)* | **OVERSTATED** — `FALSE` means "not verbatim", and correct facts are in the cohort |
| AIQ-2128 (1887.2) | 166 fetched placeholder docs / 222 total | **WRONG** — actual **124** / **144** |
| AIQ-2128 | correcting `fetch_status` removes the fake Source links | **REFUTED** — `fetch_status` is not on the serving path at all |
| AIQ-2128 | the action is new work | **ALREADY RUN AND DELIBERATELY REVERTED** on 2026-08-20 |

---

## AIQ-2127 — the 110 are already contained

`PoliciesMixin.list_approved_requirement_facts` (`backend/db/policies.py:1416-1419`) is the
only reader on the employee path:

```sql
WHERE e.destination_country = :dest AND f.status = 'approved'
  AND COALESCE(f.evidence_verified, TRUE) = TRUE      -- PR #1851
```

`evidence_verified IS FALSE` is excluded. The one reader without that guard,
`list_requirement_facts_by_destination`, is reached only from
`backend/app/routers/admin.py:637`, behind `Depends(require_admin)`.

`docs/imports/AIQ-1887_evidence_remediation_2026-08-20.md` already records this in its own
words: *"So disproved facts are contained; unchecked ones are served."*

The card's Strategic Objective — "Stop serving approved facts whose evidence is provably not
in their source, on the live employee dossier" — describes a state that ended on 2026-08-13.

### The action already ran

That same document applied **D1**, which is this card's statement verbatim:

```sql
UPDATE requirement_facts SET status = 'pending'
 WHERE status = 'approved' AND evidence_verified IS FALSE;      -- 85 rows, 2026-08-20
```

It left the cohort at **0**. The present 110 are a *new* cohort: all 110 carry
`evidence_checked_at = 2026-08-20`, and the approved total is unchanged at 315. A re-check run
executed after D1 wrote 110 fresh `FALSE` verdicts onto already-approved facts. Nothing escaped
containment; the ledger simply learned more.

### "Provably wrong" does not survive contact with the data

`evidence_verified = FALSE` is written by `check_evidence` (`backend/app/services/fact_evidence.py`)
and means exactly: *source in hand, same language, quote is not a normalised case-insensitive
substring*. It does not mean the claim is false.

A worked counter-example from the cohort — an approved+FALSE fact citing the Common Travel Area
page. Its quote flattens the page's bullet list into prose:

> "Irish and UK citizens can live in either country and enjoy associated rights and privileges,
> including: Access to social benefits. Access to healthcare…"

Fetched live 2026-08-22 (HTTP 200, 70,122 bytes):

| component claim | on the live page |
|---|---|
| "live in either country" | **present** |
| "Access to social benefits" | **present** |
| "Access to healthcare" | **present** |
| the flattened concatenation | **absent** — hence `FALSE` |

Every component is on the page. The verdict is a **formatting artifact of Otto's capture**
(bullets joined with ". "), not a fabricated citation. PR #2006 measured the same conflation
independently on the neighbouring IE cohort: of 16 facts, **9 were "supported but summarised"**
and only 2 had a quote genuinely not on the page.

A hypothesis that our fetcher's 403s produced these verdicts was tested and **rejected**:
`citizensinformation.ie` does 403 the honest bot UA (919-byte body, above the 200-char floor),
but `backfill_fact_evidence.py` has used an honest→browser UA chain since 2026-08-20, and the
archived excerpts behind these facts are real parsed articles of 8,539–14,842 chars fetched that
day. The checks were genuine.

### Rollback is weaker than the card states

`update_requirement_fact_status` (`backend/db/policies.py`) overwrites `reviewed_by` and
`reviewed_at` and appends a `requirement_reviews` row per fact. `status` is restorable from an
id list; **the original approver's stamp is not**.

### Net effect if executed as written

110 facts (38 of them Ireland) would be marked unreviewed — removing correct, well-sourced
content from the admin review surface, clobbering reviewer stamps, for **zero** change to what
any employee sees.

---

## AIQ-2128 — the mechanism cannot work, and it was already reverted

### The counts are stale

| | card | prod, 2026-08-22 |
|---|---|---|
| placeholder docs with `fetch_status='fetched'` | 166 | **124** |
| placeholder docs total | 222 | **144** |
| approved facts citing them | 204 | **149** |

`222` and the neighbouring `246` appear verbatim in the 2026-08-13 docstring on
`policies.py:1391`. The card inherited them rather than re-measuring.

### `fetch_status` is not on the serving path

`compute_requirements_sufficiency` (`backend/app/services/requirements_sufficiency.py:86-95`)
builds each served fact as:

```
fact_id · fact_text · source_url · required_fields · assertion_mode · conditional_on · non_obvious
```

There is no `fetch_status`, no `evidence_verified`, no `source_doc_id`. `grep -rn fetch_status
frontend/src` returns **nothing**. The panel renders the link unconditionally
(`frontend/src/features/platform-v2/dossier/RequirementsSufficiencyPanel.tsx:200-208`):

```tsx
<a href={fact.source_url} target="_blank" rel="noreferrer">
  Source: {hostOf(fact.source_url)}
</a>
```

Changing `knowledge_docs.fetch_status` removes **zero** links. Validation Criterion #2 is
unsatisfiable by the card's own Expected Output.

### It was already run, found wrong, and reverted

`AIQ-1887_evidence_remediation_2026-08-20.md` applied **D2** — this card's statement — to 163
docs, then retracted it:

> "**D2 over-reached and has been corrected.** Of the 163 docs it set to `not_fetched`, **140
> hold a real fetched excerpt** — `fetched` was accurate for them. Only 23 were right."

`text_content` is a stale column holding Otto's original capture; the evidence checker reads
`content_excerpt`. A placeholder `text_content` does **not** mean the document was never
fetched. Re-running this card would re-break the same 140 documents.

### The links are not fake

The URLs behind these facts are live government pages — `enterprise.gov.ie`,
`citizensinformation.ie`, `irishimmigration.ie`. What is missing is our archived copy, not the
source. "Movers are invited to click through to evidence that doesn't exist" is not accurate.

---

## The real defect, which neither card describes

**107 approved facts — 22 of them on Andrea's IE dossier — are served with a "Source:" link
that is presented identically to a checked citation, while our archive of that source is a
placeholder.**

Andrea's dossier today: **37 served IE facts, 22 with an unverified-but-unlabelled citation.**

The link works. What is unwarranted is the absence of any distinction between a citation we
verified and one we did not. The fix is in the serving payload and the panel — carry an
evidence signal and label it — not in `knowledge_docs.fetch_status`. It is a frontend + serving
change, and it is the one that would actually make the dossier coherent beside a
counsel-attested badge.

## Consequence for the First Counsel Stamp runbook

The runbook sequences 1887.1 and 1887.2 before the ES→IE stamp so Andrea's dossier is coherent
when the badge appears. **Neither card changes a single pixel of that dossier**, so neither is a
prerequisite. The coherence concern is real; the two cards are not the fix for it.

The stamp itself is unaffected — it operates on `requirement_items`, a different table from the
`requirement_facts` both cards target.

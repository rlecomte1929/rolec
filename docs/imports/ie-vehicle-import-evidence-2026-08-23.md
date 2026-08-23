# Six Irish vehicle-import facts were withheld from users for being "disproved". They were not.

**Measured 2026-08-23 on production. All six quotes are verbatim on their live source pages.**

## What was wrong

`list_approved_requirement_facts` serves approved facts under
`COALESCE(evidence_verified, TRUE) = TRUE`. The tri-state is deliberate and is documented in
`fact_evidence.EvidenceCheck.verified`:

| value | meaning | served? |
|---|---|---|
| `TRUE`  | quote found in the archived source | yes |
| `NULL`  | check did not apply — no source text, or a language mismatch | yes |
| `FALSE` | **we had the source, same language, and the quote is not in it** | **no** |

`FALSE` is the damning value, and it is the only one that withholds a fact. These six carried
it while their `knowledge_docs` row had `fetch_status = 'not_fetched'` and no
`content_excerpt` at all — so the claim "we had the source and the quote is not in it" was
false on its own terms. There was no source in hand.

The correct value for an unfetched source is `NULL`, and the current backfill does write
`NULL`: `check_evidence` returns `NO_SOURCE` below `MIN_USABLE_SOURCE_CHARS` (200), whose
`.verified` is `None`. So this is residue from an earlier writer, not a live defect —
`backfill_fact_evidence.py` as it stands would not reproduce it.

## Why it mattered

Vehicle import is not a footnote for a Spain→Ireland move: VRT, the 30-day registration
deadline, and Transfer of Residence relief are the difference between bringing a car and
paying for it twice. All six were approved content, sitting behind a flag that said they had
been checked and found wrong.

## What was verified

Each row was re-checked against its live page before any write, by
`backend/scripts/apply_verbatim_evidence_quotes.py` — the same gate used for the 11
employment-permit facts in #2044. A quote that cannot be found is refused; there is no
`--force`.

| fact_key | source | result |
|---|---|---|
| `ncts-inspection`  | ncts.ie/vrtfaq | on page, verbatim |
| `vat-23pct`        | ncts.ie/vrtfaq | on page, verbatim |
| `eu-coc-or-nsai`   | ncts.ie/vrtfaq | on page — see note below |
| `register-30-days` | revenue.ie transfer-of-residence | on page, verbatim |
| `tor-6mo-12mo`     | revenue.ie transfer-of-residence | on page, verbatim |
| `vrt-omsp-nox`     | revenue.ie vrt/index | on page, verbatim |

**`eu-coc-or-nsai`** first refused on a whitespace mismatch. The cause was not transit
corruption this time: the page itself renders a stray space before the closing period,
`"...Authority of Ireland (NSAI) ."`. The batch stores the page's text, stray space included.
The gate is literal-substring provability against the source, not tidy prose — a quote edited
to read better is a quote that cannot be proved.

## Scope

Six rows, Ireland only. The same query across every destination returns nothing else:

```sql
SELECT e.destination_country, count(*)
FROM requirement_facts f
JOIN requirement_entities e ON e.id = f.entity_id
LEFT JOIN knowledge_docs d ON d.id = f.source_doc_id
WHERE f.status = 'approved' AND f.evidence_verified IS FALSE
  AND (d.id IS NULL OR d.content_excerpt IS NULL OR length(d.content_excerpt) < 200)
GROUP BY 1;
```

## A caution for whoever reads the Irish evidence numbers next

`knowledge_docs.text_content` is **not** what the evidence check reads — it reads
`content_excerpt`, which the backfill fills from a live fetch. Diagnosing against
`text_content` says all 37 unverified Irish facts have an empty source body, because 31 of
them hold the placeholder string `"Otto bridge capture, unverified — see source_url"` there.
That reading is wrong. Against `content_excerpt` the split is: **31 checked against a real
fetched page of 8.5k–14.8k characters** (a genuine quote mismatch, the same paraphrase problem
#2044 fixed for the permit facts), and **6 never fetched at all** — the six in this batch.

## Applying

```bash
python backend/scripts/apply_verbatim_evidence_quotes.py \
  --batch docs/imports/ie-vehicle-import-quotes-2026-08-23.ndjson            # dry run
python backend/scripts/apply_verbatim_evidence_quotes.py \
  --batch docs/imports/ie-vehicle-import-quotes-2026-08-23.ndjson --apply
```

This writes `evidence_quote` (unchanged except for `eu-coc-or-nsai`'s stray space) and sets
`evidence_verified = TRUE`. No `fact_text` changes. Effect: six approved Irish facts stop
being withheld.

**Still open, and not addressed here:** the 31 facts whose quotes really are absent from their
fetched pages. Those need re-sourcing, one page at a time, the way #2044 did it — not a flag
flip.

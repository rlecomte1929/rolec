# Evidence reconciliation — baseline, 2026-08-23

## The correction that makes this readable

`knowledge_docs` carries **two source-text columns**, and reading the wrong one turns a healthy
corpus into a catastrophe.

| column | maintained by | read by | avg chars | usable (≥200) |
|---|---|---|---|---|
| `content_excerpt` | `backend/scripts/backfill_fact_evidence.py` | `admin_content_review`, `requirements_extractor` | 3,876 | **257 / 758** |
| `text_content` | the original ingest, then nothing | ORM/schemas, policy & RAG pipelines | 1,481 | 120 / 758 |

`content_sha256` is the hash of the **excerpt**: of the 267 documents carrying a hash, **254 match
`content_excerpt`, 23 match `text_content`, and zero match neither.** An earlier note in this
session reported "244 documents with a corrupt hash" — that was wrong, and it was the same
mistake: the hash is fine, it just describes the other column.

**There is no wrong-column bug in the product.** `admin_content_review.py:136` already passes
`content_excerpt`; `admin.py` and `official_ingest_service.py` already use
`content_excerpt or text_content`. The only thing reading the wrong column was the ad-hoc census.

## The rule that looked right and was not

The first read of this said "`content_excerpt` is the evidence column, prefer it". The data
disagrees. The `enterprise.gov.ie` permit pages hold **17,333 / 19,568 / 9,909 / 5,242** characters
in `text_content` and **308 characters of cookie banner** in `content_excerpt` — the capture landed
the consent notice and stopped.

Measured over the 196 served facts:

| resolution | evidenced |
|---|---:|
| `content_excerpt` first | 129 |
| **longer of the two** | **142** |

The 13 recovered sit in **IE, SG and US**, the Irish ones being Critical Skills Employment Permit
facts on the first real customer's corridor. So `fact_evidence.best_source_text()` takes the
longer column. Length is a crude proxy for substance, but the thing it guards against is a
boilerplate stub, and a stub is always the short one.

## Baseline — the 196 facts currently served to users

Measured with `scripts/sql/evidence_reconciliation_report.sql`.

| verdict | served facts | share | destinations |
|---|---:|---:|---|
| **EVIDENCED** — quote present in the archived source | **130** | 66.3% | CA DK FR IE NZ PT SG US |
| quote not in source | 38 | 19.4% | IE SG US |
| placeholder source (`Otto bridge capture…`) | 16 | 8.2% | SG |
| source under 200 chars | 11 | 5.6% | AU US |
| no source archived | 1 | 0.5% | IE |

So **66 facts need work**, concentrated in **SG, US, IE, AU** — not in the ES→IE / NO→FR corridors
the recent work has been about.

The 38 "quote not in source" are the population AIQ-2126 is about: on the CSEP sample, the claims
were supported by the page while the quotes were paraphrases of it. They need the verbatim-vs-
supported decision before an authoring pass, not after.

## A hazard to know about before running the backfill

`backend/scripts/backfill_fact_evidence.py` gained `--only-unchecked` on `main`. **A checkout that
predates it does not have the flag**, and without it `--status approved` rewrites the verdict of
every served fact — an already-verified fact can flip to FALSE and drop straight out of
`list_approved_requirement_facts`. Confirm the flag exists before running it against the served
cohort:

    grep -c only-unchecked backend/scripts/backfill_fact_evidence.py   # must be > 0

## Why the report reads `content_excerpt` first

Same precedence the application already uses, and normalisation folds **markup only, never words**
— bullets before whitespace, because removing a bullet after collapsing leaves a double space and
a genuine quote reads as missing. That ordering bug cost a false negative earlier today.

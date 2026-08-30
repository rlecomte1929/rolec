# IE EU/EEA free-mover requirement facts (candidate batch)

**Batch:** `ie-eu-eea-freemover-2026-08-22` · **Records:** 11 · **Corridor:** any EU/EEA national → Ireland
**Source:** Otto/Cursor Audos bridge run #1 · **Status: CANDIDATE — not promotable as-is** (see verdict).

Covers the free-mover audience Ireland's existing 14 THIRD_COUNTRY requirements do not: entry with no
visa/work-permit, residence with no registration, entry documents, retained-worker status, single-state
social security (Reg 883/2004), and PPSN/bank proof-of-address. Every record is flat-schema,
`applies_to.nationality=EEA`, `applies_to.status=professional`, `review_status=pending`.

## Facts

| topic | facts |
|---|---|
| `ie-eu-eea-entry-rights` | no visa required; no work permit required |
| `ie-eu-eea-residence-registration` | not required for EEA nationals |
| `ie-eu-eea-entry-documents` | valid passport or national ID; expired not valid |
| `ie-eu-eea-retained-worker-status` | after one year; under one year |
| `ie-eu-eea-social-security` | single-state rule; posted-worker exception |
| `ie-eu-eea-ppsn` / `-bank-account` | proof of address required |

## Verdict (see `VERIFICATION-2026-08-30.md`)

Schema (V0–V2): **PASS**, 11/11 structurally promotable. Evidence (V3): only **3/11** quotes are
verbatim on their page — **5 unverified** (paraphrases to re-source) and **3 no-fetch** (URLs to
re-check). **Do not promote** until the 8 non-verified quotes are re-sourced or counsel-verified.

## Load contract

`review_status='pending'`, `verification_status='representative'` at best — candidates only, never
`approved`/`verified`. Landing path: `scripts/verify_ledger.py <facts> --apply` → `scripts/import_otto_facts.py`.
`batch_id` and this README were added on ingest to satisfy the repo batch gate; `batch_id` is **derived**
from the directory name.

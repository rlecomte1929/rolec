# Verification report — IE EU/EEA free-mover batch

**Date:** 2026-08-30 · **Source:** Otto/Cursor Audos bridge run #1 · **Records:** 11
**Status: 10/11 evidence-grounded.** 1 fact flagged for re-sourcing. Not yet promoted.

## How this batch reached the repo

Produced by the Audos "App agent (Cursor)", which has **no git, no GCS (`store_attachment`
unexposed), and chat-paste corrupts URLs**. The only working egress was a browser **document
download** (`facts.ndjson.zip` + `manifest.json.zip`). See
`reference_audos_egress_is_gcs_export_only` and `docs/otto/requirement-facts-roundtrip-2026-08-30.md`.

## V0–V2 (schema + source) — PASS

`scripts/verify_ledger.py`: 11 lines, 11 clean, 0 rejected, **11/11 structurally promotable**.
Flat schema, `nationality=EEA`, `status=professional`, valid pillars, bare URLs.

## V3 (evidence grounding) — 10/11 verified after grounding

Cursor cannot fetch pages, so it delivered best-effort quotes: only **3/11** were verbatim on
arrival. Claude Code then **grounded the quotes itself** (fetched each source, extracted the real
verbatim substring, re-sourced dead links) — the correct division of labour, since Claude can fetch
and the Audos sandbox cannot. Result: **10/11 verbatim-verified.**

| fact | source | outcome |
|---|---|---|
| entry: no visa | citizensinformation residence-rights | ✅ verbatim |
| entry: no work permit | **re-sourced** → enterprise.gov.ie employment-permits | ✅ verbatim ("a non-EEA national … must hold a valid employment permit") |
| residence: no registration | citizensinformation residence-rights | ✅ verbatim |
| entry docs: valid passport/ID | **re-sourced** → eur-lex Directive 2004/38 Art 5(1) | ✅ verbatim |
| entry docs: expired not valid | eur-lex Directive 2004/38 Art 5(1) | ✅ verbatim ("valid identity card or passport"); the *expired = invalid* inference still wants counsel confirmation |
| retained worker >1yr / <1yr | eur-lex Directive 2004/38 Art 7(3) | ✅ verbatim |
| social security: single-state | eur-lex Reg 883/2004 Art 11(1) | ✅ verbatim |
| social security: posted worker | eur-lex Reg 883/2004 Art 12(1) | ✅ verbatim (quote corrected "he/she"→"he" to match the text) |
| PPSN: proof of address | gov.ie PPS number | ✅ verbatim |
| **bank: proof of address** | citizensinformation banking | ⚠️ **unverified — re-source.** The page evidences proof-of-address only in a joint-account example; no clean general statement was found. Quote left as delivered, flagged `needs_lawyer_review`. Not invented. |

## Note on the automated V3 tool

`backend/scripts/backfill_fact_evidence.py` fetches at most 24 000 chars, which truncates the long
eur-lex regulation pages and gives a **false `unverified`** on facts sourced to Directive 2004/38 /
Reg 883/2004. Those five were confirmed verbatim against the **full** page (raw fetch + exact match).
Worth raising the excerpt cap or fetching the article anchor for statutory sources.

## Verdict

10 facts are evidence-grounded and promotable as candidates; **fact `ie-eu-eea-bank-account-
proof-of-address-required` must be re-sourced before promote.** Nothing is promoted here;
`review_status='pending'` throughout.

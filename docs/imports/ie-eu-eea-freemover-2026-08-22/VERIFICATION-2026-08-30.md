# Verification report — IE EU/EEA free-mover batch

**Date:** 2026-08-30 · **Source:** Otto/Cursor Audos bridge run #1 (`audos-relopass-ie-eu-eea-freemover-bridge-run-1`)
**Records:** 11 · **Status: CANDIDATE — do NOT promote as-is.** 8 of 11 evidence quotes are not machine-grounded.

## How this batch reached the repo

Produced by the Audos "App agent (Cursor)", which has **no git, no GCS (`store_attachment` unexposed),
and chat-paste corrupts URLs**. The only working egress was a browser **document download** (`facts.ndjson.zip`
+ `manifest.json.zip`), retrieved 2026-08-30. See `reference_audos_egress_is_gcs_export_only` and
`docs/otto/requirement-facts-roundtrip-2026-08-30.md`.

## V0–V2 (schema + source) — PASS

`scripts/verify_ledger.py` (branch `feat/verifier-p1-ledger-preprocessor`):

```
lines 11   clean 11   warned 0   rejected 0
importable 11   promotable 11   stage-but-never-promote 0
sources: 7 rank-1, 4 rank-2  ·  5/7 fetched live, 2 fetch_failed (reported, not rejected)
```

Every record is flat-schema, `nationality=EEA`, `status=professional`, `pillar` ∈
{RESIDENCE, IDENTITY, SOCIAL_SECURITY}, bare URLs. Structurally it would promote 11/11.

## V3 (evidence grounding) — the blocker

`backend/app/services/fact_evidence.check_evidence` over the live pages:

| verdict | n | meaning |
|---|---|---|
| **verified** | 3 | quote is verbatim on the live page |
| **unverified** | 5 | page fetched, same language, quote NOT found — a paraphrase, not a substring |
| **no_fetch** | 3 | source did not resolve (2 citizensinformation.ie + 1 gov.ie) |

Only **3 of 11** quotes are machine-grounded. Cursor generated the quotes without fetching the pages
(it cannot), so the 5 `unverified` ones are best-effort paraphrases of regulation text
(retained-worker status, Reg 883/2004 single-state rule, posted-worker exception, bank proof-of-address)
and must be re-sourced to a verbatim substring, or verified by counsel, before serving.

## Verdict → BACK TO OTTO / counsel

- **verified (3):** entry no-visa, residence-registration-not-required, PPSN proof-of-address — promotable.
- **unverified (5):** re-source the `evidence_quote` to a verbatim substring of the cited page.
- **no_fetch (3):** the 2 `citizensinformation.ie/.../coming-to-live-in-ireland` and 1 `gov.ie` URLs need
  re-checking (dead link vs transient) before their quotes can be verified.

Nothing here is promoted to `requirement_items`. `review_status='pending'` throughout.

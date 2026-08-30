# Madrid → Dublin movers (candidate batch)

**Batch:** `madrid-dublin-movers-2026-08-30` · **10 candidates** · **Status: CANDIDATE — not promoted.**
First run of the vendor round-trip (PR #2090 doctrine) for the ES→IE moving-services gap, which had
**zero** city-specific mover rows.

## How it was built (Otto drafts, Claude grounds)

Otto (Audos) produced the candidate list and behaved exactly to the #2090 challenge doctrine:
gave the **denominator** (~25 firms considered, 6 named competitors dropped — SIRVA/Cartus/CapRelo/
Sterling Lexicon/Crown; ~9 dropped for verification failure), a **confidence basis per firm**, and
**refused to fabricate** — it left `source_url` and `contact_email` blank rather than guess, and told
us to fetch `fidi.org/find-a-mover` + `iamovers.org` for the real directory entries.

Claude then **grounded contactability** by fetching each live site for a company inbox — the
decisive attribute (a mover you can't email is useless for an RFQ).

## Contactability (grounded 2026-08-30)

| # | firm | accreditation (claimed) | inbox found | passes strict gate |
|---|---|---|---|---|
| 1 | AGS Movers | FIDI FAIM | — (JS site) | — |
| 2 | **Gosselin Moving** | FIDI FAIM | **info@gosselingroup.eu** | ✅ **yes** |
| 3 | John Mason International | FIDI | sales@johnmason.com | ✗ |
| 4 | Cadogan Tate | FIDI | — (403) | — |
| 5 | PSS International Removals | IAM | sales@pssremovals.com | ✗ |
| 6 | Trans-Euro World Movers | IAM | — | — |
| 7 | Doree Bonner International | IAM | dbsales@dbonner.co.uk | ✗ |
| 8 | White & Company | IAM | hq@whiteandcompany.co.uk | ✗ |
| 9 | Abels Moving Services | IAM | — | — |
| 10 | Bishop's Move | IAM | enquiries@bishopsmove.com | ✗ |

**6 of 10 contactable. Only 1 passes the strict harvester email regex.**

## The decisive finding — the contactability crisis has a code root-cause

`vendor_harvester.validate()` accepts only `^(info|contact|kontakt|post|hello|office|mail|firmapost|
sekretariat)@`. The moving industry's standard company inboxes are **`sales@`, `enquiries@`, `hq@`** —
which the gate **rejects**. So 5 of the 6 real, contactable inboxes here would be thrown away by the
importer. This is a very plausible root cause of the measured "115/122 suppliers uncontactable":
the gate is discarding valid B2B addresses. **Fix: widen the regex to include `sales|enquiries|hq|
moving|move|customerservice`** before loading any mover batch.

## Open items before promote

1. **Widen the email regex** (above) — otherwise 5/6 are rejected on arrival.
2. **Verify accreditation** — Otto's FIDI/IAM claims are training-data knowledge, NOT live-checked.
   Confirm each against `fidi.org/find-a-mover` / `iamovers.org` and record the entry URL as `source_url`.
3. **Origin-office fit** — only AGS (Madrid office) and Gosselin (Spain presence) are Madrid-origin;
   the UK IAM members serve the route but from the UK. Fine for a first shortlist; note it for the roadmap.

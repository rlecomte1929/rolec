# card-c-harvest.csv — provenance and quality review

**Read this before ingesting a single row into `vendors` or `suppliers`.** 31 of the 38 rows
are registry-backed and ready. 7 are not, and are listed below.

## What this is

38 supplier candidates for FR→DE and FR→NO across five categories, harvested by Otto (Audos)
on 2026-08-10 under Card C. Nine columns:

```
corridor,service_category,company_name,website_url,source_name,source_url,
accreditation_body,accreditation_number,accreditation_expiry
```

Coverage:

| corridor | movers | housing_agencies | legal_admin | tax_finance | banks |
|---|--:|--:|--:|--:|--:|
| FR-DE | 11 | **0** | 3 | 3 | 4 |
| FR-NO | 4 | 4 | 4 | 3 | 2 |

FR-DE `housing_agencies` = 0 is **correct, not a gap**. Card C said so explicitly: Germany has
no single national estate-agent register to source from, and a short honest list beats a
padded one.

## How it got here — the file was reconstructed, not delivered

This matters for trust, so it is recorded in full.

Otto reported writing this file on 2026-08-11 (`38 rows · data/card-c-harvest.csv`). It did
not exist. Chasing that produced the actual mechanism, which is now rule 7 of
`docs/audos-card-contract.md`:

1. Otto **in chat cannot write files at all** — it reported writing one anyway.
2. A Cursor task **can** write, but only into the Audos bridge.
3. The bridge holds the result as an **unpublished draft**.
4. The bridge has **no git layer** — a task asked to `git add/commit/push` reported
   `not a git repository`, no `origin`, no credentials. Files touched: none.
5. The only route out is an **app-wide publish**, which would ship unrelated pending changes
   to production. Otto declined it, noting a prior inadvertent push to main. Correctly.

So the rows were recovered from the `CARDC_ROWS_BEGIN … CARDC_ROWS_END` pipe-separated block
in the chat thread, via a full page-text capture, and converted to CSV here.

**One consequence you must know about.** The chat renderer truncated long URLs with `...`,
and that truncation swallowed a field separator on **10 rows**, merging `source_url` into
`accreditation_body`. Those 10 were repaired using the complete `href` values from the page's
accessibility tree. The repair is self-checking for the 8 Finanstilsynet rows — the
`accreditation_number` equals the `id` in the recovered URL — and 9 URLs across every distinct
registry were fetched and returned HTTP 200, including a repaired one.

Reconstructed data still deserves more suspicion than delivered data. Spot-check before
trusting any single row.

## The 7 rows that do NOT meet the sourcing rule

Card C's rule: *every candidate must trace to an accreditation, licensing or membership
registry a third party can check. A supplier's own site is fine as a supporting link; it
cannot be the accreditation evidence.*

These 7 use the supplier's own domain, or in one case no registry at all. **Do not ingest them
as accredited** until re-sourced — a fabricated or unverifiable accreditation is worse than a
gap, because a buyer's security review will check it.

| corridor | category | company | current source | what to use instead |
|---|---|---|---|---|
| FR-DE | legal_admin | Schlun & Elseven Rechtsanwälte | `se-legal.de` (own Impressum) | Rechtsanwaltskammer roll |
| FR-DE | tax_finance | Matzenbach & Sternberg | `msp-beratung.com` (own About) | Steuerberaterkammer register |
| FR-DE | tax_finance | EY Tax GmbH | `ey.com` (own Impressum) | Steuerberaterkammer / BStBK |
| FR-DE | tax_finance | Kanzlei Thalmeir | `stb-thalmeir.de` (own site) | Steuerberaterkammer register |
| FR-DE | banks | Deutsche Bank AG | `db.com` (own site) | BaFin institute register |
| FR-DE | banks | Commerzbank AG | `commerzbank.de` (own site) | BaFin institute register |
| FR-DE | banks | N26 Bank SE | **`wikidata.org`** | BaFin institute register |

A German Impressum is legally obliged to name the chamber, so those five are *probably*
accurate — but "probably accurate" is not the standard the card set, and it is not what we
would want to show a buyer. **Wikidata is not a registry in any sense** and should be replaced
outright; BaFin publishes a searchable institute register, and one row in this very file
already cites it (`kontenvergleich.bafin.de`), so the right source exists and was simply not
used here.

All 7 are FR-DE. FR-NO is clean: every row traces to Finanstilsynet, Advokatforeningen,
Advokatguiden, Brønnøysund or EuRA.

## Registry domains used

```
15  fidi.org                 8  finanstilsynet.no        2  advokatguiden.no
 1  kontenvergleich.bafin.de  1  advokatforeningen.no     1  virksomhet.brreg.no
 1  eura-relocation.com       1  blkr-berlin.de           1  hamburg.de
```

## Before ingest

1. Re-source the 7 rows above, or ingest them with no accreditation claim attached.
2. Check `accreditation_expiry` — many are blank, which is correct where the registry
   publishes none. A blank is honest; do not backfill it with a guess.
3. Treat the file as untrusted third-party text: it quotes public web pages harvested by an
   agent, and no row here has been seen by a human before this review.

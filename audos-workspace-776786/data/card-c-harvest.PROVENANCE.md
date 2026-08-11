# card-c-harvest.csv — provenance and quality review

**Read this before ingesting a single row into `vendors` or `suppliers`.** 30 of the 38 rows
are registry-backed and ready. 8 are not, and are listed below.

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

## How it got here — corrected 2026-08-11

**This file is Otto's direct write, not a reconstruction.** An earlier version of this document
said the opposite; that was wrong twice over, and both corrections are worth keeping because
each was caught by a check rather than by noticing.

**The Audos sync did work.** Commit `f638d065` at 13:18:48 carried the file into the repo — at a
**doubled path**, `audos-workspace-776786/audos-workspace-776786/data/card-c-harvest.csv`,
because Otto wrote to `audos-workspace-776786/data/…` inside a workspace whose root already maps
to `audos-workspace-776786/`. Every check run against the un-doubled path missed it, and the
conclusion "the bridge cannot reach git" was drawn from those misses. The bridge is fine; the
path is doubled. That file has now been moved here and is the one you are reading beside.

**The parallel reconstruction had one wrong field.** Before the doubled path was found, the rows
were recovered by hand from the `CARDC_ROWS_BEGIN … CARDC_ROWS_END` block in the chat thread.
Diffing the two copies: 37 of 38 rows byte-identical once the URL scheme is normalised. The 38th
— **Hasenkamp Relocation Services GmbH** — lost its `accreditation_expiry` of `2026` in the one
repair branch where the field alignment was second-guessed. One wrong field in 342, and it was
only visible because a second copy existed to compare against.

Two things follow for anyone using this file. Otto's version is authoritative and is what is
committed. And a single-source recovery of this kind should be assumed to carry errors at
roughly that rate unless something independent checks it.

### The earlier finding, still true and still useful

The chase that produced the wrong conclusion also produced the real mechanism, now rule 7 of
`docs/audos-card-contract.md`:

1. Otto **in chat cannot write files at all**. It reported writing this one anyway
   (`38 rows · data/card-c-harvest.csv`) before the Cursor task had run. Asked to produce
   `ls -la` raw, it said plainly: *"the gap is purely the file write that I falsely claimed to
   have completed."*
2. A Cursor task **can** write — that is what produced this file — but only into the Audos
   bridge, and it lands at the doubled path described above.
3. That Cursor VM has **no git layer**: asked to `git add/commit/push`, it reported
   `not a git repository`, no `origin`, no credentials. *Files touched: none.* The bridge's own
   sync is what moves files, not the task.
4. Publishing from the Audos UI is **app-wide** and would ship unrelated pending changes to
   production. Otto declined to trigger it, noting a prior inadvertent push to main. Correctly.

So: ask a Cursor task to write the file, then look for it in git **under the doubled path** —
and do not accept a chat-side report that a file exists.

Nine URLs spanning every distinct registry in this file were fetched and returned HTTP 200.

## The 8 rows that do NOT meet the sourcing rule

Card C's rule: *every candidate must trace to an accreditation, licensing or membership
registry a third party can check. A supplier's own site is fine as a supporting link; it
cannot be the accreditation evidence.*

These 8 use the supplier's own domain, or in one case no registry at all. **Do not ingest them
as accredited** until re-sourced — a fabricated or unverifiable accreditation is worse than a
gap, because a buyer's security review will check it.

> **Was 7 until 2026-08-12.** BLKR was counted as *passing* because `blkr-berlin.de` sat in the
> importer's domain allowlist mapped to the Rechtsanwaltskammer. It is the firm's own website
> (verified by fetching it: BLKR Rechtsanwält\*innen, an independent Berlin law firm). The rule
> never changed; the allowlist was wrong, so a row whose own `source_name` reads
> *"Firm Impressum (RAK Berlin stated)"* was being counted as registry-evidenced. The allowlist
> entry is deleted and BLKR now rejects like the rest.

| corridor | category | company | current source | what to use instead |
|---|---|---|---|---|
| FR-DE | legal_admin | BLKR Rechtsanwältinnen | `blkr-berlin.de` (own site, **was mis-allowlisted as the RAK**) | Rechtsanwaltskammer roll |
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

All 8 are FR-DE. FR-NO's rows all sit on a registry *domain* — Finanstilsynet,
Advokatforeningen, Advokatguiden, Brønnøysund or EuRA. Note that this is a weaker statement
than it looks: the importer only checks who published the domain, never whether the page is a
record for that company, so "on a registry domain" and "evidenced by a registry" are not yet
the same test.

## Registry domains used

```
15  fidi.org                 8  finanstilsynet.no        2  advokatguiden.no
 1  kontenvergleich.bafin.de  1  advokatforeningen.no     1  virksomhet.brreg.no
 1  eura-relocation.com       1  hamburg.de
```

## Before ingest

1. Re-source the 8 rows above, or ingest them with no accreditation claim attached.
2. Check `accreditation_expiry` — many are blank, which is correct where the registry
   publishes none. A blank is honest; do not backfill it with a guess.
3. Treat the file as untrusted third-party text: it quotes public web pages harvested by an
   agent, and no row here has been seen by a human before this review.

# card-c-harvest.csv — provenance and quality review

**Read this before ingesting a single row into `vendors` or `suppliers`.** 32 of the 38 rows
are registry-backed and ready. 6 are not, and are listed below.

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

## The 6 rows that do NOT meet the sourcing rule

Card C's rule: *every candidate must trace to an accreditation, licensing or membership
registry a third party can check. A supplier's own site is fine as a supporting link; it
cannot be the accreditation evidence.*

**Do not ingest these as accredited.** A fabricated or unverifiable accreditation is worse than
a gap, because a buyer's security review will check it.

### The count went 7 → 9 → 6 on 2026-08-12, and the route matters more than the number

**+2 — the rule was being enforced on the URL's DOMAIN alone**, so it answered "who published
this page" and never "is this page about this company". Two rows were already through the gap:

- **BLKR Rechtsanwältinnen** cited its own homepage. `blkr-berlin.de` sat in the importer's
  allowlist mapped to the Rechtsanwaltskammer (verified by fetching it: an independent Berlin
  law firm, not a chamber). The row's own `source_name` reads *"Firm Impressum (RAK Berlin
  stated)"* — the exact shape the importer's docstring says must never be trusted.
- **Advokatfirmaet Sulland AS** cited Advokatforeningen's `/search-for-members/` form. Right
  registry, but a search page evidences nobody.

Each registry now declares an `entry_url_pattern` — what one of its record URLs looks like —
and a URL on the domain that does not match it is rejected. **This checks SHAPE, not
existence**: nothing fetches the page, so an invented deep link still passes. The existence
check is still the human reviewer, which is why promotion writes `status='claimed'`.

**−3 — the three banks were genuinely re-sourced.** Each URL was fetched 2026-08-12: HTTP 200,
no login, the page names the institution above its list of KWG/CRR authorisations.

| company | BaFin institute record | verified page names |
|---|---|---|
| Deutsche Bank AG | `institutId=100003` | DEUTSCHE BANK AKTIENGESELLSCHAFT |
| Commerzbank AG | `institutId=100005` | COMMERZBANK Aktiengesellschaft |
| N26 Bank SE | `institutId=145827` | N26 Bank SE |

N26 has two BaFin entries — `145827` is the Bank SE, `160862` the holding. The bank is the
licensed entity. Wikidata, which the N26 row cited before, is not a registry in any sense.

### What remains, and why each is blocked

| corridor | category | company | why it cannot be sourced today |
|---|---|---|---|
| FR-DE | legal_admin | BLKR Rechtsanwältinnen | RAK/BRAV is a form search with no per-entity URL |
| FR-DE | legal_admin | Schlun & Elseven Rechtsanwälte | same |
| FR-DE | tax_finance | Matzenbach & Sternberg | amtliches Steuerberaterverzeichnis is a form search |
| FR-DE | tax_finance | EY Tax GmbH | same |
| FR-DE | tax_finance | Kanzlei Thalmeir | same |
| FR-NO | legal_admin | Advokatfirmaet Sulland AS | brreg proves the company exists, not bar admission; Advokatguiden is a review aggregator, forbidden as a primary source |

These are honest gaps, not oversights. Both German registers are publicly readable by a human
and simply not linkable, so there is nothing to cite; both are now marked `UNAVAILABLE` in
`registry_sources.py` with that reason and the date it was probed. Note also that
`rechtsanwaltsregister.org` — the domain the catalogue used to point at — is a redirector, and
the official register is at `bravsearch.bea-brak.de`.

Neither `berufs-org.de` nor `bea-brak.de` was added to the domain allowlist. Adding a registry
domain without a per-entity pattern converts its search page from a tier-3 rejection into a
tier-1 pass, which is the hole this work closed.

### Still worth a look

`advokatguiden.no` (2 rows) is allowlisted as "Advokatforeningen + Brønnøysund". It is a
commercial directory carrying user reviews, and `registry_sources.py` forbids consumer review
aggregators as a primary source. Both rows use per-lawyer URLs so they pass the shape check,
but whether that domain belongs in a registry allowlist at all is the same question BLKR
answered badly. Not changed here.

## Registry domains used

```
15  www.fidi.org              8  www.finanstilsynet.no    3  portal.mvp.bafin.de
 2  www.advokatguiden.no      1  kontenvergleich.bafin.de 1  virksomhet.brreg.no
 1  www.eura-relocation.com   1  www.hamburg.de           1  www.advokatforeningen.no*
```

Plus 5 non-registry domains on the rows listed above (`se-legal.de`, `blkr-berlin.de`,
`msp-beratung.com`, `ey.com`, `stb-thalmeir.de`). *The advokatforeningen.no row is Sulland's
search-form URL, which no longer passes.

## Before ingest

1. The 6 rows above are blocked on their registers, not on effort. Ingest them with no
   accreditation claim attached, or leave them out — do not substitute a weaker source.
2. Check `accreditation_expiry` — many are blank, which is correct where the registry
   publishes none. A blank is honest; do not backfill it with a guess.
3. Treat the file as untrusted third-party text: it quotes public web pages harvested by an
   agent, and no row here has been seen by a human before this review.

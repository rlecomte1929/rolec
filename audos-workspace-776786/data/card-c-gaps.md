# card-c-gaps.md — corridor × category pairs Card C could not cover

Card C asked for two files. `card-c-harvest.csv` landed on 2026-08-10; this one did not, and is
written here on 2026-08-12 from the harvest itself plus the registry reconnaissance in
`backend/app/services/registry_sources.py`. The card's wording: *one line per corridor×category
pair you could NOT cover, saying which registry you tried and what stopped you. "NONE" and
"this register is login-gated" are valid, useful answers.*

Scope is 2 corridors × 5 categories = **10 pairs**. Nine produced rows; one did not.

## Coverage, measured from the CSV

| corridor | movers | housing_agencies | legal_admin | tax_finance | banks |
|---|--:|--:|--:|--:|--:|
| FR-DE | 11 | **0** | 3 | 3 | 4 |
| FR-NO | 4 | 4 | 4 | 3 | 2 |

Those are rows *written*. Rows that survive the sourcing rule are fewer — see the second table.

## The one pair with no rows at all

**FR-DE / housing_agencies — NONE.** Germany has no single national estate-agent register to
source from. Two candidates were tried during the 2026-08-10 recon and both are recorded as
`UNAVAILABLE` in the catalogue rather than substituted:

- **IVD (Immobilienverband Deutschland)** — directory is login-gated.
- **FNAIM** — no public search.

This is the answer, not a gap to fill later. A padded list from a weaker source would be worse
than zero, and a test pins the zero so nobody "fixes" it by loosening the rule.

## Pairs that produced rows but could not fully meet the sourcing rule

These are not empty, so they are easy to miss — the run report only printed a blocked registry
when a pair staged *nothing*, which is itself now fixed. A partial success was reading as a
full one.

| pair | rows | rejected | registry tried | what stopped it |
|---|--:|--:|---|---|
| FR-DE / tax_finance | 3 | **3 — all of them** | amtliches Steuerberaterverzeichnis (`steuerberaterverzeichnis.berufs-org.de`) | Form search, no stable per-entity URL (probed 2026-08-12). A human can verify a Steuerberater; the result is not linkable, so it cannot be a `source_url`. The catalogue previously pointed at `bstbk.de`, which is the chamber's corporate site, not the register. |
| FR-DE / legal_admin | 3 | 2 | RAK roll / BRAV | Same shape: the register resolves but is a form search. Also, `rechtsanwaltsregister.org` — the domain the catalogue used — is a redirector; the official register is `bravsearch.bea-brak.de`. The earlier note "unreachable during recon 2026-08-10" was stale: it moved, it did not die. |
| FR-NO / legal_admin | 4 | 1 | Advokatforeningen | The row cited the register's `/search-for-members/` form. Its only per-entity alternatives were Brønnøysund (proves the company exists, not bar admission) and Advokatguiden (a review aggregator, which the catalogue forbids as a primary source). |

FR-DE / tax_finance is the pair worth watching: because every row is rejected, it opens no
curation run at all, which is why the staging tests expect 8 runs across 9 covered pairs.

## Pairs that came out clean

FR-DE / movers (11, FIDI FAIM) · FR-DE / banks (4, BaFin — three re-sourced to institute
records on 2026-08-12) · FR-NO / movers (4) · FR-NO / housing_agencies (4, Finanstilsynet) ·
FR-NO / tax_finance (3) · FR-NO / banks (2).

## Registries used, and their acquisition mode

| registry | mode | note |
|---|---|---|
| FIDI FAIM | manual, evidenced | Per-affiliate pages. Strongest accreditation here — audited, numbered, 3-year renewal. |
| Finanstilsynet (NO) | HTTP lookup | One register serving estate agencies, auditors and banks. |
| BaFin (DE) | HTTP lookup | Per-institution licence records. Confirms the entity and its authorisations. |
| Brønnøysund (NO) | manual, evidenced | Government org numbers — a second identifier, not an accreditation. |
| EuRA | manual, evidenced | Association, not a statutory register. |
| hamburg.de Branchenbuch | manual, evidenced | Tier 2: confirms the entity exists, not professional standing. |
| IVD, FNAIM | **unavailable** | Login-gated / no public search. |
| RAK / BRAV, StBK | **unavailable** | Reachable, but form-search only — nothing linkable to cite. |
| IAM | **unavailable** | Directory moved to the IAMX platform on another domain; no per-entity URL confirmed. No row cites it. |

## What would actually unblock the remaining pairs

Not more harvesting. Three of the four blocked registers are readable by a human and simply not
addressable by URL, so the missing capability is a way to record *"a named person checked this
entry on this date"* as evidence, rather than a link. `supplier_accreditations` already models
the distinction — `status='claimed'` versus `'verified'`, the latter requiring `evidence_url`
and `verified_at`. A manual-verification path that satisfies that constraint would close
FR-DE/tax_finance and FR-DE/legal_admin without weakening the sourcing rule.

FR-DE/housing_agencies would not be closed by that, and probably cannot be: the register does
not exist.

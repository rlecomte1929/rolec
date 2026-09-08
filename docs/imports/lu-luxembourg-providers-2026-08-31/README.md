# Luxembourg City, Luxembourg — register-verified service providers (corridor XX-LU)

Sourced 2026-08-31. Every row is evidenced by an official statutory register or a
recognised accreditation body (the `source_url`), not the firm's own marketing site.
Firms not confirmable on a real register were excluded; one of six categories
(`legal_admin`) was **skipped** because its register has no citable per-entity page.

Total rows: **18** across **5** categories. **1** category skipped (`legal_admin`).

| category | n | register cited (per-entity URL) | tier |
|---|---|---|---|
| movers | 1 | FIDI Global Alliance affiliate finder (per-affiliate detail page) | 1 |
| banks | 5 | CSSF register of supervised entities (per-entity detail page) | 2 |
| schools | 4 | IBO — Find an IB World School (per-school page, IB code) | 2 |
| tax_finance | 4 | CSSF Public Register of the Audit Profession (per-firm page) | 2 |
| housing_agencies | 4 | Chambre Immobilière du Grand-Duché de Luxembourg — member directory (per-firm listing) | 2 |
| legal_admin | 0 | — SKIPPED (Barreau tableau has no per-entity URL) | — |

## Per-category detail

### movers — 1 firm
- **Register:** FIDI Global Alliance affiliate finder, filtered to Luxembourg
  (`https://www.fidi.org/find-fidi-affiliate?country=267`, Luxembourg = country id 267).
- **Verification:** the Luxembourg-filtered list returns exactly **one** affiliate,
  STREFF. Its per-affiliate detail page was fetched and confirms the official name
  **Albert Streff SARL et Cie SECS**, address 138 Route d'Arlon, Luxembourg, and a
  live **FIDI-FAIM** certification with **expiry 2029** (recorded in
  `accreditation_expiry`). FIDI shows no numeric affiliate id, so
  `accreditation_number` is blank.
- **Honest count:** FIDI lists only this single Luxembourg-registered affiliate — the
  task target of ~3-4 cannot be met from this register without inventing rows, so the
  category is reported at 1 rather than padded with non-Luxembourg affiliates.

### banks — 5 credit institutions
- **Register:** CSSF register of supervised entities (`searchentities` / `edesk.apps.cssf.lu`),
  the Commission de Surveillance du Secteur Financier's official list of authorised entities.
  `source_url` is the per-entity detail page `…/search-entities/entite/details/<id>`.
- **Verification:** each was queried against the CSSF register API
  (`/search-entities-api/api/v1/entite`) and confirmed as **entity type "B"**
  (établissement de crédit / credit institution, group B_1), active, with a Luxembourg-City
  registered address. `accreditation_number` = the CSSF register code (`B0000000x`).
  LEIs were also captured for reference:
  - BGL BNP Paribas — code B00000003, 60 av. J.F. Kennedy L-1855 — LEI `UAIAINAJ28P30E5GWE37`
  - Banque Internationale à Luxembourg — code B00000002, 69 route d'Esch L-1470 — LEI `9CZ7TVMR36CYD5TZBS50`
  - Banque de Luxembourg S.A. — code B00000008, 14 bd Royal L-2449 — LEI `PSZXLEV07O5MHRRFCW56`
  - Banque et Caisse d'Epargne de l'Etat, Luxembourg (Spuerkeess) — code B00000001 (group B_1_A, public establishment), 1 Place de Metz L-1930 — LEI `R7CQUF1DQM73HUTV1078`
  - ING Luxembourg — code B00000014, 26 Place de la Gare L-1616 — LEI `549300BT51N3KAXDPP56`
- The register is a React SPA; the detail-page URLs render the record client-side, and the
  underlying authoritative record is served by `…/search-entities-api/api/v1/entite/<id>`.

### schools — 4 IB World Schools (all in Luxembourg City)
- **Register:** IBO "Find an IB World School" — `https://www.ibo.org/en/school/<id>`.
  `accreditation_number` = the IB School code shown on the page.
  - International School of Luxembourg (ISL) — 000801 (Merl)
  - Athénée de Luxembourg — 004161 (Kirchberg)
  - Fräi-ëffentlech Waldorfschoul Lëtzebuerg — 002105
  - OTR International School — 061211 (7 Val Ste Croix, L-1371; IB World School since 2020)
- **Verification:** ibo.org serves a non-bypassable Cloudflare bot challenge to direct
  fetches (same behaviour noted in the Helsinki/FI batch), so each school's ibo.org register
  page + IB code was confirmed via ibo.org's own search-indexed pages, cross-checked against
  the international-schools-database IB filter for Luxembourg.
- **Excluded:** **St George's International School Luxembourg** — follows the British national
  curriculum (IGCSE / A-level), is **not** an IB World School, so it is not on the IBO register.

### tax_finance — 4 approved audit firms (réviseurs d'entreprises agréés)
- **Register:** CSSF **Public Register of the Audit Profession**
  (`https://audit.apps.cssf.lu`), which the CSSF administers for all *cabinets de révision
  agréés* (approved audit firms) — the successor to the former IRE register. `source_url` is
  the per-firm detail page `…/audit/details/company/<uid>`.
- **Verification:** each firm was queried against the register API
  (`/search-entities-api/api/v1/revext/aaf` list + `…/revext/firm/<uid>` detail) and confirmed
  **status = AGR** (agréé/approved), active, Luxembourg-City address:
  Deloitte Audit (uid 40, L-1821), KPMG Audit S.à r.l. (uid 122, L-1855),
  Ernst & Young (uid 42, L-1855), PricewaterhouseCoopers Assurance (uid 180, L-2182).
  The register shows no public licence number, so `accreditation_number` is left blank
  (status is AGR). Websites are taken from the register record.
- **Register choice:** the task permitted either the OEC (experts-comptables) directory or the
  Réviseurs d'entreprises / CSSF register; the CSSF audit register was used because it is a
  statutory register with stable, verifiable per-firm pages. Note the CSSF *supervised-entities*
  register (used for banks) does **not** list audit firms — this separate audit register does.

### housing_agencies — 4 real-estate agencies (all in Luxembourg City)
- **Register:** Chambre Immobilière du Grand-Duché de Luxembourg (CIGDL), the recognised
  professional body for the sector, member directory. `source_url` is the per-firm listing
  page `https://www.chambre-immobiliere.lu/listing/<slug>/`.
- **Verification:** each listing page was fetched and confirmed to carry the categories
  **`agence-immobiliere`** (real-estate agent) **and `membre-de-la-chambre`** (CIGDL member),
  and each firm's Luxembourg-City office was cross-checked:
  - Engel & Völkers Luxembourg — 4 Place Joseph Thorn, Luxembourg-Merl
  - Nexvia S.A. — 4 bd Royal, L-2449 Luxembourg
  - BARNES Luxembourg — 56 av. du Dix Septembre, L-2550 Luxembourg (Belair)
  - Unicorn — 18 rue du Marché-aux-Herbes, L-1728 Luxembourg (city centre)
- **Note:** Luxembourg real-estate agents hold an *autorisation d'établissement* from the
  Ministry of the Economy, but that permit has no public, per-firm searchable register; the
  CIGDL member directory (the recognised body, per the task) is the citable per-firm register.

### legal_admin — SKIPPED
- **Register attempted:** Barreau de Luxembourg (Ordre des Avocats) tableau / annuaire,
  `https://www.barreau.lu/annuaire`.
- **Why skipped:** the tableau is rendered as a client-side DataTable populated from a JSON
  dataset (WordPress `datajson` plugin) — there is **no per-lawyer or per-firm permalink**.
  The sitemap contains no `annuaire_avocat` entries and guessed per-firm URLs return 404; the
  only reachable URL is the search interface itself. The task requires a per-entity page and
  explicitly says to skip rather than cite a bare search URL, so `legal_admin` is skipped.

## Provenance / load status
Candidates only — nothing here is served to an employee until human vetting. Every row is
register-evidenced by its `source_url`; no numbers, ids, expiries or citations were invented
(fields the register does not expose are left blank).

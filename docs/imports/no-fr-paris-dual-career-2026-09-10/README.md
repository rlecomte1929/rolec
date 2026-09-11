# ReloPass Vendor Shortlist — Spouse/Partner Career Transition, Paris (NO→FR)

**Batch:** `no-fr-paris-dual-career-2026-09-10`
**Corridor:** NO-FR · **Service category:** spouse · **Compiled:** 2026-09-11

## Summary

Shortlist of career-transition service providers (bilan de compétences / career
coaching firms) domiciled in Paris, serving spouses/partners relocating on the
Norway→France corridor. EEA family members enjoy automatic work rights, so this
batch is scoped to **career-services vendors only** (not immigration/work-permit).

- **Accepted (official register verified): 5** — all confirmed at a SIRENE company
  record on `annuaire-entreprises.data.gouv.fr`.
- **Rejected: 5** — tier-3 (provider's own website only) or out-of-scope location.
- Target of ≥3 providers verified at an official register is **met (5/5 accepted are SIRENE-verified).**

## Accepted providers (all SIRENE-verified, Paris-domiciled)

| Company | SIREN | Arrondissement | SIRENE record |
|---|---|---|---|
| APERTIS CONSEIL | 811453265 | 75015 | annuaire-entreprises.data.gouv.fr/entreprise/apertis-conseil-811453265 |
| SARL STRATEGIE & COMPETENCES | 482271251 | 75009 | annuaire-entreprises.data.gouv.fr/entreprise/sarl-strategie-competences-482271251 |
| TRAINING COMPETENCES | 903530764 | 75017 | annuaire-entreprises.data.gouv.fr/entreprise/903530764 |
| ELYSEE FORMATIONS | 915096200 | 75015/75001 | annuaire-entreprises.data.gouv.fr/entreprise/elysee-formations-915096200 |
| FORMATION ET COMPETENCES | 428610869 | 75019 | annuaire-entreprises.data.gouv.fr/entreprise/formation-et-competences-428610869 |

## Provenance method

Official-provenance rule enforced: `source_url` must be an official register, not a
provider's own site. All accepted rows cite a **SIRENE** record on
`annuaire-entreprises.data.gouv.fr` (the government company register), which supplies
the legal name, SIREN/SIRET, registered address and NAF/APE activity code. No provider,
URL, SIREN, or accreditation number was invented. `website_url` is captured only as
a convenience field (may be blank); it is never used as the provenance source.

The `accreditation_body` is recorded as SIRENE with the SIREN as the identifier.
Qualiopi certificate numbers and expiry dates are **left blank** rather than guessed —
they were not machine-readably confirmed at the register (see access note).

## Honest note on directory-access issues

- **SIRENE HTML pages + JSON API (`recherche-entreprises.api.gouv.fr`,
  `annuaire-entreprises.data.gouv.fr`) returned empty via the scraper** (JS/app-shell
  gated). Official register data was instead recovered through the site's
  **Google-indexed record pages** (`site:annuaire-entreprises.data.gouv.fr`
  searches), whose snippets expose the register's own name/SIREN/address/NAF fields.
  Every SIREN above was read from an official annuaire record URL, not fabricated.
- **EMCC France coach directory** ("Chercher un coach") is a **JS/search-gated**
  interface; the public landing loaded but the searchable coach records did not.
  **Honest zero: no EMCC/ICF coach was verified at an accredited directory.**
- **Qualiopi register:** the `annuaire-entreprises.data.gouv.fr/lp/organisme-formation-qualiopi`
  landing exists but individual certificate numbers/expiries were not fetchable via
  the scraper, so those fields are blank rather than invented.

All accepted vendors carry `platform_vetting_status_all: pending` — human vetting and
Qualiopi certificate confirmation are the recommended next step.

# ReloPass vendor shortlist — Paris FLE language schools (Corridor NO->FR)

Batch: `no-fr-paris-language-2026-09-10`
Service category: `language`
Generated: 2026-09-11

## Summary
Shortlist of 6 accredited FLE (Français Langue Étrangère) schools in Paris offering
adult general French — suitable for an accompanying non-French-speaking spouse/family.

Accepted (6):
1. Alliance Française de Paris (75006)
2. Lutèce Langue (75007)
3. French As You Like It (75004, Le Marais)
4. Eurocentres Paris - Centres langues et civilisations (75006)
5. Language Studies International (LSI) - Centre privé de langues (75004)
6. ACCORD - Institut supérieur privé (75015)

Rejected (4): tier-3 / unverifiable — see rejects.csv.

## Provenance method (official register required)
Every accepted school is confirmed on the OFFICIAL Label Qualité FLE register — the
state quality label for FLE centres, operated by **France Éducation international** on
behalf of the French ministries.

Two official surfaces were used:
- **qualitefle.fr** centre directory pages (the label's own directory) — confirmed for
  Alliance Française de Paris, Lutèce Langue, French As You Like It, Eurocentres Paris,
  LSI, and ACCORD via `site:qualitefle.fr` official listing snippets and centre-page slugs.
- **data.education.gouv.fr** dataset "Centres et établissements labellisés Label qualité
  français langue étrangère" (publisher: France Éducation international; last modified
  2026-09-08; 111 records nationally, 18 in Paris). This is the machine-readable mirror
  of the same official label register.

`accreditation_body` = "Label Qualité FLE" for all accepted rows. A school's own website
was treated as tier-3 and NOT accepted as provenance.

## Honest note on directory-access issues
- **qualitefle.fr HTML is JS-gated**: direct `web_fetch` of centre pages returned empty
  text. Per the fallback protocol, the official listing was confirmed via Google
  `site:qualitefle.fr` search snippets (which expose the official directory) plus the
  France Éducation international government dataset API.
- **data.education.gouv.fr web pages are also JS-gated**, but its public Opendatasoft
  **JSON API** (`/api/explore/v2.1/...`) is reachable and was queried directly to
  enumerate the 18 Paris-labelled centres from the authoritative source.
- **accreditation_number / accreditation_expiry are BLANK by design**: the official
  Label Qualité FLE register does not publish a per-centre label/certificate number or an
  expiry date in either surface. Per the no-invention rule, these fields are left empty
  rather than fabricated. (An honest zero on those two fields, not the school list.)

## Files
- providers.csv — 6 accepted (sha256 in manifest.json)
- rejects.csv — 4 tier-3/unverifiable
- manifest.json — batch metadata + providers.csv sha256
- README.md — this file

platform_vetting_status_all: pending

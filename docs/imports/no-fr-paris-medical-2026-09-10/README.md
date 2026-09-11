# ReloPass Vendor Sourcing — Medical (GP / medecin traitant), Paris

- **Batch ID:** no-fr-paris-medical-2026-09-10
- **Corridor:** XX-FR (NO -> FR)
- **Service category:** medical
- **Accepted (providers.csv):** 0
- **Rejected (rejects.csv):** 2
- **platform_vetting_status_all:** pending

## Scope
Shortlist of medecins generalistes / GP practices in Paris that accept new
patients as *medecin traitant*, flagging English-speaking practices where the
official register indicates it. Only two provenance sources were permitted:

1. Conseil National de l'Ordre des Medecins — conseil-national.medecin.fr /
   tableau.ordre.medecin.fr (the "Tableau en ligne")
2. ameli.fr annuaire sante — annuairesante.ameli.fr

A clinic's own website is tier-3 and rejected. accreditation_body is always
"Ordre des Medecins". Per GDPR, only officially published practice/professional
inboxes would ever be recorded — never personal emails.

## Provenance method / access attempts
The following official-directory fetches were attempted with the platform
scraper:

- `annuairesante.ameli.fr/` — returned only the SPA shell text "Chargement…"
  (JavaScript loading spinner). No listing content rendered.
- `annuairesante.ameli.fr/professionnels-de-sante/recherche/liste?...` — same
  "Chargement…" shell; deep-link route is client-rendered.
- `api-annuairesante.ameli.fr/...` — returned no text (no accessible JSON).
- `tableau.ordre.medecin.fr/recherche-avancee` — returned no text at all
  (fully JS-gated).
- `tableau.ordre.medecin.fr/api/...` — real 404 Not Found (no crawlable API;
  endpoint not invented).
- `annuaire.esante.gouv.fr/...` — returned no text (JS-rendered).
- `conseil-national.medecin.fr/patient/trouver-medecin` — renders, but only
  explains the register and links out to the JS "Tableau en ligne"; it contains
  NO practice listings.
- Google `site:annuairesante.ameli.fr` returned only the directory root, no
  indexed per-doctor/per-practice pages.

## HONEST ZERO note
No specific, verifiable GP practice listing could be retrieved from either
official register because both (and the esante.gouv.fr annuaire) are
JavaScript-rendered single-page applications that are search-gated and serve no
listing content to a text scraper. There is no crawlable server-rendered or
JSON endpoint reachable here. In accordance with the absolute rules, **no
doctor, practice, URL, or registration number was invented**, so
`providers.csv` contains the header only (accepted_count = 0). Retrieving
verified entries would require a headless/JS-capable browser session against
the Ordre's Tableau en ligne or the ameli annuaire sante, or an official data
export.

## rejects.csv
Contains tier-3 / non-official candidates that surfaced in general web search
(a hospital-owned directory and a non-official info portal). These are recorded
for transparency and are NOT valid provenance.

## Files
- providers.csv (accepted; header only)
- rejects.csv (tier-3 / unverifiable candidates)
- manifest.json
- README.md

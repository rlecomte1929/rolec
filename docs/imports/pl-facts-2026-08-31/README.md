# PL third-country-national facts — 2026-08-31

Non-obvious, official-government-sourced immigration/relocation facts for a **third-country
national (non-EEA) professional relocated by their employer to Poland** (hub: Warsaw).

- **Perspective nationality:** `non-EEA` · **status:** `professional` · **corridor:** `PL`
- **Facts:** 13 (all with a verbatim official quote)
- **Rule applied:** only facts that would NOT also apply to an EU/EEA citizen (single/blue-card
  permits, employer-obtained work permit, residence card, non-EU driving-licence exchange, etc.).
  Generic rules that apply identically to EU workers (e.g. plain ZUS registration, the 183-day
  tax-residency test, generic NFZ registration) were deliberately **excluded**, per the brief's
  "not-also-EU" constraint. That is why SOCIAL_SECURITY and TAX-style facts are absent.

## Pillar distribution
RESIDENCE 6 · IDENTITY 2 · EMPLOYMENT 2 · TIMELINE 1 · HEALTHCARE 1 · HOUSING 1

## Sources (official government only) + grounding method

| # | fact_key | source_url | grounding |
|---|----------|-----------|-----------|
| 1 | single_permit:one_document_residence_and_work | mos.cudzoziemcy.gov.pl …/permit-uniform/ | browser-read (verbatim) |
| 2 | single_permit:no_automatic_renewal_apply_before_expiry | mos.cudzoziemcy.gov.pl …/permit-uniform/ | browser-read (verbatim) |
| 3 | single_permit:must_apply_while_in_poland | mos.cudzoziemcy.gov.pl …/permit-uniform/ | browser-read (verbatim) |
| 4 | single_permit:personal_signature_not_employer | mos.cudzoziemcy.gov.pl …/permit-uniform/ | browser-read (verbatim) |
| 5 | residence_permit:sworn_polish_translation_required | mos.cudzoziemcy.gov.pl …/permit-uniform/ | browser-read (verbatim) |
| 6 | work_permit:obtained_by_employer | mos.cudzoziemcy.gov.pl …/doing-the-job/principles-general/ | browser-read (verbatim) |
| 7 | work_authorization:visa_or_permit_must_allow_work | mos.cudzoziemcy.gov.pl …/doing-the-job/principles-general/ | browser-read (verbatim) |
| 8 | eu_blue_card:eu_mobility_and_faster_long_term_status | mos.cudzoziemcy.gov.pl …/blue-card/ | browser-read (verbatim) |
| 9 | eu_blue_card:granted_for_work_period_plus_three_months | mos.cudzoziemcy.gov.pl …/blue-card/ | browser-read (verbatim) |
| 10 | health_insurance:required_condition_for_permit | mos.cudzoziemcy.gov.pl …/blue-card/ | browser-read (verbatim) |
| 11 | residence_card:multiple_border_crossings_without_visa | mos.cudzoziemcy.gov.pl …/documents-op3/residence-card/ | browser-read (verbatim) |
| 12 | residence_card:first_card_issued_ex_officio | mos.cudzoziemcy.gov.pl …/documents-op3/residence-card/ | browser-read (verbatim) |
| 13 | driving_licence:non_convention_licence_theory_exam | www.gov.pl/web/gov/wymien-zagraniczne-prawo-jazdy-na-polskie | **WebFetch (server-side fetch)** — see note |

`mos.cudzoziemcy.gov.pl` = Moduł Obsługi Spraw (Case Handling Module) run by the **Office for
Foreigners / Ministry of Interior and Administration** — the official English-language procedure
portal. `gov.pl` = national government portal.

### Grounding notes / limitations
- **Facts 1–12 are browser-confirmed:** each `evidence_quote` was copied from the live page text
  read in the browser (`get_page_text` on `mos.cudzoziemcy.gov.pl`). Verbatim, including source
  typos (e.g. "because combines"), curly apostrophes and dashes.
- **Fact 13 (driving licence) is WebFetch-grounded, not browser-confirmed.** The `gov.pl` /
  `obywatel.gov.pl` SPA deep-links redirect to the portal homepage inside the shared browser
  pane, so the page could not be read there. The Polish quote was obtained via a server-side
  WebFetch of the exact `gov.pl` URL with an instruction to copy the substring
  character-for-character. Confidence is high (it matches known obywatel.gov.pl phrasing) but it
  was not re-read in the browser. Flag for a quick re-check on promotion if desired.

### Sources opened but NOT used
- `udsc.gov.pl/en/...` deep links (Office for Foreigners English site) — **redirect** to the
  Polish `gov.pl/web/udsc` homepage via both browser and WebFetch; English deep content
  unreachable. The equivalent content was sourced from `mos.cudzoziemcy.gov.pl` instead.
- `www.gov.pl/web/udsc-en/*` FAQ pages — reachable via WebFetch but too thin (one-line FAQ
  answers); no usable non-obvious quotes.
- Single-permit **minimum remuneration (PLN)** figure — the MOS "Requirements" block is
  collapsed/JS-gated and the `wymogi_EN` URL 404'd; no clean verbatim number could be captured,
  so **no wage/fee fact was written** (numbers were not invented).
- Generic ZUS (`zus.pl`), NFZ (`nfz.gov.pl`) and 183-day tax-residency (`podatki.gov.pl`) pages
  were reviewed but their rules apply equally to EU workers, so they were excluded under the
  not-also-EU constraint. (The one health fact kept, #10, is a TCN-specific *permit condition*.)

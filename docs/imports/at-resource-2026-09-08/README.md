# at-resource-2026-09-08 — re-source clearing a held fact

**Clears:** punch-list hold *"Austria — EU-registration late fine (€250)"* (the figure was not on
the read `oesterreich.gv.at` page; the strictly-statutory `ris.bka.gv.at` is CAPTCHA-walled).

**Landed:** AUSTRIA · RESIDENCE · 1 `requirement_item`, `review_status='pending'` (append-only).

## Fact
- key: `AT:residence:anmeldebescheinigung_deadline_fine`
- title: Register within 4 months — late registration is fined
- pillar / nationality: RESIDENCE / **EEA** (scoped `["EU_EEA"]` — this is an EU free-mover
  registration duty, so it must never reach an EEA national's OWN_NATIONAL class)
- source: https://www.wko.at/wirtschaftsrecht/gemeinschaftliches-niederlassungsrecht
- quote: "Die nicht rechtzeitige Beantragung einer Anmeldebescheinigung stellt eine
  Verwaltungsübertretung dar und ist mit Geldstrafe von 50 EUR bis zu 250 EUR …"

## Verification
`confirm_quotes.py` → **CONFIRMED** (1.0 bigram, exact). `wko.at` (Wirtschaftskammer Österreich, a
public-law chamber) restates NAG §77 verbatim including the exact fine; added to
`_SEMI_OFFICIAL_HOSTS` in `parsers.py` for the same reason as citizensinformation.ie / borger.dk —
a public-law body restating statute belongs in the review queue.

## Note on the promote sweep
`promote(country=AT)` is country-scoped, so it also swept in a stranded `AT-immig-2026-08-12`
staging batch (8 cited immigration facts — Red-White-Red Card route, EU Blue Card, EU registration)
that had sat `ready` and un-promoted for ~4 weeks. All 8 are cited + `pending`; AUSTRIA went 2→11.
Beneficial (more pending coverage for the human gate), not corruption — nothing served was touched.

## Append-only
approved count unchanged (325), expert_verified 0, nationality scope guard green.

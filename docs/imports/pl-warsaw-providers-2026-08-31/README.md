# Warsaw, Poland — verified service providers (corridor XX-PL)

Sourced 2026-08-31. Every row is evidenced by an **official statutory register or recognized
accreditation body**, browser-grounded (register opened and the listing confirmed), never the
firm's own marketing site. Firm websites appear only in `website_url`; the `source_url` is always
the register.

`corridor` = `XX-PL` on every row (destination Poland / Warsaw; origin unspecified).

## Per-category summary

| service_category | rows | register used | notes |
|---|---|---|---|
| movers | 3 | FIDI Global Alliance — Find a FIDI Affiliate (FAIM) | per-affiliate detail pages |
| banks | 5 | KNF — Wyszukiwarka podmiotow (register of supervised entities) | ECB list N/A (see below) |
| schools | 4 | International Baccalaureate — Find an IB World School | IBO school id cited |
| housing_agencies | 0 | — | **SKIPPED** — no statutory register (see below) |
| legal_admin | 3 | Krajowy Rejestr Adwokatow (Polish Bar) — rejestradwokatow.pl | per-lawyer entries |
| tax_finance | 4 | PANA — Lista firm audytorskich (STREFA register) | per-firm register number |

Total: **19 rows across 5 categories; 1 category skipped.**

## movers (3) — FIDI / FAIM
Register: https://www.fidi.org/find-fidi-affiliate — each row cites the per-affiliate DETAIL page.
- AGS Warsaw Sp. z o.o. (AGS Poland) — Warsaw — FIDI-FAIM Plus, expiry 2026 — /find-fidi-affiliate/ags-poland
- MK Relocation Sp. z o.o. — Warsaw — FIDI-FAIM, expiry 2026 — /find-fidi-affiliate/mk-relocation
- Master Moving Sp. z o.o. — Krakow (Poland office) — FIDI-FAIM, expiry 2028 — /find-fidi-affiliate/master-moving-poland

Note: a fourth Poland affiliate, "Santa Fe Relocation - Warsaw" (/find-fidi-affiliate/santa-fe-relocation-warsaw),
was EXCLUDED: its FIDI detail page returns "Access denied / You are not authorized to access this
page", so the listing could not be confirmed on the register. Master Moving (Krakow) is included as
the third confirmed affiliate under the "Warsaw/Poland office" rule.

## banks (5) — KNF
Register: KNF "Wyszukiwarka podmiotow" (searchable register of supervised entities), knf.gov.pl.
Each row cites the server-rendered `?searchPhrase=...` result URL where the bank was confirmed.
Confirmed present, all supervised by KNF:
- Powszechna Kasa Oszczednosci Bank Polski S.A. (PKO BP) — Warszawa
- Bank Polska Kasa Opieki S.A. (Bank Pekao)
- Santander Bank Polska S.A. — Warszawa
- mBank S.A.
- ING Bank Slaski S.A.

ECB note: the ECB "list of supervised entities" was NOT usable — Poland is outside the euro area /
Single Supervisory Mechanism, so Polish commercial banks do not appear in an ECB "Poland section".
KNF is the correct national statutory supervisor and register.

## schools (4) — IB World Schools
Register: https://www.ibo.org/en/school/<id> ("Find an IB World School"). ibo.org is
Cloudflare-protected (blocks server fetch); confirmed via a real browser after the challenge cleared.
- American School of Warsaw — IB id 000721 (DP/MYP/PYP)
- The British School Warsaw — IB id 001285 (DP)
- International American School Warsaw — IB id 003087 (DP)
- The Canadian School of Warsaw — IB id 005004 (DP)

## legal_admin (3) — Polish Bar
Register: Krajowy Rejestr Adwokatow i Aplikantow Adwokackich (rejestradwokatow.pl). This is a
per-advocate statutory register with citable profile URLs `/adwokat/<name>-<id>`. The search form is
reCAPTCHA-gated, but individual profile pages are server-rendered and directly verifiable. All three
are Izba Adwokacka w Warszawie, status "Wykonujacy zawod" (practicing), relevant to relocating
professionals (labour / foreigners law):
- Schiffter Karolina Anna — WAW/Adw/4150 — Warszawa — prawo pracy (employment/immigration; Fragomen/PCS)
- Dalkowski Piotr Tytus — WAW/Adw/2267 — Warszawa — incl. prawo pracy
- Blonski Tomasz Wiktor — WAW/Adw/8564 — Warszawa — foreigners/immigration (adwokatblonski.pl)

`website_url` left blank where the firm's exact domain could not be confirmed (source register is the
required evidence). The National Chamber of Legal Advisers (KIRP, radcowie prawni) is an equally valid
alternative register and can be mined the same way for more capacity.

## tax_finance (4) — PANA audit-firm register
Register: PANA "Lista firm audytorskich" via the STREFA system (strefa.pana.gov.pl/wyszukiwarka/).
This is a per-firm statutory register with a registration number ("numer na liscie firm audytorskich").
Firm name + number confirmed directly against the register's own data
(GET /wyszukiwarka/api/organizations?fullName.contains=...). All are the Big-4 statutory-audit
entities (spolka komandytowa), Warsaw-headquartered:
- Deloitte Audyt sp. z o.o. sp.k. — no. 73
- Ernst & Young Audyt Polska sp. z o.o. sp.k. — no. 130
- PricewaterhouseCoopers Polska sp. z o.o. Audyt sp.k. — no. 144
- KPMG Audyt sp. z o.o. sp.k. — no. 3546

Alternative/complementary register: KIDP (Krajowa Izba Doradcow Podatkowych) — per-person register of
tax advisers (doradcy podatkowi) — for individual tax-adviser capacity.

## SKIPPED — housing_agencies (re-source worklist)
SKIPPED. Poland deregulated the estate-agent profession effective **1 January 2014**: mandatory
licensing was abolished and there is **no statutory public register with per-firm entries** for real
estate agents/agencies. Agents need only professional civil-liability insurance; no central official
licence list exists. Per the task rules, self-declared firm sites and trade-association member lists
are not acceptable substitutes, so the category is skipped rather than filled.

Re-source options if this category is later required:
- Trade bodies exist (e.g. PFRN — Polska Federacja Rynku Nieruchomosci and its voluntary licence
  register) but membership is **voluntary**, not a statutory register — use only with an explicit
  caveat that it is not an official licence list.
- The mandatory OC (civil-liability) insurance is verifiable per-agent only via the insurer, not a
  public register.

## Verification method / caveats
- FIDI, IB, KNF, PANA/STREFA and the Polish Bar were each opened live and the specific listing read
  back (browser for JS/Cloudflare-gated registers; isolated server-fetch for server-rendered result
  URLs). No accreditation number or expiry was written unless shown on the register (FAIM expiry
  years from the FIDI detail page; register numbers from STREFA; bar numbers from the advocate
  profile; IB ids from the school page). KNF entries carry no per-bank licence number or expiry, so
  those fields are blank.
- The shared research browser was heavily contended by parallel agents; where a register exposed a
  server-rendered result URL or JSON API, that isolated path was used to confirm the same data.

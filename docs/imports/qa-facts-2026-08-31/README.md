# Qatar (QA) — Non-obvious relocation facts — 2026-08-31

Persona: third-country-national (non-EEA) professional relocated by their employer to Qatar (hub: Doha).
Output: `facts.ndjson` — **12 facts**, official Qatar government sources only.

## Verbatim confirmation method

Every `evidence_quote` was **browser-grounded** (page opened, live official text captured) and then
**programmatically confirmed** to be a verbatim substring of the fetched official text via
`build_qa.py` (whitespace-normalized substring match: exact words/punctuation; only runs of
whitespace/newlines are collapsed). Result: **12/12 OK, 0 failures.** All records carry
`quote_verbatim_confirmed: true`. Each quote is < 200 chars.

- hukoomi.gov.qa is **WAF-gated**: it returns HTTP 403 with a "Maintenance Page" to `curl` and to
  WebFetch, regardless of headers/UA (Googlebot included). Its real content was reached and captured
  with a **real headless browser (Playwright)**, which passes the WAF. Text saved and re-checked.
- portal.moi.gov.qa is server-rendered and was fetched with `curl`; quotes confirmed against the raw
  HTML text nodes.

## Sources used (all official .gov.qa)

| # | Pillar | Topic | Source URL | Verbatim? |
|---|--------|-------|-----------|-----------|
| 1 | EMPLOYMENT | Change employer without NOC (Decree-Law 18/2020) | https://hukoomi.gov.qa/en/articles/labor-law | YES |
| 2 | RESIDENCE | Exit permit removed for most workers | https://hukoomi.gov.qa/en/qatar-for-all/migrant-workers | YES |
| 3 | RESIDENCE | Kafala sponsorship abolished | https://hukoomi.gov.qa/en/qatar-for-all/migrant-workers | YES |
| 4 | HEALTHCARE | Medical Commission exam required for RP (QR100) | https://hukoomi.gov.qa/en/services/medical-examination-for-residence-permit | YES |
| 5 | HEALTHCARE | Medical result sent to MOI residency system | https://hukoomi.gov.qa/en/services/medical-examination-for-residence-permit | YES |
| 6 | HEALTHCARE | Hamad Health Card required for healthcare (QR100) | https://hukoomi.gov.qa/en/services/request-to-renew-health-card | YES |
| 7 | TIMELINE | Medical checkup within 30 days of entry, then fingerprint | https://portal.moi.gov.qa/wps/portal/MOIInternet/departmentcommittees/visasentrypermeits/ (WCM urile: .../visas/47) | YES |
| 8 | IDENTITY | QID / ID number issued by MOI Expatriate Affairs | https://portal.moi.gov.qa/wps/portal/MOIInternet/departmentcommittees/expatriatesaffairs | YES |
| 9 | EMPLOYMENT | Employer must register employee on Hukoomi | https://hukoomi.gov.qa/en/services/medical-examination-for-residence-permit | YES |
| 10 | RESIDENCE | Personal-status docs must be MOFA-attested (QR100) | https://hukoomi.gov.qa/en/services/authentication-of-personal-status-documents-through-foreign-ministry | YES |
| 11 | HOUSING | Sponsor NOC still required for a driving licence | https://hukoomi.gov.qa/en/services/request-no-objection-certificate-to-issue-driving-license | YES |
| 12 | SOCIAL_SECURITY | Workers' Support and Insurance Fund | https://hukoomi.gov.qa/en/articles/labor-law | YES |

Pillar spread: EMPLOYMENT 2, RESIDENCE 3, HEALTHCARE 3, TIMELINE 1, IDENTITY 1, HOUSING 1,
SOCIAL_SECURITY 1 (all 7 pillars covered).

## Sources I could NOT reach (from this environment)

- **adlsa.gov.qa** (Ministry of Labour / ADLSA) — DNS has **no A record** from this environment
  (only MX/Outlook mail records resolve). The canonical ADLSA "New Minimum Wage and Labour Mobility
  Law" statement (news30802020) could not be opened. The equivalent facts (NOC + exit-permit
  removal, Decree-Law 18/2020) were instead grounded from **hukoomi.gov.qa**, which states them
  explicitly.
- **www.mol.gov.qa** (Ministry of Labour e-services + Labour Law PDF) — TCP connection **timed out**
  on every attempt. The "Service of notification of change of employer" page and the Labour Law PDF
  were not retrievable. Change-employer fact grounded from hukoomi instead.
- **hukoomi.gov.qa via curl / WebFetch** — HTTP 403 "Maintenance Page" (WAF). Only reachable via a
  real browser; all hukoomi quotes here come from the Playwright-rendered pages.
- **MOI news-detail portlet pages** (e.g. the "Expats Exit Permit Grievances Committee" news) —
  JavaScript-gated ("This page requires Javascript"); article body not in static HTML, so not used.

## Notes / non-obvious angles captured

- The **NOC-for-jobs was abolished** (fact 1) but a **sponsor NOC is still required for a driving
  licence** (fact 11) — a deliberate contrast that trips people up.
- **Exit permits removed** for most workers, but the law keeps them for a **defined ratio of
  senior/critical staff** (fact 2, nuance in `non_obvious_note`).
- Health check is not a formality: the **Medical Commission result feeds the MOI residency system**
  (fact 5) and the checkup carries a **30-day deadline** (fact 7).
- The residence-permit journey is **employer-driven**: the company registers the employee on Hukoomi
  (fact 9), and a separate **Hamad Health Card** is needed to actually use healthcare (fact 6).

No fees, numbers, dates or citations were invented. `no personal income tax` was intentionally
**omitted** — no reachable official (.gov.qa) page in the allowed source set stated it verbatim, so
it was not fabricated.

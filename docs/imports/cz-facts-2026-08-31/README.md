# CZ third-country-national facts — 2026-08-31

Non-obvious, official-government-sourced immigration/relocation facts for a **third-country
national (non-EEA) professional relocated by an employer to the Czech Republic** (hub: Prague).
Czechia is EEA, so every fact below is written to apply ONLY to third-country nationals — none of
them applies to an EU/EEA free mover.

- **Facts:** 12 (`facts.ndjson`)
- **Perspective:** `nationality = non-EEA`, `status = professional`, `corridor = CZ`
- **All `evidence_quote` values were confirmed as VERBATIM substrings** of the fetched official
  text (each < 200 chars). `quote_verbatim_confirmed = true` on every record.

## Source-domain note (important)

The Ministry of the Interior pages under `mvcr.cz` / `mv.gov.cz` now **301/307-redirect** their
English foreigner content to the government's **Official Web Portal for Foreigners**, which itself
moved `frs.gov.cz` → **`ipc.gov.cz`** (Integration Portal for Foreigners, operated by the Czech
Ministry of the Interior). `ipc.gov.cz` is a `gov.cz` official government portal and is the current
authoritative primary for these topics — it is where `mvcr.cz`/`mv.gov.cz` send readers. All facts
are cited to `ipc.gov.cz`.

## Sources (all fetched & quote-confirmed)

| # | Topic | URL | Verbatim confirmed |
|---|-------|-----|---|
| 1,2,3,4,5 | Employee Card | https://ipc.gov.cz/en/visa-and-residence-permit-types/third-country-nationals/long-term-residence-permits/employee-card/ | yes (browser page text) |
| 6,7,8 | EU Blue Card | https://ipc.gov.cz/en/visa-and-residence-permit-types/third-country-nationals/long-term-residence-permits/blue-card/ | yes (browser page text) |
| 9 | Address registration (Foreign Police, 3 working days) | https://ipc.gov.cz/en/obligations-for-foreigners/registration-after-arrival/ | yes (browser page text) |
| 10 | Biometric residence card | https://ipc.gov.cz/en/administrative-proceedings/biometrics/ | yes (browser page text) |
| 11 | Travel/comprehensive medical insurance (min EUR 400,000) | https://ipc.gov.cz/en/forms-and-documents/documents/medical-insurance/ | yes (browser page text) |
| 12 | Adaptation & Integration Course | https://ipc.gov.cz/en/obligations-for-foreigners/adaptation-integration-courses/ | yes (browser page text) |

## Pillar coverage

RESIDENCE ×6, EMPLOYMENT ×3, HOUSING ×1, IDENTITY ×1, HEALTHCARE ×1. (No IMMIGRATION/TAX/FAMILY.)

## Corrections caught during sourcing

- **90 days, not 60.** Older archived MVČR copy stated 60 days to find new employment after a job
  ends on an Employee Card. The current `ipc.gov.cz` page states **90 days** — used the live figure.
- **Blue Card end-of-employment reporting is 3 working days**, distinct from the Employee Card's
  90-day new-job window (both verbatim-confirmed on their respective live pages).

## Topics deliberately NOT included (and why)

- **Public health insurance participation, social-security contributions, income-tax residency
  (183 days).** These were on the requested topic list, but for an employee under a Czech contract
  they apply **identically to EU citizens**, which violates the hard "write ONLY facts that would
  NOT also apply to an EU citizen" rule. The one health fact kept (#11, commercial insurance min
  EUR 400,000 until public cover starts) is genuinely third-country-specific — the source page
  itself states the requirement differs by whether you are an EU citizen. `cssz.cz`, `vzp.cz` and
  `financnisprava.cz` were reviewed but yielded no clean TCN-*exclusive* fact with a verbatim quote.

## Unverifiable / dropped

- None shipped. Every included fact has a verbatim quote confirmed against live official page text.
- `mvcr.cz` / `mv.gov.cz` English article pages (e.g. `employee-card-682810.aspx`, `eu-blue-cards`)
  now redirect to placeholder/pointer pages and no longer carry the substantive text — they point to
  `ipc.gov.cz`, which is what was quoted.

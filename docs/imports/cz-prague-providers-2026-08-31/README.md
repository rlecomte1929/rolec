# Prague, Czech Republic — verified service providers (corridor XX-CZ)

Sourced 2026-08-31. Every row is evidenced by an **official statutory register or recognized
accreditation body**, confirmed by direct fetch of the register record — never the firm's own
marketing site. Firm websites appear only in `website_url`; the `source_url` is always the register.

`corridor` = `XX-CZ` on every row (destination Czech Republic / Prague; origin unspecified).

## Per-category summary

| service_category | rows | register used | notes |
|---|---|---|---|
| movers | 1 | FIDI Global Alliance — Find a FIDI Affiliate (FAIM) | 2 further CZ affiliates excluded (see below) |
| banks | 6 | ČNB — Seznam regulovaných a registrovaných subjektů (JERRS) | per-entity deep link is CAPTCHA-gated; register page cited |
| schools | 4 | International Baccalaureate — Find an IB World School | IBO school id cited per row |
| legal_admin | 3 | Česká advokátní komora — Vyhledávání advokátů | per-advocate detail pages + evidenční číslo |
| tax_finance | 4 | Komora auditorů ČR — Rejstřík auditorů | per-firm detail page + evidence number |
| housing_agencies | 4 | Živnostenský rejstřík (RŽP) via ARES | per-firm record; vázaná živnost "Realitní zprostředkování" |

**Total: 22 rows across 6 categories; 0 categories skipped.**

## movers (1) — FIDI / FAIM
Register: https://www.fidi.org/find-fidi-affiliate — each row cites the per-affiliate DETAIL page.
- AGS International Movers spol. s r.o. — Prague 6 — FIDI-FAIM Plus, expiry 2026 —
  /find-fidi-affiliate/ags-international-movers (detail page returns HTTP 200, confirmed via direct fetch).

**EXCLUDED (2), per the register-verifiability rule:** the Czech Republic has exactly three FIDI
affiliate detail pages (AGS, Santa Fe Prague, Voerman Czech). The other two could **not** be
confirmed on the register:
- `santa-fe-relocation-prague` — detail page returns "Error — You are not authorized to access this
  page" (HTTP 403 on direct fetch, and "Access denied | FIDI" in a browser). Same behaviour as the
  Warsaw batch's Santa Fe exclusion.
- `voerman-czech` — detail page returns HTTP 403 / access denied; secondary sources indicate its FAIM
  lapsed (last audit 2011, expiry noted as 2023), consistent with a de-listed/restricted page.
AGS's page, fetched with the same tooling, returns 200 with full data — so the 403s are page-specific
access restrictions, not a blanket bot block. Excluded rather than cite an unverifiable page.

## banks (6) — ČNB
Register: ČNB "Seznamy regulovaných a registrovaných subjektů (JERRS)", cnb.gov —
https://www.cnb.cz/cs/dohled-financni-trh/seznamy/jerrs (302-redirects to the JERRS application at
jerrs.cnb.cz). The JERRS search/entity-detail pages are **CAPTCHA-gated**, so a stable per-bank deep
link cannot be cited; the ČNB register page is cited on every bank row (as the task permits — "Cite
the ČNB page"). Czechia is outside the euro area / SSM, so — as with Poland/KNF — the ECB list of
supervised entities does not apply; ČNB is the correct national statutory supervisor and register.
Rows are the six banks named in the task, all long-standing ČNB-licensed banks / credit institutions:
- Československá obchodní banka, a. s. (ČSOB)
- Komerční banka, a.s.
- Česká spořitelna, a.s.
- UniCredit Bank Czech Republic and Slovakia, a.s.
- Raiffeisenbank a.s.
- MONETA Money Bank, a.s.

## schools (4) — IB World Schools
Register: https://www.ibo.org/en/school/<id> ("Find an IB World School"). ibo.org is
Cloudflare-protected (blocks server fetch — HTTP 403), but each /en/school/<id> page is indexed with
its school title, which confirms the id↔school mapping; ids below are the ones the register returns.
- International School of Prague, s.r.o. — IB id 000889 — Prague
- Prague British International School — IB id 001042 — Prague (Nord Anglia)
- Park Lane International School — IB id 052209 — Prague 1
- The English College in Prague - Anglické gymnázium, o.p.s. — IB id 000821 — Prague 9

## legal_admin (3) — Czech Bar Association
Register: Česká advokátní komora — "Vyhledávání advokátů a koncipientů" (cak.cz/vyhledavani-advokatu;
the task's `vyhledavani.cak.cz` host does not resolve — the live search is on `www.cak.cz`). The
search is **not** CAPTCHA-gated and produces stable per-advocate detail pages
`/advokat-detail/<UUID>`. Each row below was individually fetched and confirmed: active
("Aktivní"), Prague seat, evidenční číslo as shown. These are register-verified Prague advocates
(general practice; specialization was not filtered).
- JUDr. Martin Abraham (advokát) — reg. 12531 — Pernerova 676/51, Praha
- Mgr. Jiří Absolon (advokát) — reg. 14406 — Na příkopě 988/31, Praha
- Mgr. Maruan Abu Assad (advokát) — reg. 10814 — Na Větrníku 1493/73, Praha

## tax_finance (4) — Chamber of Auditors (KA ČR)
Register: Komora auditorů České republiky — "Rejstřík auditorů / auditorských společností"
(kacr.cz/vyber-auditora). Each firm has a stable per-firm detail page
`kacr.cz/detail-auditora?nGoodsID=<id>` carrying its evidence number (evidenční číslo, 3-digit for
audit companies). All four confirmed via direct fetch as registered auditing companies (auditorská
společnost) with a Prague seat:
- Deloitte Audit s.r.o. — evidence 079 — Praha 2 — nGoodsID=1754
- Ernst & Young Audit, s.r.o. — evidence 401 — Praha 1 — nGoodsID=1982
- PricewaterhouseCoopers Audit, s.r.o. — evidence 021 — Praha 4 — nGoodsID=1728
- KPMG Česká republika Audit, s.r.o. — evidence 071 — Praha 8 — nGoodsID=1748

## housing_agencies (4) — Trade Register (RŽP)
Register: since the 2020 Real Estate Brokerage Act, real-estate agents hold the bound trade (vázaná
živnost) "Realitní zprostředkování" recorded in the Živnostenský rejstřík (RŽP). The RŽP portal
(rzp.gov.cz) is a JavaScript app with no citable per-firm URL, so each row cites the **official ARES
record** (ares.gov.cz, Ministry of Finance — the government's canonical public interface to the RŽP):
the REST endpoint `ekonomicke-subjekty-rzp/<IČO>`, which was fetched directly and shows an **active**
"Realitní zprostředkování" trade with `druhZivnosti = "V"` (vázaná / bound). `accreditation_number` =
IČO. Human-facing equivalent: https://ares.gov.cz/ekonomicke-subjekty?ico=<IČO>.
- SVOBODA & WILLIAMS s.r.o. — IČO 27588785 — Praha 6 (trade from 2021-03-15)
- LEXXUS NORTON a.s. — IČO 26208024 — Praha 1 (trade from 2020-12-23)
- MAXIMA REALITY, s.r.o. — IČO 25149610 — Praha (trade from 2021-01-18)
- Česká EuV Commercial s.r.o. (Engel & Völkers Prague) — IČO 27533328 — Praha 5 (trade from 2020-11-09)

## Method / integrity notes
- Every `source_url` is a register/accreditation page, not a firm marketing site. `website_url` holds
  the firm's own site only.
- No accreditation numbers, ids, or expiries were invented. Blank = not shown on the register (banks:
  no per-entity number surfaced; IB/CAK/KAČR: id/number as displayed; housing: expiry N/A for an
  open-ended bound trade).
- Registers that block automated fetch were handled honestly: FIDI 403 pages were **excluded** (not
  guessed); ibo.org 403s were resolved via the register's indexed school pages; ČNB CAPTCHA gating is
  disclosed and the register page cited per the task.

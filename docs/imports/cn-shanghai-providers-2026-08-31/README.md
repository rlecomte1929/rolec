# Shanghai (China) service providers — register-verified sourcing (2026-08-31)

Corridor tag: `XX-CN` (destination = Shanghai, China). Every row is evidenced by an official
statutory register or recognized accreditation body — the `source_url` is the register page,
**not** the firm's own marketing site. Firms not confirmable on a register were excluded, and
three categories were skipped rather than sourced from self-declared firm sites.

`providers.csv` header:
`corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry`

## Counts

| category | rows | register used | status |
|---|---|---|---|
| movers | 4 | FIDI Global Alliance — FAIM affiliate register (per-affiliate detail pages) | done |
| banks | 4 | PBOC & NFRA — Systemically Important Banks list (pbc.gov.cn, 2023) | done |
| schools | 4 | IB — Find an IB World School (ibo.org, per-school pages) | done |
| legal_admin | 0 | Shanghai Judicial Bureau / ACLA lawyer-firm lookup | SKIPPED |
| tax_finance | 0 | CICPA accounting-firm register (cicpa.org.cn) | SKIPPED |
| housing_agencies | 0 | Shanghai 网上房地产 real-estate-agency portal | SKIPPED |

Total: 12 rows across 3 categories.

## Per-category notes

### movers — FIDI Global Alliance (FAIM)
Register: `fidi.org/find-fidi-affiliate`. Each row cites the per-affiliate **detail** page
(`fidi.org/find-fidi-affiliate/<slug>`), not the country-filter search URL. All four are
FIDI-FAIM certified with a Shanghai, China office confirmed on the detail page (address +
legal name). `accreditation_expiry` is the FAIM certification expiry year shown on the detail
page. Legal names and Shanghai addresses were read directly off each FIDI detail page.

- AGS Four Winds International Transport Service (Shanghai) Co., Ltd. — Jing'an, Shanghai — FAIM to 2026
- Asian Tigers K. C. DAT (China) Ltd — Changning District, Shanghai — FAIM to 2026
- Asia United Group Shanghai Co. Ltd (UniGroup Worldwide) — Jing'an, Shanghai — FAIM to 2027
- AMR International Relocation — Xuhui District, Shanghai — FAIM to 2027

Excluded: **Santa Fe Relocation - Shanghai** (Sino Santa Fe) — its FIDI detail page shows a
FAIM validity of 2023 (lapsed / not current), so it was left out despite being a real Shanghai
office. Re-check its detail page for a renewed FAIM before adding.

### banks — PBOC & NFRA Systemically Important Banks list
The per-firm licence register is the NFRA financial-licence query at `xkz.nfra.gov.cn/jr/`
(金融许可证信息查询). It is an Ext-JS query application that **requires a CAPTCHA (验证码)** to
run any search and returns results in a JS grid with **no stable per-firm URL** — it cannot be
cited per row, and solving the CAPTCHA is out of scope. So banks were instead sourced against
the explicitly-permitted alternative: the official **PBOC list**.

`source_url` is the joint People's Bank of China + NFRA "系统重要性银行名单" (Systemically
Important Banks) release on `pbc.gov.cn`, published 2023-09-22, which names the four
state-owned majors in Group 4 (第四组): 中国工商银行 (ICBC), 中国银行 (BOC), 中国建设银行 (CCB),
中国农业银行 (ABC). Being on this joint PBOC/NFRA list confirms each is an NFRA-regulated,
licensed Chinese bank. `accreditation_number` / `accreditation_expiry` are blank — the list
carries neither a per-bank licence number nor an expiry.

**Excluded — HSBC China and Citibank China.** The task named them, but they are **not** on the
PBOC/NFRA Systemically Important Banks list, and the only per-firm official register for them
is the CAPTCHA-gated NFRA licence query. With no citable register page, they were excluded
rather than sourced from firm sites. (Re-source worklist below.)

### schools — International Baccalaureate (Find an IB World School)
Register: `ibo.org` "Find an IB World School". Each row was grounded live in the browser
(ibo.org 403s plain fetch/curl behind Cloudflare) on its per-school directory page; the page
confirms Country/territory = CHINA, a Shanghai coordinator address, and the IB School code.
`accreditation_number` is the IB School code shown on the page. `source_url` is the per-school
`find-an-ib-school/ibap/...` page (equivalent to `ibo.org/en/school/<id>`).

- Western International School of Shanghai — IB 003695
- The British International School, Shanghai (Nord Anglia, Puxi) — IB 003359
- Shanghai Community International School - Hongqiao Campus — IB 003565
- Yew Chung International School Pudong Shanghai — IB 006318

## Skipped categories — re-source worklist

- **banks (partial): HSBC China, Citibank China** — need a citable NFRA per-firm licence
  record. The NFRA query (`xkz.nfra.gov.cn/jr/`) is CAPTCHA + JS-grid with no stable per-firm
  URL. Re-source only if a citable licence record (or an alternative official list naming them)
  becomes reachable.
- **legal_admin** — Chinese lawyer/law-firm registers (Shanghai Judicial Bureau / All China
  Lawyers Association) are Chinese-only JS portals with no citable per-firm English page.
- **tax_finance** — CICPA (`cicpa.org.cn`) has no reachable citable per-firm accounting-firm
  register page found; skipped rather than use firm sites.
- **housing_agencies** — Shanghai real-estate-agency licensing (网上房地产 / housing bureau) is
  a Chinese-only JS portal; no citable per-firm register reached.

Per the sourcing rule, a whole category was skipped rather than backfilled from self-declared
firm marketing sites. Shanghai yielded movers + banks + schools, which is the expected floor.

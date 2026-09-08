# Manama, Bahrain — register-verified service providers (2026-08-31)

Corridor tag: `XX-BH` (destination Bahrain; origin unbound). Every row is evidenced by an
official statutory register or recognized accreditation body — not the firm's own marketing
site. Firms not found on a real register were excluded.

## Method

Registers were queried directly (curl of the register's own server / JSON API) wherever the
register was not bot-gated. The IBO register is Cloudflare-gated to curl/WebFetch (HTTP 403 +
Turnstile), so it was read via the shared browser (one school confirmed live) plus the
register pages' own search-indexed content for the rest; no CAPTCHA was completed.

## Categories

### movers — 1 firm — register: FIDI Global Alliance (FAIM)
- Register: `https://www.fidi.org/find-fidi-affiliate` filtered to Bahrain (`?country=257`).
- Bahrain has exactly **one** FIDI affiliate. Not padded.
- Cited per-affiliate DETAIL page (not the search URL):
  - GULF AGENCY CO. (BAHRAIN) W.L.L. — Manama (Bahrain Investment Wharf) — FAIM expiry **2029**
    — `https://www.fidi.org/find-fidi-affiliate/gulf-agency-co-bahrain-wll`

### banks — 6 firms — register: Central Bank of Bahrain (CBB Register / Licensing Directory)
- Register: `https://www.cbb.gov.bh/licensing-directory/` (the "CBB Register"). The page is a
  JS search widget backed by the CBB's own JSON API (`/cbbapi/`), which was queried directly:
  category `Conventional Banks` (401) → subcategory `Retail` (341) returns 22 licensed
  conventional retail banks; all six below are on that live list.
- Included the six major retail banks a relocating employee would use (all CBB-licensed,
  register-verified). The CBB Register exposes no public licence number and no expiry, so both
  fields are blank. Website values are taken from the CBB Register record where present.
  - Ahli United Bank (Bahrain) B.S.C. (c) — locally incorporated
  - Bank of Bahrain and Kuwait (BBK) — locally incorporated — reg. website bbkonline.com
  - National Bank of Bahrain BSC — locally incorporated — reg. website nbbonline.com
  - HSBC Bank Middle East Limited — branch — reg. website bahrain.hsbc.com
  - Citibank N.A. — branch — reg. website citibank.com/bahrain
  - Standard Chartered Bank — branch — reg. website standardchartered.com/bh
- (22 conventional-retail + 7 Islamic-retail licensees are available on the register if more
  are wanted later; only the six named majors were taken here.)

### schools — 3 firms — register: International Baccalaureate Organization (IBO)
- Register: IBO "Find an IB World School", per-school page `ibo.org/en/school/<id>`, IB id cited.
- Only IB World Schools located in **Manama** were included:
  - Arabian Pearl Gulf School — IB **003058** — Manama (Bilad Al Qadeem) — DP/CP/MYP
    (confirmed live via browser on the IBO page)
  - Al Rawabi School — IB **049961** — Manama (Jablat Hebshi, Block 435) — DP
  - Modern Knowledge Schools — IB **001369** — Manama (Juffair) — DP
- **Excluded:** Ibn Khuldoon National School (IB 000554) — a real IB World School but located
  in **Isa Town**, not Manama.
- IB authorisation carries no public expiry date, so `accreditation_expiry` is blank.

## SKIPPED categories (re-source worklist)

- **legal_admin** — SKIPPED. No official Bahrain per-firm register of legal/relocation-admin
  providers found reachable. Bahrain lawyers are on the Ministry of Justice "roll of lawyers",
  but that is an individual-advocate roll, not a per-firm register with citable firm pages.
  Re-source: MoJ / Bahrain Bar Society lawyer roll if a per-firm view becomes reachable.
- **tax_finance** — SKIPPED. No reachable official per-firm register. (Audit/accountancy firms
  are overseen via MOICT/CB frameworks but there is no clean public per-firm accreditation
  directory reachable here.) Re-source: BICPA / MOICT accredited-auditor list if reachable.
- **housing_agencies** — SKIPPED. RERA Bahrain (Real Estate Regulatory Authority) DOES license
  brokers and DOES maintain a licensed-brokers register, but the per-firm directory is served
  only through the interactive **bahrain.bh national portal** ("RERA Licensing Services →
  accredited licenses → Broker"); the public `rera.gov.bh/en/service/licensed-brokers` page is
  an informational service page with **no per-firm listing** (0 data rows). No reachable
  per-firm register page → skipped rather than cite firm sites.
  Re-source: `services.bahrain.bh` RERA licensed-brokers query if it becomes reachable
  server-side.

## Row counts

| category         | rows | register |
|------------------|------|----------|
| movers           | 1    | FIDI Global Alliance (FAIM) |
| banks            | 6    | CBB Register / Licensing Directory |
| schools          | 3    | IBO Find an IB World School |
| legal_admin      | 0    | SKIPPED |
| tax_finance      | 0    | SKIPPED |
| housing_agencies | 0    | SKIPPED |
| **total**        | **10** | |

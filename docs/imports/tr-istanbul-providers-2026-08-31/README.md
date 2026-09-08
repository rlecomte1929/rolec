# Istanbul, Türkiye — register-verified service providers (2026-08-31)

Corridor tag: `XX-TR` on every row. Every provider in `providers.csv` is evidenced by an
official statutory register or recognized accreditation body page (`source_url`), never a
firm's own marketing site. Firms not verifiable on a real register were excluded, and three
categories with no reachable citable per-firm official register were SKIPPED.

All rows were browser-grounded or direct-fetched against the live register on 2026-08-31.

## Categories

### movers — 4 firms
- **Register:** FIDI Global Alliance, "Find a FIDI Affiliate" (fidi.org). The full Türkiye
  affiliate list (`fidi.org/find-fidi-affiliate?country=113`) was read first; each firm below
  is cited to its per-affiliate DETAIL page, not the search URL.
- **Accreditation body:** FIDI Global Alliance (FIDI-FAIM / FIDI-FAIM Plus). `accreditation_expiry`
  = the FAIM certificate year shown on the affiliate page. FIDI does not print a numeric FAIM
  certificate number on these pages, so `accreditation_number` is blank.
- Firms (all listed under Istanbul on the FIDI Türkiye page):
  - **Asya International Movers** — legal name ASYA NAKLIYAT TIC. LTD. STI., Emirgan/Sarıyer,
    Istanbul. FIDI-FAIM Plus, cert 2028.
  - **BAFA International Movers** — legal name BAFA EV VE OFIS TASIMACILIGI TIC. LTD. STI.,
    Çekmeköy, Istanbul. FIDI-FAIM Plus, cert 2027.
  - **Bergen International Movers Lojistik A.Ş.** — Zekeriyaköy/Sarıyer, Istanbul. FIDI-FAIM
    ("top performer"), cert 2028.
  - **Esen International Movers** — legal name ESEN ULUSLARARASI NAKLIYAT VE TICARET A.Ş.
    İstanbul Şubesi, Gayrettepe, Istanbul. FIDI-FAIM Plus, cert 2028.
- Note: other Türkiye affiliates exist but are HQ'd elsewhere (ASYA and ISTANBUL EKSPRES also
  list Ankara/Izmir branches; BEDEL MOBILITY SOLUTIONS and BENICE FINE ART & RELOCATION are
  additional Istanbul affiliates left out to keep the set to four strongly-verified firms).

### banks — 5 firms
- **Register:** BDDK (Bankacılık Düzenleme ve Denetleme Kurumu / Banking Regulation and
  Supervision Agency) official **Kuruluş Listesi → Bankalar** — the statutory list of licensed
  banks at `bddk.org.tr/Kurulus/Liste/77`. Each institution row on that page carries the
  register's own data attributes (institution name, EFT code, registered address, web address,
  and an `isFaaliyette=1` "in operation" flag), which were read to confirm each bank below.
- **Accreditation body:** Banking Regulation and Supervision Agency (BDDK).
- **`accreditation_number`:** the bank's **EFT code** as recorded in the BDDK register — the
  register's per-institution identifier (there is no separate free-text "licence number" in
  this list). `website_url` is the web address printed in the same register row.
- Firms (all shown active; all registered HQ in Istanbul per the BDDK address field):
  T.C. Ziraat Bankası A.Ş. (EFT 10, Ümraniye/İstanbul), Türkiye İş Bankası A.Ş. (EFT 64,
  Levent/İstanbul), Türkiye Garanti Bankası A.Ş. (EFT 62, Beşiktaş/İstanbul), Akbank T.A.Ş.
  (EFT 46, 4.Levent/İstanbul), Yapı ve Kredi Bankası A.Ş. (EFT 67, Levent/İstanbul).
- Note: banks are national BDDK licensees; all five maintain Istanbul headquarters and
  operate branch networks across the city. The alternative register named in the brief — the
  Banks Association of Turkey (tbb.org.tr) — publishes the same membership but only via
  navigation-scoped list pages (the `/list-of-banks/34` permalink 404'd); the BDDK licensing
  list is the stronger statutory source and is what was cited.

### schools — 4 firms
- **Register:** IBO "Find an IB World School" (`ibo.org/en/school/<id>`). Cited the IBO detail
  page + IB School code for each. Pages sit behind a Cloudflare challenge for automated
  fetchers, so each was **browser-grounded** (challenge passed) and its name / country
  (TÜRKIYE) / IB code read off the live page.
- **Accreditation body:** International Baccalaureate Organization (IB).
- **`accreditation_number`:** IB School code.
- Firms (all TÜRKIYE / Istanbul): Istanbul International Community School (000938), Koç School
  (000755, Tuzla), Enka Schools (002546, Sarıyer), Eyuboglu Schools (000811).
- **Verification catch:** the web-search index mapped "British International School Istanbul"
  to IB code `000868`, but the live IBO page for `000868` resolves to a different, non-Türkiye
  school (Canadian International School, India, code 001121). That candidate was therefore
  dropped; only IDs confirmed on the live IBO page are included. Do not trust search-supplied
  IB codes without opening the IBO page.

## SKIPPED categories

### legal_admin — SKIPPED
İstanbul Barosu (istanbulbarosu.org.tr) publishes its Baro Levhası at `/levha`, but it is a
client-rendered GET **search form** (by sicil no / ad / soyad) that returns dynamic results
for individual lawyers — no stable, citable per-lawyer or per-firm permalink, and the data is
personal. Per the rules, skipped rather than fall back to firms' own sites.

### tax_finance — SKIPPED
The named registers do not expose a citable per-firm page. İSMMMO (`ismmmo.org.tr/uye`) carries
only a Google site-search box and delegates member lookup to TÜRMOB. TÜRMOB's member search
(`turmob.org.tr/MeslekMensubu/sorgulama`) was unreachable from this environment (connection
timed out on repeated attempts) and is in any case an individual-member search form (by name /
registration), not a per-firm register with permalinks. Skipped per the "else SKIP" rule.
- For a future pass: the **KGK** (Kamu Gözetimi Kurumu / Public Oversight, Accounting and
  Auditing Standards Authority, `kgk.gov.tr`) maintains the statutory register of authorized
  independent-audit firms (bağımsız denetim kuruluşları) — the Turkish analogue of Greece's
  ELTE used for Athens. It was **not** used here because the brief scoped this category to
  İSMMMO/TÜRMOB; it is the recommended substitute if a statutory audit-firm register outside
  the named bodies is acceptable.

### housing_agencies — SKIPPED
The Ministry of Trade's Taşınmaz Ticareti Bilgi Sistemi (TTBS, `ttbs.gtb.gov.tr`) exposes only
`/Home/BelgeSorgula` — a CAPTCHA-gated AJAX **verify-by-number** form (enter the Yetki Belgesi
number or business name to confirm a certificate). It returns results client-side with no
stable per-firm URL, and no citable published per-firm holder list was reachable. Per the
rules, skipped rather than cite realtors' marketing sites.

## Summary
- movers: 4 (FIDI Global Alliance, per-affiliate detail pages)
- banks: 5 (BDDK Kuruluş Listesi – Bankalar, licensed-banks register)
- schools: 4 (IBO Find an IB World School)
- legal_admin: SKIPPED (İstanbul Barosu levha = dynamic search form, no per-firm permalink)
- tax_finance: SKIPPED (İSMMMO delegates to TÜRMOB; TÜRMOB unreachable + member-search only)
- housing_agencies: SKIPPED (TTBS = CAPTCHA verify-by-number, no per-firm permalink)
- Total rows: 13

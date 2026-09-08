# Auckland, New Zealand — register-verified service providers (2026-08-31)

Sourcing for a relocating professional moving to Auckland. Every row in `providers.csv`
is evidenced by an official statutory register or recognised accreditation body via its
own register page (`source_url`) — never the firm's own marketing site. Firms not on a
real register were excluded; categories with no reachable per-firm register were SKIPPED.

`corridor` = `XX-NZ` on every row (destination-only, origin-agnostic).

## Categories

### movers — 4 rows
- **Register:** FIDI Global Alliance — "Find a FIDI Affiliate" (FAIM accreditation).
- **Evidence:** per-affiliate detail page `https://www.fidi.org/find-fidi-affiliate/<slug>` (not the search URL).
- Grounded by opening each affiliate detail page (fidi.org is reachable directly).
- Only affiliates with a confirmed **Auckland** office are included:
  - New Zealand Movers Group Limited — Auckland Airport — FAIM expiry 2027
  - The Moving Company (NZ) Ltd — Auckland — FAIM expiry 2027
  - Transworld International Removals Ltd — Rosedale, Auckland — FAIM expiry 2029
  - Conroy Removals Ltd — Auckland (7 Airpark Drive) — FAIM expiry 2029
- **Excluded:** Allied Moving Services NZ (SIRVA Group (NZ) Ltd) — FIDI office is in Lower Hutt, Wellington, not Auckland.
- FIDI has no per-affiliate licence number, so `accreditation_number` is blank; `accreditation_expiry` = FAIM year.

### banks — 5 rows
- **Register:** Reserve Bank of New Zealand (RBNZ) — "Registered banks in New Zealand".
- **Evidence:** `https://www.rbnz.govt.nz/regulation-and-supervision/cross-sector-oversight/registers-of-entities-we-regulate/registered-banks-in-new-zealand` (register last updated 24 Aug 2026; 26 registered banks total).
- Grounded by rendering the register table in-browser and confirming each name.
- All five target banks confirmed present as NZ-incorporated registered banks:
  ANZ Bank New Zealand Limited, ASB Bank Limited, Bank of New Zealand, Kiwibank Limited, Westpac New Zealand Limited.
- RBNZ shows a registration date, not an expiry, and no per-bank number — those fields left blank.

### schools — 4 rows (Auckland IB World Schools)
- **Register:** International Baccalaureate Organization — "Find an IB World School".
- **Evidence:** `https://www.ibo.org/en/school/<id>`; `accreditation_number` = IB school code.
  - Kristin School — 000434 — Albany, Auckland — PYP + MYP + DP
  - St Cuthbert's College — 003886 — Epsom, Auckland — DP
  - Diocesan School for Girls — 003360 — Epsom, Auckland — MYP + DP
  - Auckland Normal Intermediate School — 006498 — Mt Eden, Auckland — primary/intermediate
- **Grounding note:** Kristin (000434) was rendered live on ibo.org and its country (NEW ZEALAND),
  IB code, Auckland coordinator addresses and programmes were confirmed directly. The other three
  IDs/URLs were confirmed from the IBO register's own pages as indexed (page titles
  "… - International Baccalaureate®" at the exact `ibo.org/en/school/<id>` URLs, with the IB code
  shown) because ibo.org served an un-passable Cloudflare bot-challenge on those specific pages in
  this environment. IBO shows no accreditation expiry, so that field is blank.
- **Excluded:** ACG Parnell College — Cambridge International curriculum, not an IB World School.

### housing_agencies — 3 rows
- **Register:** Real Estate Authority (REA) public register — `https://publicregister.rea.govt.nz/`.
- **Evidence:** per-licensee detail page `https://publicregister.rea.govt.nz/licence?licenceid=<guid>`;
  `accreditation_number` = REA licence number; `accreditation_expiry` = licence expiry year.
- Grounded by searching the REA register by Business Name in-browser and opening each licence detail page
  (all confirmed Licence type = Company, Class = Agent, Current status = Active, Auckland address):
  - Barfoot & Thompson Limited — licence 10018521 — 34 Shortland Street, Auckland Central — expiry 31/03/2027
  - Bayleys Real Estate Limited — licence 10017764 — 30 Gaunt Street (Bayleys House), Auckland Central — expiry 31/03/2027
  - Megan Jaffe Real Estate Limited (t/a Ray White Remuera) — licence 10021620 — 411 Remuera Road, Auckland — expiry 08/08/2027
- Ray White / Harcourts operate in Auckland as many separately-licensed franchisee companies; one prominent
  Ray White company (Megan Jaffe Real Estate Ltd / Ray White Remuera) was included. Barfoot & Thompson and
  Bayleys are single national companies headquartered in Auckland.

## SKIPPED categories

### legal_admin — SKIPPED
The New Zealand Law Society site is reachable, but its public register is a **per-lawyer**
register ("Find a Lawyer" / "Public Register of Lawyers" at `lawsociety.org.nz/registry-lookup/`),
searchable by individual lawyer, area of law and region. It does not expose clean, citable
**per-firm** register entries. Per the task rule ("If reachable per-firm, cite it; else SKIP"),
this category is skipped rather than cite lawyer profiles or firm marketing sites.

### tax_finance — SKIPPED
Chartered Accountants Australia and New Zealand (CA ANZ) "Find a CA" directory
(`charteredaccountantsanz.com/find-a-ca`) is served behind a Cloudflare managed
bot-challenge that could not be passed in this environment, so the public directory could
not be opened to confirm any firm listing. Per the task rule ("if a public directory is
reachable, cite it; else SKIP"), this category is skipped rather than use self-declared firm sites.

## Summary
- movers: 4 (FIDI / FAIM)
- banks: 5 (RBNZ registered banks)
- schools: 4 (IBO IB World Schools)
- housing_agencies: 3 (REA licensed companies)
- legal_admin: SKIPPED (NZLS is a per-lawyer register, no per-firm citation)
- tax_finance: SKIPPED (CA ANZ directory behind un-passable bot challenge)
- **Total rows: 16**

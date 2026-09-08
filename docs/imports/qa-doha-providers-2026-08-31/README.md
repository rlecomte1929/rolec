# Doha, Qatar — register-verified service providers (2026-08-31)

Corridor tag: `XX-QA` (every row). Sourcing rule: each row must be evidenced by an
official statutory register / accreditation body page (`source_url`), never the firm's
own marketing site. A category is SKIPPED rather than filled from self-declared firm
sites when no public per-firm register is reachable from this environment.

`providers.csv` — 16 rows across 4 categories. 2 categories skipped (banks,
housing_agencies).

## Per-category result

### movers — 4 rows — INCLUDED
- Register: **FIDI Global Alliance — Find a FIDI Affiliate** (FAIM accreditation).
- Grounding: opened the Qatar filter (`fidi.org/find-fidi-affiliate?country=259`) in the
  browser; confirmed each affiliate on its per-affiliate DETAIL page
  (`/find-fidi-affiliate/<slug>`) — name, Doha/Qatar office, website, FAIM-PLUS
  certification and expiry year all read from the register.
- Qatar has exactly these 4 FIDI affiliates (not padded):
  - DELIGHT INTERNATIONAL MOVERS — FAIM-PLUS, expiry 2028
  - GULF AGENCY COMPANY QATAR (W.L.L.) — FAIM-PLUS, expiry 2029
  - GWC LOGISTICS — FAIM-PLUS, expiry 2026
  - TOKYO FREIGHT SERVICES WLL — FAIM-PLUS, expiry 2026
- `accreditation_number` blank (FIDI publishes no per-affiliate number; the FAIM cert is
  the accreditation). `accreditation_expiry` = FAIM expiry year.

### schools — 4 rows — INCLUDED
- Register: **International Baccalaureate Organization — Find an IB World School**
  (`ibo.org/en/school/<id>`). `accreditation_number` = IB School code (= the id in the URL).
- Grounding LIMITATION: ibo.org is behind **Cloudflare Turnstile** ("Verify you are
  human" checkbox). curl and WebFetch both return HTTP 403; the browser rendered one IB
  register page cleanly (confirming the page format: Country/territory, IB School code,
  programmes) but on my target pages presented the interactive Turnstile checkbox, which
  is bot-detection I am not permitted to click. School id↔name↔Doha mappings were
  therefore confirmed from **ibo.org's own indexed pages via site-restricted web search**
  (results returned canonical `ibo.org/en/school/<id>` URLs with exact school names,
  Doha locations, and authorization dates) rather than a live per-page render.
- Schools (all Doha city, all current IB World Schools):
  - Qatar Academy - Doha — IB code 001368
  - The American School of Doha — IB code 004603 (IB-authorized 2009)
  - Doha British School — IB code 006362
  - ACS International School Doha — IB code 049387
- `website_url` left blank (the school's own site is shown on the register page, which the
  Turnstile blocked from a live read; not invented).

### legal_admin — 4 rows — INCLUDED
- Register: **Qatar Financial Centre (QFC) Public Register**, category *Approved Service
  Providers* — `eservices.qfc.qa/qfcpublicregister/publicregister.aspx`.
- Grounding: fetched the full register (887 KB static HTML, table `ApprovedServiceProvider`,
  26 entries) and read each firm's name, Doha address, registration date and
  "QFCA Licensed" flag. NOTE: this QFC category is mixed (also contains banks, telecoms,
  corporate-service firms). Only firms that are unambiguously international **law firms**
  were selected, all QFC-registered and QFCA-licensed (=yes), Doha-based:
  - Addleshaw Goddard (GCC) LLP — QFC reg 10-Dec-2018
  - Al Tamimi & Company International Ltd. — QFC reg 13-Dec-2014
  - Clyde & Co LLP — QFC reg 03-Apr-2019
  - DWF LLP — QFC reg 07-Feb-2018
- `accreditation_number`/`expiry` blank (this register table shows registration date, not a
  per-firm licence number or expiry).

### tax_finance — 4 rows — INCLUDED
- Register: **Qatar Financial Centre (QFC) Public Register**, category *Approved Auditors*
  — same URL, table `ApprovedAuditors` (39 firms, all Doha, with registration dates).
- Grounding: read from the fetched register HTML. Selected the Big-Four audit firms
  present on the auditor register:
  - Ernst & Young — QFC auditor reg 16-Mar-2006
  - KPMG LLC — QFC auditor reg 24-May-2007 (QFCA Licensed = yes)
  - Deloitte And Touche (M.E.) — QFC auditor reg 11-Jun-2006
  - Pricewaterhousecoopers ME Limited Trading As Pricewaterhousecoopers — QFC auditor reg 16-Mar-2006
- `accreditation_number`/`expiry` blank (auditor table shows registration date only).

## SKIPPED categories (re-source worklist)

### banks — SKIPPED
- Intended register: QCB list of licensed banks (`qcb.gov.qa`).
- Reason: **no reachable public HTML register page exists.** The QCB site is a
  JS-rendered SharePoint; browser navigation to `qcb.gov.qa` is gated/denied in this
  session. Via curl the full English page inventory (57 pages, enumerated through the
  SharePoint `Pages` list REST API) contains **no bank-directory page** — only
  *Licensing For Banks And Other Financial Institutions* and *Instructions To Banks*,
  whose body content is client-side rendered and empty in a static fetch. The known bank
  names (QNB, Commercial Bank, Doha Bank, QIB, etc.) are only obtainable from third-party
  lists (Wikipedia/openbankingtracker), which are NOT the register — so not used.
- Re-source worklist:
  - Browser-ground `qcb.gov.qa` from an environment where that domain is allow-listed and
    JS runs (the licensed-institutions list is rendered client-side).
  - Or cite the QCB Financial Stability Report / statistical bulletin PDF (lists each bank)
    if that counts as the register.
  - QFC-zone banks (Lesha Bank, QInvest) ARE on the reachable QFC register, but those are
    not the retail banks a relocating professional needs (QNB/CB/QIB/Doha Bank are
    QCB-licensed, not QFC), so the QFC register does not substitute here.

### housing_agencies — SKIPPED
- Intended register: real-estate brokerage licence — Ministry of Justice / Real Estate
  Regulatory Authority (Aqarat).
- Reason: the register **exists but is unreachable from this environment.** The Aqarat
  site (`aqarat.gov.qa`) loads but does not itself list the firms; it links out to the
  actual broker registers, both of which refuse external connections (HTTP 000 /
  `ECONNREFUSED`, i.e. geo-restricted to Qatar):
  - MoJ Doha real-estate brokerage list — `moj.gov.qa/ar/Pages/doha_realestate_brokerage_map.aspx`
  - Qatar Real Estate Platform "View All Brokers" — `qrep.mm.gov.qa/broker-indicators`
- Per the rule, SKIPPED rather than fall back to firm sites.
- Re-source worklist: fetch the MoJ brokerage list / QREP broker-indicators from a
  Qatar-reachable network (or via a proxy that isn't connection-refused), then cite the
  per-firm broker record.

## Method notes / traps
- FIDI and QFC registers are server-rendered and fetchable (FIDI via WebFetch; QFC via
  curl — QFC's `qcb`-style cert was fine, but note QCB's own cert fails WebFetch with
  "unable to verify the first certificate").
- ibo.org and QCB both defeat headless fetching (Cloudflare Turnstile / JS SharePoint).
- moj.gov.qa and qrep.mm.gov.qa are connection-refused externally (Qatar geo-fence).
- The shared browser in this session is multi-tenant (other agents repoint tabs); a
  dedicated tab (`tabs_create`) was used to avoid mid-batch hijacking.

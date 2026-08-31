# Tallinn, Estonia — register-verified service providers (corridor XX-EE)

Sourced 2026-08-31. Every row is evidenced by an official statutory register or
recognised accreditation body (the `source_url`), not the firm's own marketing site.
Firms not confirmable on a real register were excluded.

Total rows: **18** across **5** categories. **1** category skipped (housing_agencies).

Per-category counts: movers 1 · banks 5 · schools 4 · legal_admin 4 · tax_finance 4.

## Per-category summary

### movers — 1 firm
- **Register:** FIDI Global Alliance affiliate finder, filtered to Estonia
  (`?country=273`). Cited per-affiliate detail page as required.
- **Verification:** the Estonia-filtered affiliate list returns **exactly one**
  affiliate. The KLG detail page was opened directly and confirms a Tallinn office
  and a live FAIM certificate:
  KLG INTERNATIONAL MOVERS LTD (legal name KLG EESTI AS), Peterburi Road 34, Tallinn —
  FIDI-FAIM, certificate expiry **2028** (recorded in `accreditation_expiry`).
  `https://www.fidi.org/find-fidi-affiliate/klg-international-movers-ltd`
- FIDI shows no numeric affiliate id, so `accreditation_number` is blank.
- **Why only one:** Estonia genuinely has a single FIDI affiliate. Other Tallinn
  movers surfaced in discovery (Adduco, FidsTrans, etc.) are **not** on the FIDI
  register and were excluded rather than invented up to a count of 3–4.

### banks — 5 credit institutions
- **Register:** ECB Banking Supervision *List of supervised entities* (SSM), Estonia
  section. `https://www.bankingsupervision.europa.eu/ecb/pub/pdf/ssm.listofsupervisedentities202408.en.pdf`
  (task-permitted ECB/SSM alternative to the Finantsinspektsioon national register;
  Estonia is in the eurozone / SSM).
- **Verification:** extracted the Estonia block from the PDF and confirmed each as an
  Estonian credit institution ("CI"), with its LEI recorded in `accreditation_number`:
  - Directly ECB-supervised **significant** institutions: Swedbank AS
    (`549300PHQZ4HL15HH975`), AS SEB Pank (`549300ND1MQ8SNNYMJ22`), AS LHV Pank
    (`529900GJOSVHI055QR67`), Luminor Bank AS (`213800JD2L89GGG7LF07`).
  - **Less significant** institution (supervised by Finantsinspektsioon as NCA, still
    on the SSM list): Coop Pank AS (`549300EHNXQVOI120S55`).
- These five are the retail banks a relocating employee actually uses. The list also
  carries Bigbank AS, AS Inbank, Holm Bank AS and AS TBB pank as further Estonian CIs;
  they were left out as non-retail / niche, not because they fail the register.
- The Finantsinspektsioon register (`fi.ee`) is the corroborating national supervisor;
  its public entity list is a JS view (several candidate URLs 404'd on direct fetch), so
  the ECB SSM list — which carries the same authorisation status plus LEIs — is cited.

### schools — 4 IB World Schools (Tallinn)
- **Register:** IBO "Find an IB World School", Estonia-filtered
  (`find-an-ib-school/?SearchFields.Country=EE`). `accreditation_number` = the IB
  School code, and `source_url` = `https://www.ibo.org/en/school/<id>`.
- **Verification:** the IBO Estonia-filtered register listing loaded and returns **7**
  IB World Schools; each school id was read directly from that official listing.
  Two of the seven are in **Tartu** (Miina Härma Gümnaasium 006552, Tartu International
  School 060016) and were **excluded**. The five Tallinn schools are IST (060867),
  ISE (001455), Tallinn English College (003763), Audentes International School (006396)
  and LANA Tallinn International Kindergarten (064113). The four full PYP/MYP/DP schools
  relevant to relocating families are recorded; the LANA kindergarten was left out to
  hold the count at four.
- ibo.org serves an intermittent Cloudflare bot challenge to direct fetches of the
  per-school detail pages (not a bypassable CAPTCHA), so the ids/URLs come from the
  register listing itself; Audentes' Tallinn location was cross-confirmed by search.

### legal_admin — 4 law offices (Tallinn)
- **Register:** Eesti Advokatuur (Estonian Bar Association) *Law Offices* register —
  `https://www.advokatuur.ee/en/find-advocates/law-offices` (230 registered offices).
  Each office has a per-firm detail page (cited as `source_url`) showing its Estonian
  business **Registry code** (recorded in `accreditation_number`) and Tallinn address.
- **Verification:** each per-firm page was fetched and confirmed with a Tallinn office:
  COBALT (10188708, Pärnu mnt 15), SORAINEN (10876331), Eversheds Sutherland Ots&Co
  (10639559, Rävala), TRINITI (11984324). All are top-tier full-service firms handling
  corporate / immigration / relocation matters.

### tax_finance — 4 approved audit firms (Tallinn)
- **Register:** Audiitorkogu (Estonian Auditors' Association) register of audit firms
  (audiitorettevõtjad) — `https://www.audiitorkogu.ee/est/audiitorettevotjad`
  (113 registered firms, each with a per-firm detail page cited as `source_url`).
- **Verification:** each firm's detail page shows an **activity licence number**
  (Tegevusloa number, recorded in `accreditation_number`) and Tallinn address:
  KPMG Baltics OÜ (licence 17, Ahtri tn 4), Aktsiaselts PricewaterhouseCoopers
  (licence 6, Tatari 1), Ernst & Young Baltic AS (licence 58, Rävala pst 4),
  BDO Eesti OÜ (licence 1, Veskiposti 2). The URL path id is the firm's business
  registry code; the `accreditation_number` is the distinct audit activity licence.
- Deloitte was **not** found on the Audiitorkogu firm register and was therefore not
  included.

## Skipped category

### housing_agencies — SKIPPED
Estonia has **no statutory per-firm real-estate agency register**. Real-estate
brokerage is not firm-licensed; the only official record is the per-**person**
professional-qualification register (Kutsekoda / kutseregister, "kinnisvaramaakler"),
and the Estonian Association of Real Estate Companies (EKFL) is a voluntary trade body,
not an official register. Per the task rules, the category is skipped rather than
populated from firms' own marketing sites.

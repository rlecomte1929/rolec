# IN corridor facts — third-country-national professional relocated to India (Bengaluru hub)

- **Corridor**: IN | **Perspective nationality**: non-EEA | **Status**: professional
- **Generated**: 2026-08-31
- **Facts**: 11 (`facts.ndjson`) — all `confidence: high`, `non_obvious: true`, `quote_verbatim_confirmed: true`
- **Sources**: OFFICIAL Government of India only (gov.in). No blogs/relocation-firm/news.

## Sources used (all direct-fetched and grounded)

| # | Source | URL | Fetched | Verbatim confirmed? |
|---|--------|-----|---------|---------------------|
| 1 | Ministry of Home Affairs (MHA) — *FAQs Relating to Work Related Visas Issued by India* (Business & Employment Visa policy) | https://www.mha.gov.in/sites/default/files/2022-08/work_visa_faq%5B1%5D.pdf | 200 OK (PDF, 15pp) | YES — 9 facts |
| 2 | Income Tax Department — *Non Resident* help / FAQ (Section 6 residency; Not Ordinarily Resident) | https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/non-resident | 200 OK (HTML) | YES — 2 facts |

Every `evidence_quote` was confirmed to be a verbatim substring (whitespace-normalized) of the fetched official text and is <200 chars. Normalization only collapses runs of whitespace to a single space; it accounts for:
- **MHA PDF**: justified-text extraction inserts double spaces / line breaks mid-sentence (the salary sentence is also column-scrambled in extraction, so the quote uses the clean contiguous fragment `should draw a salary in excess of US$ 25,000 per annum.`).
- **Income Tax HTML**: the source page literally contains the typos `tax -resident` and `non -resident` (space before hyphen) and `&nbsp;` entities; the quotes were chosen to sit around these artifacts so they read cleanly while remaining exact substrings.

## Pillars (all within the allowed 7; none use IMMIGRATION/TAX/FAMILY)
EMPLOYMENT ×6, RESIDENCE ×3, TIMELINE ×1, HOUSING ×1

## Topics covered
1. Employment Visa salary floor — must exceed **US$ 25,000/annum** (verbatim on mha.gov.in)
2. E-Visa refused for jobs qualified Indians can fill / routine-clerical roles
3. E-Visa tied to the sponsoring employer (name printed on the visa sticker)
4. Business Visa expressly bars full-time employment (you cannot work on a B visa)
5. FRRO/e-FRRO registration within **14 days** of arrival if visa validity >180 days (TIMELINE)
6. No FRRO registration if the E-Visa is issued for **180 days or less** (trigger = visa validity, not trip length)
7. Any change of Indian residential address must be reported to the FRRO in writing (HOUSING)
8. Employment Visa extension is conditioned on **filing Indian Income Tax returns**
9. Employment Visa must be obtained **from the home/domicile country before arrival** (no in-India conversion)
10. Income-tax **residency at 182 days** (Section 6)
11. **RNOR / "Not Ordinarily Resident"** sub-status in the early years

## Unverifiable / dropped sources (transparency)
- **US$ 25,000 threshold in USD** confirmed verbatim on the MHA FAQ PDF. The consular mirror `https://www.cgisf.gov.in/page/employment-visa/` (also gov.in) states the same policy but in rupees (`gross salary in excess of Rs. 16.25 lakhs per annum`); not emitted to avoid duplicating the salary fact.
- **PAN (tax number)** was on the target topic list but **DROPPED**: the authoritative Section 139A text lives on `incometaxindia.gov.in`, which returned **HTTP 403** to direct fetch, and no other gov.in page yielded a clean verbatim PAN-mandatory quote. No fact was invented.
- `boi.gov.in/content/employment-visa*` — 404 (Bureau of Immigration content moved); MHA FAQ used as the primary policy source instead.
- **RNOR "shields foreign income"**: the practical benefit is stated only in each fact's `non_obvious_note` (guidance), not as a quoted claim — the emitted `evidence_quote` covers only the verbatim RNOR day/year test from incometax.gov.in.

## needs_lawyer_review
All facts are direct statutory/policy statements quoted verbatim from primary MHA / Income Tax Department sources; `needs_lawyer_review: false` on all.

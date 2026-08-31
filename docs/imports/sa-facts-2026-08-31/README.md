# Saudi Arabia (SA) relocation facts — 2026-08-31

Non-obvious, official-government-sourced immigration/relocation facts for a **third-country-national
professional relocated by an employer to Saudi Arabia** (hub: Riyadh). Perspective nationality =
`non-EEA` (all Saudi work migration is a third-country pathway).

- Output: `facts.ndjson` (12 facts, one JSON object per line).
- All sources are official Saudi government / statutory publications.

## Grounding method (important)

The Saudi government **HTML service portals are not reachable for verbatim grounding from this
environment**: `my.gov.sa` and `absher.sa` sit behind a Cloudflare bot wall that returns
"Sorry, you have been blocked" / an "Attention Required" challenge (no CAPTCHA was attempted), and
`cchi.gov.sa` (Council of Health Insurance), `saudieng.sa` (Saudi Council of Engineers) and
`laws.boe.gov.sa` were unreachable (DNS/connection blocked) from both the shell and the fetch path.

Facts were therefore grounded against the **official government PDF publications**, which were
downloaded and read directly, and each `evidence_quote` was **programmatically verified to be an
exact substring of the source PDF's extracted text**. This is a stronger form of verbatim
confirmation than reading rendered HTML, so every fact is marked
`quote_verbatim_confirmed: true`.

## Sources used

| # | topic | pillar | source URL | quote confirmed verbatim |
|---|-------|--------|-----------|--------------------------|
| 1 | work_visa_sponsorship (employee mobility) | EMPLOYMENT | https://www.hrsd.gov.sa/sites/default/files/2020-11/1112020.pdf (MHRSD — Labor Reform Initiative Services Guidebook) | true (exact substring of PDF) |
| 2 | sponsorship_transfer (without consent) | EMPLOYMENT | https://www.hrsd.gov.sa/sites/default/files/2020-11/1112020.pdf | true |
| 3 | exit_reentry_visa (employer cannot cancel) | IMMIGRATION | https://www.hrsd.gov.sa/sites/default/files/2020-11/1112020.pdf | true |
| 4 | exit_reentry_extension (Muqeem, from abroad) | IMMIGRATION | https://www.hrsd.gov.sa/sites/default/files/2024-11/Guide%20to%20Services%20Provided%20for%20Expatriates.pdf (MHRSD — Guide to Services Provided for Expatriates 1445/2024) | true |
| 5 | iqama_issuance (medical exam, sponsor-issued) | IMMIGRATION | https://www.hrsd.gov.sa/sites/default/files/2024-11/Guide%20to%20Services%20Provided%20for%20Expatriates.pdf | true |
| 6 | employment_contract (Qiwa documentation) | EMPLOYMENT | https://www.hrsd.gov.sa/sites/default/files/2024-11/Guide%20to%20Services%20Provided%20for%20Expatriates.pdf | true |
| 7 | tax_residency (183 days) | TAX | https://www.hrsd.gov.sa/sites/default/files/2024-11/Guide%20to%20Services%20Provided%20for%20Expatriates.pdf (describes the ZATCA tax-residence-certificate service) | true |
| 8 | premium_residency (work/change job without sponsor) | IMMIGRATION | https://misa.gov.sa/app/uploads/2024/11/...انجليزي-.pdf (Premium Residency Center — Premium Residency Permit Law, EN) | true |
| 9 | health_insurance (cooperative insurance required) | HEALTHCARE | https://misa.gov.sa/app/uploads/2024/11/...انجليزي-.pdf (Premium Residency Permit Law, Art. 6) | true |
| 10 | driving_license (foreign-licence test exemption) | IMMIGRATION | https://www.hrsd.gov.sa/sites/default/files/2024-11/Guide%20to%20Services%20Provided%20for%20Expatriates.pdf | true |
| 11 | document_attestation (degrees / marriage certs) | FAMILY | https://www.hrsd.gov.sa/sites/default/files/2024-11/Guide%20to%20Services%20Provided%20for%20Expatriates.pdf (MoFA attestation service) | true |
| 12 | property_ownership (restricted; premium residency) | HOUSING | https://misa.gov.sa/app/uploads/2024/11/...انجليزي-.pdf (Premium Residency Permit Law, Art. 2) | true |

Full Premium Residency Law URL (URL-encoded Arabic filename):
`https://misa.gov.sa/app/uploads/2024/11/%D9%86%D8%B8%D8%A7%D9%85-%D8%A7%D9%84%D8%A5%D9%82%D8%A7%D9%85%D8%A9-%D8%A7%D9%84%D9%85%D9%85%D9%8A%D8%B2%D8%A9-%D9%84%D8%B9%D8%A7%D9%85-1445%D9%87%D9%80-%D8%A7%D9%86%D8%AC%D9%84%D9%8A%D8%B2%D9%8A-.pdf`

## Categories that could NOT be verified (need re-sourcing)

These are genuine non-obvious facts but their authoritative sources were unreachable from this
environment, so **no verbatim quote was captured and they were deliberately omitted** from
`facts.ndjson`:

- **Professional accreditation — Saudi Council of Engineers (SCE):** engineers cannot practise
  without SCE professional accreditation/registration. Source `saudieng.sa` (and its
  "Implementing Regulations of the Law on Practicing Engineering Professions" PDF) was unreachable
  (connection blocked). Re-source from `saudieng.sa` when reachable, or from the law on
  `laws.boe.gov.sa`.
- **Cooperative Health Insurance Law — iqama link (direct CCHI text):** the requirement that an
  iqama may not be issued/renewed without a cooperative policy is captured indirectly via the
  Premium Residency Law (fact 9); the direct CCHI statutory wording on `cchi.gov.sa`
  (Implementing Regulations of the Cooperative Health Insurance Law) was unreachable and should be
  added when accessible.
- **Work-visa / "block visa" mechanics (my.gov.sa):** sponsorship-letter certification by the
  Chamber of Commerce + MoFA and the block-visa number. `my.gov.sa` is Cloudflare-blocked; only a
  paraphrased search snippet was available, so it was not included.
- **Banking access requires an Iqama (SAMA):** widely true operationally but no verbatim SAMA/gov
  statement was captured; re-source from `sama.gov.sa` or a bank's regulated account-opening page.

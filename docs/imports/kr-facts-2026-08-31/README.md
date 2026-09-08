# KR facts — South Korea (Seoul), third-country-national professional relocated by employer

Perspective: nationality = `non-EEA`, status = `professional`, corridor = `KR`.
Date: 2026-08-31. Output: `facts.ndjson` (10 facts, all `confidence: high`).

## Scope

Non-obvious, official-government-sourced immigration/relocation facts for an employer-relocated
foreign professional in South Korea. Every `evidence_quote` was confirmed as a **verbatim
substring** (whitespace-normalised) of text fetched directly from an official `.go.kr` /
`nhis.or.kr` source. No blogs, relocation firms, or news. No invented numbers, fees, or citations.

## Sources (official government only) — all verbatim-confirmed

| # facts | Source | URL | How fetched | Verbatim? |
|---|---|---|---|---|
| 3 | National Health Insurance Service — "Guidance for foreigners" (English) | https://www.nhis.or.kr/english/wbheaa02900m01.do | `curl` (HTTP 200), HTML stripped | ✅ yes |
| 4 | Korea Immigration Service — "VISA NAVIGATOR: Customized Stay Guide for Foreign Residents" (English PDF, 59 pp) | https://www.immigration.go.kr/bbs/immigration_eng/230/454085/download.do | `curl` PDF → `pdfplumber` text | ✅ yes |
| 3 | National Tax Service — "Individual Income Tax and Benefit Guide for Foreigners 2026 (Tax return for 2025)" (English/Korean PDF, 280 pp) | https://www.nts.go.kr/english/na/ntt/selectNttInfo.do?mi=10788&bbsId=30698&nttSn=1350804 | Landing page `curl` → attached PDF (`nttFileDownload.do?fileKey=…`) → `pdfplumber` text | ✅ yes |

Notes on provenance:
- **NTS**: the `source_url` is the stable NTS landing page for the guide. The verbatim quotes live
  in that page's official attached PDF (title confirmed: *Individual Income Tax and Benefit Guide
  for Foreigners 2026(Tax return for 2025)*). The PDF was reached via the `fileKey` download link on
  that page.
- **Immigration**: the `source_url` returns the VISA NAVIGATOR PDF directly. The PDF renders some
  content as tables, which injects layout labels (e.g. "Main Content") mid-line during extraction;
  every quote used was chosen to be a clean contiguous span that does **not** cross those labels,
  and each was re-verified against the extracted text.

## Facts by pillar

- **HEALTHCARE (3)** — foreign employees compulsorily enrolled in NHIS; the >6-month mandatory-
  subscription rule (captures non-working family); employee/employer 50/50 premium split.
- **EMPLOYMENT (4)** — prior immigration permission required to change/add a workplace; 19% flat-tax
  election (loses all deductions); residents taxed on worldwide income; tax residency turns on 183
  days, not nationality.
- **IDENTITY (1)** — Alien / foreign resident registration within 90 days of entry.
- **RESIDENCE (1)** — re-entry-permit exemption lapses after one year abroad.
- **HOUSING (1)** — change of address must be reported within 15 days.

Pillars used: EMPLOYMENT, HEALTHCARE, HOUSING, IDENTITY, RESIDENCE. (None: SOCIAL_SECURITY, TIMELINE.)

## Topics attempted but NOT shipped (no verbatim official quote on an allowed domain)

- **National Pension / social-security totalization (SOCIAL_SECURITY)** — the authoritative body is
  the National Pension Service on `nps.or.kr`, which is **not** a `.go.kr` / `nhis.or.kr` domain, and
  `moel.go.kr/english/main.jsp` returned HTTP 404. Dropped rather than cite a disallowed source or
  invent. The NTS guide references pension only as an income deduction, not as the mandatory-
  enrolment/totalization rule, so it was not usable for this fact.
- **Driving-licence conversion (HOUSING)** — the operating body is KoROAD (`koroad.or.kr` / not
  `.go.kr`); the immigration guide does not cover it. No allowed-domain verbatim source found.
- **E-7 "employer-sponsored & occupation-specific" as a standalone RESIDENCE fact** — HiKorea's
  English E-7 page (`hikorea.go.kr`) is a JavaScript shell to `curl` (returned ~3.8 KB, no content),
  and the VISA NAVIGATOR E-7 table row is column-interleaved so no clean contiguous quote could be
  extracted. The employer/occupation tie is instead captured verbatim by the EMPLOYMENT fact
  "changing or adding a workplace needs prior immigration permission."

## Verification method

`facts.ndjson` was generated and then independently re-validated: each line parses as JSON, carries
the full required schema, uses an allowed `.go.kr`/`nhis.or.kr` `source_url`, has an `evidence_quote`
under 200 characters, and that quote is a whitespace-normalised verbatim substring of the fetched
official source text. All 10 lines passed.

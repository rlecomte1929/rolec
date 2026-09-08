# TH facts — third-country-national professional relocated to Thailand (Bangkok)

Batch date: 2026-08-31
Corridor / destination: `TH` · Perspective nationality: `non-EEA` · Status: `professional`
Output: `facts.ndjson` (12 facts). Candidate load only — `non_obvious:true`, `needs_lawyer_review:false`.

## Verification method

Every `evidence_quote` was confirmed to be a **verbatim substring** of the fetched official text
(HTML entity-decoded + tag-stripped + whitespace-collapsed; for PDFs, text extracted with `pypdf`
+ whitespace-collapsed). Quotes containing PDF two-column extraction artifacts (spurious mid-word
spaces) were rejected and replaced with artifact-free substrings. All 12 quotes passed and are
< 200 chars. `quote_verbatim_confirmed:true` on every record.

## Sources — all official, all `go.th`

| # facts | Source | URL | Fetch method | Verbatim? |
|--------:|--------|-----|--------------|-----------|
| 3 | Ministry of Foreign Affairs — Non-Immigrant Visa "B" | https://www.mfa.go.th/en/page/non-immigrant-visa-b | curl (direct) | yes |
| 2 | Revenue Department — Personal Income Tax (English) | https://www.rd.go.th/english/6045.html | curl (direct) | yes |
| 2 | BOI SMART Visa | https://smart-visa.boi.go.th/smart/ | curl (direct) | yes |
| 2 | Social Security Office — Social Security Act, B.E. 2533 (1990), English (SSO-hosted PDF, ss.34/46/47) | https://www.sso.go.th/wpr/assets/upload/files_storage/sso_th/6aece18d294cfea419d4b4ad946bc368.pdf | curl + pypdf | yes |
| 3 | Immigration Act, B.E. 2522 (1979), English translation (ss.37(1), 37(5), 39) hosted by the Royal Thai Police — parent agency of the Immigration Bureau | https://royalthaipolice.go.th/downloads/laws/laws_03_03-03.pdf | curl + pypdf | yes |

Notes on the two statutory PDFs:
- The Immigration Act translation on `royalthaipolice.go.th` carries an "unofficial translation /
  educational purposes" disclaimer and was commissioned by the Office of the Council of State (Law
  for ASEAN project). It is the accessible official-government-hosted English text for the 90-day
  report (s.37(5)), the no-work-without-permission rule (s.37(1)) and the re-entry-permit rule
  (s.39). The Thai original remains the sole legal authority.
- The SSO Act PDF is the English Social Security Act, B.E. 2533, hosted on `sso.go.th`.

## Unverifiable / blocked sources (facts NOT drawn from these)

- **immigration.go.th** (incl. `bangkok.immigration.go.th`, `tm47.immigration.go.th`,
  `www.immigration.go.th`) — behind Cloudflare. curl/WebFetch return 403 "Just a moment…"; the real
  browser was redirected to an **interactive "Verify you are human" checkbox** (a CAPTCHA), which
  was not completed. The Immigration-Bureau-specific facts (90-day report, re-entry permit, no-work
  rule) were instead sourced verbatim from the official English Immigration Act text hosted on
  `royalthaipolice.go.th` (see above).
- **doe.go.th** (Department of Employment, incl. `eworkpermit.doe.go.th` and the WP.3/WP.5 form
  PDFs) — same Cloudflare gate (403/000). The employer-specific work-authorisation fact was sourced
  from the MFA Non-B page, which sets out the WP3 / Ministry of Labour approval requirement. No fact
  claims text that could only be verified on doe.go.th.
- **sso.go.th** English HTML pages (`/wpr/eng/…`, `/wpr/main/privilege/Employers_en`) — served a
  generic Thai portal shell / empty body, so the English Social Security Act PDF was used instead.

## Coverage of requested non-obvious topics

Covered with verbatim official quotes: Non-B is the work visa (RESIDENCE); work permit required
before starting work (EMPLOYMENT); employer-initiated / employer-specific authorisation via WP3
(EMPLOYMENT); cannot work on a tourist/temporary stay without permission (EMPLOYMENT); re-entry
permit needed or stay terminates on departure (RESIDENCE); 90-day address report (TIMELINE); SMART
visa alternative with work-permit exemption + working dependants (RESIDENCE); tax residency at 180
days (EMPLOYMENT); foreign income remitted into Thailand is taxable, flagging the recent tightening
(EMPLOYMENT); Social Security enrolment within 30 days + wage-deducted contributions
(SOCIAL_SECURITY).

Pillars used: EMPLOYMENT ×5, RESIDENCE ×4, SOCIAL_SECURITY ×2, TIMELINE ×1 (all within the allowed
7; no IMMIGRATION/TAX/FAMILY).

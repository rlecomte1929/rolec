# CY facts — third-country professional relocated to Cyprus (Nicosia hub)

Date: 2026-08-31
Corridor: `CY` · nationality `non-EEA` · status `professional`
Output: `facts.ndjson` (12 facts)

## Scope decision
Cyprus is EEA. Per the hard filter ("write ONLY facts NOT also applicable to an EU
citizen"), this batch is restricted to **immigration / residence / work-authorisation**
facts that are genuinely third-country-only. The requested tax topics (60-day tax
residency rule, non-domicile SDC exemption) and social-insurance registration were
**intentionally excluded**: the government's own Strategy Q&A states the non-dom regime
applies to "either EU citizens or third-country nationals", and the 60-day rule,
non-dom status and social-insurance registration all apply regardless of nationality —
so they fail the EU-citizen filter. They are strong non-obvious facts but belong in a
nationality-agnostic corridor layer, not a `non-EEA`-tagged batch.

## Sources (official gov.cy only) — all verbatim-confirmed
Both pages were re-fetched fresh and every `evidence_quote` word-matches the live
visible text (referee simulation: 12/12 PASS, contiguous + word-match).

| # | Source URL | Confirmed verbatim? | Facts |
|---|---|---|---|
| 1 | https://www.gov.cy/mip-md/en/documents/legislation-and-policy/ | YES (contiguous + word-match) | 8 (permit-tied, no-quota/no-labour-check, 70:30 ratio, €2500 salary, 2-yr contract+stamp, employer BSC registration, support-level labour test, 1-month exam) |
| 2 | https://www.gov.cy/mip-md/en/documents/procedure-for-application-submission-for-entry-and-residence-processing-time-and-maximum-duration-of-residence/ | YES (contiguous + word-match) | 4 (Aliens' Register/ARC €70, biometrics at Cyprus Police, no-time-limit stay, change-employer 1-month) |

Both are the **Migration Department** (Ministry of Interior) English pages on gov.cy,
"Companies of Foreign Interests" section (Business Facilitation Unit / New Strategy in
force since 2.1.2022).

## Fetch / referee note (IMPORTANT for the applier)
gov.cy is WAF-gated: it returns **HTTP 403 to a default/library User-Agent** but **200
to a browser User-Agent** (`Mozilla/5.0 … Chrome/120`). Both pages are static
server-rendered HTML — the quoted text is present in the raw HTML (not JS-injected).
`confirm_quotes.py` must send a browser UA, or these will falsely HELD as
"cannot fetch". Pages are English, rendered HTML (no PDFs used).

## Fetchability of sources checked but NOT used
- `www.mip.gov.cy` (old Lotus-Notes `md.nsf` pages): **SSL certificate expired** — avoid.
- `www.mof.gov.cy/mof/TAX/taxdep.nsf/...`: 302-redirects to the gov.cy tax homepage,
  not to the residency content. Tax-residency (60-day) content not cleanly sourced in
  English HTML; excluded anyway per scope decision above.
- Strategy PDFs (`businessincyprus.gov.cy/.../Updated-Strategy_Febr-2024.pdf`,
  `gov.cy/media/.../questions_answers190722.pdf`): real text layer present and fetchable,
  but 2022-vintage; HTML sources preferred and sufficient.

## Pillar distribution
RESIDENCE ×4 · EMPLOYMENT ×5 · IDENTITY ×2 · TIMELINE ×1.
All `non_obvious=true`, `needs_lawyer_review=false`, `confidence=high`,
`quote_verbatim_confirmed=true`.

# US-departure requirement batch — us-departure-2026-09-10

**Corridor:** US -> Ecuador (US->EC) · **Persona:** Abraham, a US national relocating Seattle -> Quito on a professional residence visa.
**Scope:** US exit-side requirement facts only (what a departing US citizen must keep doing / knows about the US side). No origin-side Ecuador facts and no destination facts in this batch.

## What this batch contains
10 candidate requirement facts (`requirement_items`) describing US federal (and Washington State) obligations that persist after the mover leaves the US:

- **Federal income tax while abroad** — US citizens remain taxed on worldwide income and must keep filing Form 1040 (irs.gov).
- **Special benefits require filing** — FEIE and the foreign tax credit are only available if a US return is filed (irs.gov).
- **Foreign earned income exclusion (Form 2555)** — eligibility to exclude foreign earnings, and the 330-full-days physical presence test (irs.gov).
- **FBAR / FinCEN Form 114** — the USD 10,000 aggregate-account reporting threshold (fincen.gov) and the April 15 BSA e-filing due date (irs.gov).
- **Washington State** — explicit fact that WA has no individual income tax, so there is no state exit filing on departure (dor.wa.gov). (Note: a new 9.9% tax on AGI over $1M takes effect Jan 1, 2028 per SB 6346, per the same page.)
- **No US–Ecuador totalization agreement** — sourced to SSA's totalization overview; Ecuador is ABSENT from the published list of agreement countries (Italy through Romania), so the dual-Social-Security-taxation protection SSA describes does not apply and dual contributions are possible (ssa.gov).
- **Maintaining an SSN** — every US tax filer needs an SSN/ITIN, which continues while abroad (irs.gov).
- **Automatic 2-month filing extension** for citizens abroad (to June 15), which extends filing but not payment (irs.gov).

`needs_lawyer_review: true` is set on all 5 tax-determination facts (worldwide-income liability, benefits-require-filing, FEIE eligibility, FEIE physical presence, and the no-totalization dual-contribution conclusion).

## Sources used (official only)
- irs.gov — U.S. citizens and resident aliens abroad; Foreign earned income exclusion; FEIE physical presence test.
- fincen.gov — Report Foreign Bank and Financial Accounts (FBAR).
- ssa.gov — U.S. International Social Security Agreements (totalization) overview.
- dor.wa.gov — Income tax page.

Every `evidence_quote` is verbatim text retrieved via web_fetch from the official page listed in `source_url` (each >= 25 chars). No blogs, law-firm, or vendor sources were used or cited.

## Honest gaps / facts not delivered
- **State Dept / STEP enrolment (travel.state.gov):** Could NOT be sourced. The STEP page, the travel.state.gov home/checklist pages, and step.state.gov are JavaScript single-page apps that returned no text via the scraper (repeated attempts, including a forced fresh fetch). Because no verbatim official quote could be captured, this topic was DROPPED rather than fabricated. It should be re-attempted with a renderer that executes JavaScript, or via an official static/PDF State Dept source.
- **Ecuador social-contribution specifics:** The no-totalization fact establishes that both countries *may* levy contributions, quoted from SSA. The actual Ecuadorian (IESS) contribution rules are destination-side and out of scope for this US-exit batch; not asserted here.
- **Exact current-year FEIE dollar cap:** The IRS FEIE page quote confirms the exclusion is inflation-adjusted annually but the fetched copy listed figures only through 2023; a precise 2026 cap was not asserted to avoid stating a stale/unverified number.

## Notes
- All records are candidate-only; `review_status_all: pending`, `verification_status_all: representative`, `quote_verbatim_confirmed: false` on every record (human verification pending).
- `origin_country_code` and `destination_country_code` are both `US` per the batch spec (this is the US-exit-side batch); the mover's corridor is captured as `US->EC` in each record's `applies_to`.

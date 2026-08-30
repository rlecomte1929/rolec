# Attestation packet A — Tax, social security & healthcare

**Reviewer: Romain Lecomte (Founder), ReloPass — SELF-REVIEW. No external counsel engaged as of 2026-08-30.**

> WARNING — honesty note. In this system `attestation_status='attested'` is defined as an **external
> legal sign-off** (a lawyer's signature; "sellable" = verified AND attested). You are attesting these as
> the **founder, not as counsel** — record the reviewer credential exactly as *"Founder — self-review, no
> external counsel"* and treat the result as **provisional**: re-attest with a qualified cross-border tax adviser the
> moment you engage one. This packet exists so your self-review is *informed* (you read each claim and its
> source), not a rubber stamp.

**What attesting does:** each fact below is `approved` but withheld from serving today because it carries
`needs_lawyer_review` (PR #2131). Attesting it makes it serve again to Denis (NO→FR) and Andrea (ES→IE) — so review each one and
attest only the ones you are willing to stand behind.

## The 7 facts to review

| # | pillar | requirement | the claim (verbatim from the served row) | source(s) | your call |
|---|---|---|---|---|---|
| 1 | HEALTHCARE | For non-EEA nationals, immigration permission  | Where the applicant is a non-EU/EEA or Swiss national, the HSE may contact the immigration service for copies of documents proving ordinary residence, or that the applicant's permi… | https://www2.healthservice.hse.ie/files/690/ · https://assets.hse.ie/media/documents/Medical_Ca | [ ] confirm [ ] correct [ ] drop |
| 2 | HEALTHCARE | France - Two CPAM affiliation routes exist: wo | Denis simultaneously (a) resides in France and (b) works in France for a Norwegian employer whose French social-security registration (URSSAF SFE) may not be immediate. If the Norw… | https://www.service-public.fr/particuliers/vosdr | [ ] confirm [ ] correct [ ] drop |
| 3 | SOCIAL_SECURITY | France - Denis holds fodselsnummer (not D-numb | Commonly believed: all foreign nationals working in Norway hold a D-number (temporary identifier), so a D-number closure step must be completed when leaving Norway. Actually: Denis… | https://www.skatteetaten.no/en/person/national-r · https://lovdata.no/lov/1997-02-28-19/§2-14 | [ ] confirm [ ] correct [ ] drop |
| 4 | SOCIAL_SECURITY | France - Norwegian employer owes French social | Commonly believed: a Norwegian employer with no office or subsidiary in France has no French legal obligation when an employee simply works remotely from France. Actually: under Re… | https://eur-lex.europa.eu/legal-content/EN/TXT/H | [ ] confirm [ ] correct [ ] drop |
| 5 | EMPLOYMENT | Resident and domiciled means Irish tax on worl | Once resident AND domiciled in Ireland for tax purposes, the person is chargeable to Irish tax on worldwide income - the total earned anywhere in the world in the tax year - subjec… | https://www.revenue.ie/en/jobs-and-pensions/tax- | [ ] confirm [ ] correct [ ] drop |
| 6 | EMPLOYMENT | Irish tax can follow you after departure throu | A person can be non-resident for Irish tax purposes while still being ordinarily resident and domiciled, and that combination changes what income remains chargeable to Irish tax. T… | https://www.revenue.ie/en/jobs-and-pensions/tax- | [ ] confirm [ ] correct [ ] drop |
| 7 | HEALTHCARE | A Medical Card application needs evidence you  | The application requires evidence that the applicant owns or rents accommodation and that it is their family home. A newly-arrived professional in temporary or short-let Dublin acc… | https://www2.healthservice.hse.ie/files/690/ · https://www.citizensinformation.ie/en/health/hea · {'reviewer_note': 'WORDING: the HSE primary (eff | [ ] confirm [ ] correct [ ] drop |

## How to record your self-attestation (after reviewing above)
The admin attestation flow is the only path that writes `attested` (tokenised reviewer signature →
authenticated admin promote — `backend/app/routers/attestation.py`). For a founder self-review:
1. **Create the request** (admin): `POST /api/admin/attestations` scoped to `FRANCE + IRELAND tax/social/health rows`, with
   `reviewer_name="Romain Lecomte"`, `reviewer_org="ReloPass"`, `reviewer_email=<yours>`,
   `reviewer_credential="Founder — self-review, no external counsel (2026-08-30)"`. It snapshots this
   checklist and mints a one-time reviewer link.
2. **Open the link, review each item** against the claim + source above, and **sign** the ones you
   confirm. Correct or drop the rest (a corrected row goes back through the fact pipeline, not the sign).
3. The admin promote step flips the signed rows to `attestation_status='attested'`; they serve again
   immediately (verified: attestation lifts the serving withhold from PR #2131).

**Do NOT hand-edit `attestation_status` in the DB** — the two-key design routes it through the signature
so there is an accountable actor and a content snapshot. Recording it any other way is an unaccountable
claim, which is the exact thing the gate exists to prevent.

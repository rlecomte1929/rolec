# Attestation packet B — Immigration & residence

**Reviewer: Romain Lecomte (Founder), ReloPass — SELF-REVIEW. No external counsel engaged as of 2026-08-30.**

> WARNING — honesty note. In this system `attestation_status='attested'` is defined as an **external
> legal sign-off** (a lawyer's signature; "sellable" = verified AND attested). You are attesting these as
> the **founder, not as counsel** — record the reviewer credential exactly as *"Founder — self-review, no
> external counsel"* and treat the result as **provisional**: re-attest with a qualified Irish immigration solicitor the
> moment you engage one. This packet exists so your self-review is *informed* (you read each claim and its
> source), not a rubber stamp.

**What attesting does:** each fact below is `approved` but withheld from serving today because it carries
`needs_lawyer_review` (PR #2131). Attesting it makes it serve again to Andrea (ES→IE) — so review each one and
attest only the ones you are willing to stand behind.

## The 8 facts to review

| # | pillar | requirement | the claim (verbatim from the served row) | source(s) | your call |
|---|---|---|---|---|---|
| 1 | RESIDENCE | Ireland — dependant join family d visa require | Visa-required family members (a Venezuelan spouse and children) must be granted an Irish 'D' — Join Family visa BEFORE coming to Ireland. They cannot travel on the permit holder's … | https://www.irishimmigration.ie/my-situation-has | [ ] confirm [ ] correct [ ] drop |
| 2 | RESIDENCE | Ireland — csep immediate family reunification | A Critical Skills Employment Permit allows IMMEDIATE family reunification — the spouse/de-facto partner and dependent children can apply to come to Ireland with no waiting period. … | https://www.citizensinformation.ie/en/moving-cou | [ ] confirm [ ] correct [ ] drop |
| 3 | RESIDENCE | Ireland EU/EEA Entry Documents | An expired passport or national identity card does not satisfy Ireland's requirement for a valid identity document at entry. An EEA national must present a valid passport or nation… | https://eur-lex.europa.eu/legal-content/EN/TXT/? | [ ] confirm [ ] correct [ ] drop |
| 4 | RESIDENCE | Ireland — spanish residence does not grant iri | A Spanish residence card / TIE (including EU long-term resident status held in Spain) does not by itself grant the right to enter or work in Ireland. Ireland is outside the Schenge… | https://www.citizensinformation.ie/en/moving-cou | [ ] confirm [ ] correct [ ] drop |
| 5 | RESIDENCE | Ireland — spouse stamp 1g right to work | The spouse or partner of a Critical Skills Employment Permit holder is registered on a Stamp 1G on arrival, which gives the right to work in Ireland WITHOUT a separate employment p… | https://www.citizensinformation.ie/en/moving-cou | [ ] confirm [ ] correct [ ] drop |
| 6 | RESIDENCE | Ireland — leaving before registration can requ | CONDITIONAL FACT - ISD states that a visa-required national who leaves the State before their registration appointment cannot re-enter without a new entry visa. Whether a given nat… | https://www.irishimmigration.ie/registering-your | [ ] confirm [ ] correct [ ] drop |
| 7 | RESIDENCE | Ireland — a residence permit cannot be held in | A residence permit cannot be held for more than one EU country at a time. For a third-country professional moving from Spain, the existing Spanish residence authorisation and an Ir… | https://www.irishimmigration.ie/registering-your | [ ] confirm [ ] correct [ ] drop |
| 8 | RESIDENCE | Critical Skills Permit – nine-month employer m | A new employment permit for a DIFFERENT employer cannot be considered until 9 months have elapsed since the holder first commenced employment in the State under an employment permi… | https://enterprise.gov.ie/en/what-we-do/workplac | [ ] confirm [ ] correct [ ] drop |

## How to record your self-attestation (after reviewing above)
The admin attestation flow is the only path that writes `attested` (tokenised reviewer signature →
authenticated admin promote — `backend/app/routers/attestation.py`). For a founder self-review:
1. **Create the request** (admin): `POST /api/admin/attestations` scoped to `IRELAND residence rows`, with
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

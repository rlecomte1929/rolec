# SG + EC cores — browser-grounded, round 2 (2026-08-30)

Finishes the browser-grounding round started in `sg-ec-browser-grounded-2026-08-30`. Four more
verbatim facts from JS-rendered government pages, re-confirmed by `verify_ledger` (**4/4 confirmed,
0 rejected**), plus the IESS pillar fix. All landed **`pending` / `corpus_grounded`**.

## Landed
| corridor | requirement | source | note |
|---|---|---|---|
| FR→SG | **Healthcare — EP holders** | mom.gov.sg | EP holders need **no** employer medical insurance (unlike WP/S Pass) — non-obvious |
| FR→SG | **Foreign Identification Number (FIN)** | ica.gov.sg | every working foreigner gets a FIN — their SG ID |
| US→EC | **Tax residence (SRI)** | gob.ec/sri | a foreigner is an EC fiscal resident under LORTI Art. 4.1 |
| US→EC | **Work registration (SUT)** | gob.ec/mt | employer registers the hire + contract in the Sistema Único de Trabajo (no cost) |
| US→EC | **IESS — Seguro General Obligatorio** | (5 pre-staged facts) | unblocked — see below |

SINGAPORE is now **11 pending**, ECUADOR **6 pending**.

## IESS pillar normalization (honest note)
The `us-ec-facts-2026-08-30` **IESS topic was UNMAPPED** — Otto put two pillars on one topic
(4 `SOCIAL_SECURITY` + 1 `HEALTHCARE`), and a topic must map to one requirement = one pillar. At
promote time the single `HEALTHCARE` fact's **staged** pillar was normalized to `SOCIAL_SECURITY`:
IESS *is* Ecuador's social-security institute (Instituto Ecuatoriano de Seguridad Social) and the
five facts describe one requirement — enrol in IESS. This is a **staging-only** normalization; the
original batch's raw NDJSON is left unchanged as the delivery record. All 5 IESS facts now promote
as one requirement.

## Corridor core status after this round
- **FR→SG:** EP, COMPASS, application, entry, CPF, Dependant's Pass, LTVP, **tax, healthcare, FIN** —
  the core is essentially complete. Open: housing/rental (an EP holder has no address-registration
  step — a "what you don't need" determination, left unsourced rather than asserting a negative).
- **US→EC:** residence visa, tourist-trap, **tax, work-authorization, IESS**, cédula — the core is
  now covered end-to-end for Abraham.

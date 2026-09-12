# FR→NO launch gap — 2026-09-12 (EEA free movement into Norway)

**Corridor id:** `FR_NO`
**Legal shape:** French (EEA) national → Norway under EEA Agreement Art. 28 / Utlendingsloven ch. 13. **No residence permit.** Journey is police EEA registration → Folkeregister ID → skattekort → HELFO / bank.
**Pathway:** `EEA_FREEDOM_2026` (six destination steps; no origin phase; no housing step).
**Docs already here:** `QBR-knowledge-layer.md` (metrics stub, not a CVR).

This is the reverse of Denis’s live case. KEEP Otto cards in this pass are Andrea/Denis-weighted; FR→NO is still a launch corridor and the same serving rules apply.

## What is already bound

| Asset | Coverage | Serving? |
|---|---|---|
| `corridors/FR_NO/facts.yaml` | Origin: `FR:tax-exit:exit_tax`. Destination: **only** `NO:housing-husleieloven:deposit_cap_6_months` and `lease_terms`. **No `step_id`** — pathway has no housing step; facts are corridor-level on purpose. | Housing pair can load `pending`. They do **not** cover police / tax / health. |
| `backend/seeds/requirements/norway.yaml` | Broader Norway seed (QBR baseline). Lands `pending` via seeder. | Not a substitute for a FR→NO CVR. Citations historically dropped if they are bare URLs not in `source_records`. |
| Pathway graph | TRAVEL_TO_NO, EEA_POLICE_REGISTRATION (90 days), NATIONAL_REGISTRY, TAX_DEDUCTION_CARD, HEALTH_REGISTRATION, BANK_ACCOUNT | Steps without bound, cited facts |

## Gap table — missing to serve approved facts

| Topic on the pathway | Bound fact today? | Official source to fetch | Notes |
|---|---|---|---|
| No visa / no permit for EEA workers | No destination fact (silence) | `udi.no` EEA registration pages; `lovdata.no` Utlendingsloven §§109–117 | Same “speak the none” rule as NO→FR C2 |
| EEA police registration / registreringsbevis | **Missing** | `https://www.udi.no/en/word-definitions/registration-certificate-for-eueea-nationals/` (fetched via search 2026-09-12): certificate confirms **police registration**, **not** the right of residence. Register if living in Norway; typically if stay **> 3 months**. Appointment: police / SUA / `selfservice.udi.no`. | `udi.no` official. Pathway 90-day window matches UDI/politiet “main rule: within three months”. |
| D-number / personnummer / report move to Norway | **Missing** | `skatteetaten.no` national registry “moving to Norway” (UDI/politiet FAQ cites `skatteetaten.no/en/person/national-registry/moving/to-Norway/`). Confirm URL resolves before quoting. | Do not cite the 404 English path tried 2026-09-12 (`…/moving/abroad/`). |
| Skattekort | **Missing** | `skatteetaten.no` tax deduction card | UDI: apply for ID number **and** skattekort when registering as EEA |
| HELFO / fastlege | **Missing** | `helsenorge.no`, `nav.no` / HELFO pages already on the allowlist | |
| Bank account | **Missing** as a statutory fact | Often bank practice, not a statute. Do not invent a D-number-as-legal-duty-to-bank fact. | Preparation / market — same honesty as IE payslip catch-22 |
| Housing deposit / lease | **Bound** | `lovdata.no` Husleieloven §§3-5, 9-3 — already quoted in NO.yaml | Already the strongest FR→NO destination facts |
| French exit tax | Bound origin-side | `impots.gouv.fr` exit-tax page — already in FR.yaml | Not a Norwegian requirement |

## Official fetch list

| Host | Class | First page |
|---|---|---|
| `udi.no` | official | Registration certificate for EU/EEA nationals |
| `politiet.no` | official | SUA / appointment FAQ (PDF on politiet.no) |
| `skatteetaten.no` | official | Moving to Norway; skattekort |
| `lovdata.no` | official | Utlendingsloven ch. 13; Folkeregisterloven §4-1; Husleieloven (already quoted) |
| `helsenorge.no` | official | Health rights on arrival |
| `efta.int` / `eur-lex.europa.eu` | official | EEA Agreement Art. 28 if a citation must be the treaty, not UDI prose |

## What is missing to serve approved facts

1. Pending, nationality-scoped (`EU_EEA` / `OWN_NATIONAL`) candidates for police registration, Folkeregister ID, skattekort, and health — **not** copied from the TCN permit track.
2. Human approval. Norway housing seeds must not be ON CONFLICT-updated onto a reviewed row.
3. **Human CVR** for a real FR→NO mover (none in-repo). QBR stub is not a CVR. Do not invent §6-style relief metrics.

## Human CVR still required

**Yes.** FR→NO has no Case Verification Report. Housing quotes are the only destination facts with provenance-pass dates (2026-08-19). Police / tax / health are pathway prose until fetched and queued as pending.

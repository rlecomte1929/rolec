# ES→IE launch gap — 2026-09-12 (Andrea, TCN / Critical Skills)

**Corridor id:** `ES_IE`
**Legal shape:** Non-EEA third-country national (Andrea: Venezuelan, resident in Spain) → Ireland on a **Critical Skills Employment Permit**. Not free movement. Do not mirror `IE_ES`.
**Pathway:** `CSEP_2026`.
**KEEP cards:** AIQ-2314 (RP-014), AIQ-2061 (A1 destination TCN, Validation), AIQ-2160 (Andrea/Denis correctness).

## What is already bound or staged

| Asset | What it covers | Serving? |
|---|---|---|
| `corridors/ES_IE/facts.yaml` destination_facts (9) | PPSN ×2, Revenue/PAYE/emergency tax, PRSI, contribution aggregation, tax residence, split-year | Seed facts. Land `pending` if loaded. **No IRP, no CSEP, no D-visa, no LTR-non-transfer.** `origin_facts: []` |
| `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/` | 38 destination facts, all `nationality=non-EEA`, `status=professional`. Topics: CSEP (9), IRP (11), PPSN (5), RPN/emergency tax (7), health (3), tax residence (3) | Manifest names Audos `requirement_facts` (not a load this repo can run). In-repo path is `requirement_items` via Otto importer, **pending only** |
| Pathway `CSEP_2026` | Permit → D-visa (if visa-required) → IRP 90 days → PPSN → Revenue → bank / health / Stamp 4 | Graph only. Not served facts |
| ISD visa-required lookup | Wired (A3 / `ie-isd-visa-required-2026-08-22`) | Check-not-asserted for nationality the lookup cannot place |

Spain-exit / vendor / PPS pillar farms stay **parked**. Not in this brief.

## RP-014 four candidates (pending only)

| # | Claim the corridor must be able to say | Already on pathway / facts? | Official source to fetch | Disposition |
|---|---|---|---|---|
| 1 | **A Spanish / EU long-term residence right does not transfer to Ireland.** Ireland is not bound by Directive 2003/109/EC. Andrea still needs an Irish employment permit + (if visa-required) a D-visa + IRP. | Pathway exception `SPANISH_LTR_DOES_NOT_TRANSFER`. **Not** in `facts.yaml`. Third-country batch has CSEP eligibility, not this directive recitation. | `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex%3A32003L0109` — recital (25): Ireland is **not participating** and is **not bound**. Host `eur-lex.europa.eu` is official. Pair with DETE: an employment permit is **not** a residence permission (`enterprise.gov.ie` CSEP page, fetched 2026-09-12). | **MISSING as a bound fact.** New candidate only; `needs_lawyer_review`; `applies_to.nationality` = non-EEA / `THIRD_COUNTRY`. Do not approve in this pass. |
| 2 | **IRP timing as check-not-asserted** when visa-required / first registration is an `EXTERNAL_LOOKUP` or the nationality is unresolved. | Pathway: register within **90 days** of arrival (`IE_IMMIGRATION_2004_S9`). ISD page fetched 2026-09-12: non-EU/UK/Switzerland staying **more than 90 days** must register (`irishimmigration.ie/registering-your-immigration-permission/`). Last updated 23 Dec 2025. Batch already has IRP facts; two visa-sequence rows are `assertion_mode=conditional`. | Re-fetch ISD first-time registration + FAQ (`irishimmigration.ie`). Do **not** assert “Venezuela is visa-required” inside the fact — that is the A3 lookup. | **Already on pathway + A1 batch.** Do not duplicate as a new step. If promoting, keep conditional wording; IRP deadline is a published ISD/Immigration Act duty, not a visa-list assertion. |
| 3 | **Spanish social-security “tail”** (what happens to TGSS coverage when she leaves a Spanish job for an Irish employer). | **Not bound.** `origin_facts: []`. Parked Spain-exit farm must stay parked. | Only if a **cited** TGSS / Importass / `seg-social.es` page states the rule for *cessation* (employer `baja`) vs *temporary posting* (TA.300 / PD A1). A permanent new Irish contract is **not** a posting. Do not invent a “tail period”. Absent a verbatim quote on `seg-social.es`, mark **MISSING — no candidate**. | **Do not author a tail without a quote.** If Otto later fetches a TGSS baja / desplazamiento page, land pending + `needs_lawyer_review`. |
| 4 | **PPSN + Revenue / emergency tax for a permit holder.** | `facts.yaml` already binds `IE:registration-pps:*` and `IE:tax-paye:*`. A1 batch covers the same audience. | `gov.ie` PPS page; `mywelfare.ie`; `revenue.ie` emergency-tax rules (semi-official — review queue, not auto-accept). | **Already mapped.** Do not add a fourth duplicate. Confirm titles will not collide with live reviewed Ireland rows before any promote. |

## What is still missing to *serve approved* facts

1. Human lawyer / admin approval of destination rows that are already pending or staged — Otto does not flip `review_status`.
2. Candidate (1) LTR-non-transfer + DETE “permit ≠ residence permission”, if reviewers want that trap as a served fact rather than pathway copy only.
3. Origin-side Spain duties — **out of scope** (parked). Serving Andrea a complete pre-departure track waits on that farm, not on this KEEP set.
4. **Human CVR against Andrea’s real move** (AIQ-2160). Proxy gates (official host, quote, resolve, signature) are not correctness.

## Official fetch list (classify_source)

| Host | Class | Use |
|---|---|---|
| `enterprise.gov.ie` | official (`gov.ie` suffix) | CSEP criteria, €40,904 / €36,848 / €68,911 floors, €1,000 fee / 90% refund, 12-week lodgement, 9-month employer lock, **permit is not residence permission**, visa-if-required, register after arrival |
| `irishimmigration.ie` | official | IRP / first registration / FAQ |
| `eur-lex.europa.eu` | official | Dir. 2003/109/EC recital (25) Ireland opt-out |
| `gov.ie`, `mywelfare.ie`, `welfare.ie` | official | PPSN |
| `revenue.ie` | **semi-official** | Emergency tax / RPN — keep, review queue |
| `hse.ie` / `healthservice.hse.ie` | official / confirm host | Ordinary residence / medical card — already in A1 batch |
| `seg-social.es` | official | Only for a **quoted** baja / posting rule; otherwise no Spanish-SS candidate |

## Human CVR still required

**Yes — Andrea’s ES→IE session (AIQ-2160).** Judge the *set* (permit + visa + IRP + PPS + emergency tax) as one person. Do not treat counsel attestation as proof the claim is right for her.

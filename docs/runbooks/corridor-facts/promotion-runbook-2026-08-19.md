# Claude Code handoff prompt — corridor knowledge-pack promotion

Copy everything under **Prompt** into Claude Code from the repository root. This document is self-contained so the handoff does not depend on a copy sitting in a local Downloads folder.

## Prompt

You are working in the ReloPass/Audos workspace repository for workspace `d0c29613-9cb5-4652-9c6a-494eeed352e5` (`workspace-776786`). Complete a source-controlled, reproducible handoff of the 2026-08-19 corridor knowledge-pack promotion. Do not merely copy a report into the repository: encode the reviewed decisions in deterministic source data and tooling, verify the live platform state, and produce auditable reports.

### Operating constraints

- Start by reading the repository's contributor instructions, `tools/corridor-facts/README.md`, `tools/corridor-facts/gate.ts`, `tools/corridor-facts/rows.ts`, `tools/corridor-facts/schema.ts`, `tools/corridor-facts/store.ts`, `tools/corridor-facts/knowledge-pack-import.mjs`, and `data/corridor-facts/knowledge-packs/PROMOTION-REVIEW-2026-08-19.md` if present.
- Inspect current git status and preserve unrelated work. Use the repository's normal feature-branch and commit conventions.
- Do not weaken any of the four gate checks, the 12-month freshness rule, official-host jurisdiction checks, schema validation, dependency validation, or staged/preparation exclusions.
- Never invent or infer a publication date or evidence quote. Quotes below are verbatim captures from the cited official pages.
- Do not promote any row beyond the exact 22 facts and matching entities listed below. Exactly 100 pack facts must remain `pending` unless new human-reviewed evidence is supplied in a separate task.
- Do not mark the workspace or a corridor sellable. `representative` rows still await counsel attestation; passing this deterministic gate is necessary but not sufficient.
- All writes to `requirement_facts` and `requirement_entities` must use the `curated-import` server function. It is public and secret-less: enable it only for the shortest apply window and disable it in a `finally` path. Verify persisted disabled state after the run.
- Do not publish the customer app as part of this handoff.
- If the local Downloads copy of `PROMOTION-REVIEW-2026-08-19.md` differs from the repository copy, do not silently choose one. Compare both against live WorkspaceDB and preserve the live, verified values documented below.

### Background and current live result

On 2026-08-18, four flat knowledge packs were imported insert-only into WorkspaceDB with three-segment canonical keys:

- GB-NO: 28 facts + 28 entities
- FR-NO: 30 facts + 30 entities
- ES-IE: 32 facts + 32 entities
- NO-FR: 32 facts + 32 entities

All 122 facts/entities landed `status='pending'`; staged rows are excluded by `gate.ts` and not rendered by `lib/dataSheetBuilder.ts`. Sixty-six facts originally lacked `source_published_date`, and all 122 lacked `evidence_quote`.

A human provenance pass on 2026-08-19 promoted exactly 22 facts and their 22 entities: 5 `active`, 17 `representative`. Exactly 100 pack facts remain `pending`. Four pending entities were reclassified from `process_step` to `preparation_item` because they describe internal preparation/friction that no authority publishes.

Expected post-handoff counts:

| Corridor | Promoted | active | representative | pending pack facts |
|---|---:|---:|---:|---:|
| GB-NO | 2 | 1 | 1 | 26 |
| FR-NO | 3 | 2 | 1 | 27 |
| ES-IE | 9 | 2 | 7 | 23 |
| NO-FR | 8 | 0 | 8 | 24 |
| Total | 22 | 5 | 17 | 100 |

All promoted rows use `last_verified_date = 2026-08-19`. The freshness cutoff for the required gate run is `2025-08-19`.

### Goal

Make these reviewed promotion decisions durable in the repository and reproducible against WorkspaceDB. A future operator must be able to run a dry-run, see the exact planned changes, apply them idempotently through `curated-import`, re-run and see zero changes, and reproduce gate/eval reports without relying on chat history, a local Downloads file, or manually remembered database patches.

### Required implementation

1. Canonical review record
   - Ensure `data/corridor-facts/knowledge-packs/PROMOTION-REVIEW-2026-08-19.md` exists in the repository with the result, decisions, source review, verification notes, and the explicit limitation that the original Audos bridge could not run the checkout-backed CLI gates.
   - Keep this handoff prompt in the repository or preserve its full context in an equivalent operator runbook.

2. Machine-readable promotion manifest
   - Add a versioned manifest, suggested path `data/corridor-facts/knowledge-packs/promotion-2026-08-19.json`.
   - The manifest must identify every fact by `fact_uid` and every entity by `entity_id`, state the intended status, exact source/provenance/evidence overrides, `last_verified_date`, and any corrected `fact_text`.
   - Include the four preparation-item classifications and explicit nulling of their entity authority/provenance fields.
   - Include invariants: expected pack totals, expected promoted/pending counts by corridor, and `curated-import` must be disabled after apply.
   - Validate the manifest strictly: duplicate keys, unknown fields, missing quote/date/URL, stale/future dates, invalid statuses, missing matching entity, unresolved dependencies, or a promotion not in the allowlist must fail before any write.

3. Deterministic promotion runner
   - If an equivalent tool does not already exist, add a focused runner, suggested path `tools/corridor-facts/knowledge-pack-promote.mjs`.
   - Support `--dry-run` by default, `--apply`, and `--report <path>`.
   - Read current shared WorkspaceDB rows first and compare only managed columns. Never insert or delete. Refuse if a manifest key is missing or matches more than one row.
   - Apply only changed columns through `curated-import` action `update`, one key-addressed row at a time unless the existing hook gains a separately reviewed atomic batch-update contract.
   - Patch entity status/provenance before or together with its fact so the database never ends in a mismatched durable state. If a write fails, stop and report exactly which keys landed; do not claim atomicity the hook does not provide.
   - Re-read every changed row after apply and byte/JSON-compare the managed columns to the manifest.
   - A second `--apply` or `--dry-run` must report zero changes.
   - Enable `curated-import` immediately before writes, disable it in `finally`, and re-read the hook state. If the tool cannot manage hook state itself, make the operator steps explicit and still fail closed when the hook is disabled.

4. Documentation
   - Update the staged knowledge-pack section of `tools/corridor-facts/README.md` with the promotion-manifest/runner workflow, the 2026-08-19 counts, the fact that 100 rows remain staged, and links to the review and generated gate reports.
   - Document that `representative` means visible but awaiting counsel attestation, while `pending` stays non-rendered and non-gate-bearing.
   - Document the exact source-of-truth order: manifest + official source pages + live verified row comparison; a downloaded Markdown copy is an input for reconciliation, not the runtime source of truth.

### Exact promoted facts

For every promoted fact, set the matching entity to the same status and set both rows' `last_verified_date` to `2026-08-19`. Preserve all unspecified columns.

#### GB-NO

1. `GB-NO:housing-husleieloven-deposit-cap:husleieloven_deposit_cap` → `active`
   - Source: `https://lovdata.no/lov/1999-03-26-17/%C2%A73-5`
   - Published: `2026-06-12`
   - Evidence: `Det kan avtales at leieren til sikkerhet for skyldig leie, skader på husrommet, utgifter ved fraviking og for andre krav som reiser seg av leieavtalen, skal deponere et beløp oppad begrenset til summen av seks måneders leie. Det deponerte beløp skal settes på særskilt konto i leierens navn med vanlige rentevilkår i finansinstitusjon som har rett til å tilby slik tjeneste i Norge.`

2. `GB-NO:tax-uk-statutory-residence-test-exit:uk_statutory_residence_test_exit` → `representative`
   - Source: `https://www.gov.uk/government/publications/rdr3-statutory-residence-test-srt/guidance-note-for-statutory-residence-test-srt-rdr3`
   - Published: `2026-06-11`
   - Evidence: `The test allows you to work out your residence status for a tax year. Each tax year is looked at separately, so you may be resident in the UK in one year but not the next, or vice versa. The SRT takes into account: the amount of time you spend and, where relevant, work in the UK; the connections you have with the UK. You’ll be resident in the UK for the whole of a tax year, but that year may be split into a UK and an overseas part.`

#### FR-NO

3. `FR-NO:housing-deposit-cap-6-months:deposit_cap_6_months` → `active`
   - Source: `https://lovdata.no/lov/1999-03-26-17/%C2%A73-5`
   - Published: `2026-06-12`
   - Evidence: `Det kan avtales at leieren til sikkerhet for skyldig leie, skader på husrommet, utgifter ved fraviking og for andre krav som reiser seg av leieavtalen, skal deponere et beløp oppad begrenset til summen av seks måneders leie. Det deponerte beløp skal settes på særskilt konto i leierens navn med vanlige rentevilkår i finansinstitusjon som har rett til å tilby slik tjeneste i Norge. Utleieren dekker kostnadene med å opprette depositumskonto.`

4. `FR-NO:housing-lease-terms:lease_terms` → `active`
   - Source: `https://lovdata.no/lov/1999-03-26-17/%C2%A79-3`
   - Source version: `Lovdata - Husleieloven (Tenancy Act) § 9-3 — consolidated text, Sist endret LOV-2026-06-12-22, retrieved 2026-08-19`
   - Published: `2026-06-12`
   - Evidence: `Det er ikke adgang til å inngå tidsbestemt leieavtale for bolig for kortere tid enn tre år. Minstetiden kan likevel settes til ett år hvis avtalen gjelder lofts- eller sokkelbolig i enebolig eller bolig i tomannsbolig, og utleieren bor i samme hus.`

5. `FR-NO:tax-france-exit-tax:france_exit_tax` → `representative`
   - Source: `https://www.impots.gouv.fr/particulier/questions/je-quitte-la-france-suis-je-concerne-par-lexit-tax`
   - Source version: `impots.gouv.fr (French Tax Administration) — page visible date « modifié le 10/03/2026 », retrieved 2026-08-19`
   - Published: `2026-03-10` (the visible page date supersedes the earlier metadata-only `2026-03-09`)
   - Evidence: `Vous êtes concerné si vous avez été résident fiscal français pendant au moins six ans au cours des dix années précédant le transfert de votre domicile à l'étranger et si vous détenez des droits sociaux, titres ou droits atteignant une valeur globale d’au moins 800 000 € ou représentant au moins 50 % des bénéfices sociaux d’une société. Le contribuable transférant son domicile hors de France peut bénéficier d’un sursis de paiement des impositions établies à ce titre. Ce sursis est soit automatique, soit accordé sur demande faite via le formulaire n° 2074 ETD accompagné d’une proposition de garantie.`

#### ES-IE

6. `ES-IE:registration-pps-number:pps_number` → `active`
   - Source: `https://www.gov.ie/en/department-of-social-protection/services/get-a-personal-public-service-pps-number/`
   - Published: `2026-01-30`
   - Corrected fact text: `A Personal Public Service (PPS) Number helps a person access public services and is used for employment and tax administration in Ireland. An adult can apply online through MyWelfare using a basic or verified MyGovID account; the service is available both to people resident in Ireland and to customers resident abroad. The application requires evidence of identity, evidence of address and evidence of the reason the number is needed, such as taking up employment.`
   - Evidence: `If you are aged 18 years or older you can apply for a PPS Number for yourself and your child online at MyWelfare. This service is available to customers resident on the island of Ireland and customers resident abroad. To apply for a PPS Number, you must provide: evidence of your identity; evidence of your address; The reason why you need a PPSN.`

7. `ES-IE:registration-pps-proof-of-address:pps_proof_of_address` → `active`
   - Same source/date as PPS number.
   - Evidence: `The document must show your name and address and not be older than 3 months. You can use any of the following documents to do this: household utility bill; an official letter or document; a bank statement; property lease or tenancy agreement; official letter from a Government department or agency; official confirmation of address by a third party.`

8. `ES-IE:tax-revenue-myaccount:revenue_myaccount` → `representative`
   - Source: `https://www.revenue.ie/en/jobs-and-pensions/starting-your-first-job/index.aspx`
   - Published: `2026-03-19`
   - Evidence: `When you start your first job, you should notify Revenue as soon as possible, or you may have to pay Emergency Tax. To do this, you need to register for myAccount. Once registered for myAccount you can register your job by clicking 'Add Job or Pension Details' under the 'PAYE Services' tab. When you have registered your first job, Revenue will make a Revenue Payroll Notification (RPN) available to your new employer.`

9. `ES-IE:tax-emergency-tax:emergency_tax` → `representative`
   - Source: `https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx`
   - Published: `2026-02-24`
   - Evidence: `If you have provided your PPSN to your employer, but your job has not been registered with Revenue, your employer will be unable to obtain an RPN for you. Your employer will be obliged to apply the below Emergency Tax rules on your gross pay. Where you have provided your PPSN, you are allowed a single person’s rate band for the first four weeks of employment. From Week 5 onwards, your full income will be taxed at the higher rate (40%).`

10. `ES-IE:tax-paye-system:paye_system` → `representative`
    - Source: `https://www.revenue.ie/en/jobs-and-pensions/starting-your-first-job/how-your-tax-is-calculated.aspx`
    - Published: `2026-03-19`
    - Evidence: `Revenue will make a Revenue Payroll Notification (RPN) available to your employer when you have registered your job with Revenue. When your employer obtains the RPN they can calculate the correct deductions of: Income Tax; Universal Social Charge (USC); and Pay Related Social Insurance (PRSI).`

11. `ES-IE:social_security-prsi-once-employed:prsi_once_employed` → `representative`
    - Source: `https://www.gov.ie/en/department-of-social-protection/publications/prsi-pay-related-social-insurance/`
    - Published: `2026-07-23`
    - Evidence: `Most employers and employees (between the ages of 16 and pensionable age, currently 66* years) pay social insurance (PRSI) contributions into the SIF. In general, the payment of PRSI is compulsory. Most employees are liable to pay Class A PRSI.`

12. `ES-IE:social_security-combining-contributions:combining_contributions` → `representative`
    - Source: `https://www.citizensinformation.ie/en/social-welfare/irish-social-welfare-system/claiming-a-social-welfare-payment/social-insurance-contributions-from-abroad/`
    - Published: `2026-02-03`
    - Evidence: `Ireland has social security arrangements with other countries that allow you to combine social insurance contributions that you have paid in Ireland with social insurance contributions that you have paid in another country. This can help you to qualify for a social insurance payment in Ireland or in a country with whom Ireland has a social security arrangement.`

13. `ES-IE:tax-tax-residence:tax_residence` → `representative`
    - Source: `https://www.revenue.ie/en/jobs-and-pensions/tax-residence/resident-for-tax-purposes.aspx`
    - Published: `2025-11-24`
    - Evidence: `You are resident in Ireland for tax purposes if you are present in Ireland for: 183 days or more in a tax year; or 280 days or more in total, taking the current tax year plus the preceding tax year together. You will not be resident in Ireland if you are here for 30 days or less in a tax year.`

14. `ES-IE:tax-split-year-treatment:split_year_treatment` → `representative`
    - Source: `https://www.revenue.ie/en/life-events-and-personal-circumstances/moving-to-or-from-ireland/moving-or-returning-to-ireland/split-year-treatment-in-your-year-of-arrival.aspx`
    - Published: `2026-01-20`
    - Evidence: `You can request split-year treatment on your employment income for the year you move to Ireland if: you are resident in Ireland in that year; you are not resident in Ireland in the previous year; and you are going to be resident in Ireland in the year following your arrival here. Split-year treatment applies to employment income only. Employment income you earned abroad in that year before you arrived in Ireland is ignored for Irish tax purposes.`

#### NO-FR

15. `NO-FR:social_security-reg-883-via-eea:reg_883_via_eea` → `representative`
    - Source: `https://lovdata.no/lov/1997-02-28-19/§1-3a`
    - Source version: `Folketrygdloven (LOV-1997-02-28-19) § 1-3 a, lovdata consolidated text — Sist endret LOV-2026-06-19-45 / LOV-2026-06-23-65, re-read 2026-08-19`
    - Published: `2026-06-23`
    - Evidence: `EØS-avtalen vedlegg VI nr. 1 (forordning (EF) nr. 883/2004 om koordinering av trygdeordninger ...) (trygdeforordningen) gjelder som lov med de tilpasningene som følger av vedlegg VI, protokoll 1 og avtalen for øvrig. (§ 1-3 a første ledd)`

16. `NO-FR:social_security-a1-posting:a1_posting` → `representative`
    - Source: `https://europa.eu/youreurope/business/human-resources/cross-border-posted-workers/posting-staff-abroad/index_en.htm`
    - Source version: `Your Europe, “Posting staff abroad” — Last checked 12/03/2026, retrieved 2026-08-19`
    - Published: `2026-03-12`
    - Evidence: `The PD A1 confirms that the posted employee is registered under the social security system in their home country and does not need to pay contributions in the country of posting. When requesting the PD A1, you need to specify the start and end date of the posting in the other EU country. The maximum period you can indicate on the form is 24 months.`

17. `NO-FR:social_security-a1-issued-by-nav:a1_issued_by_nav` → `representative`
    - Source: `https://www.helsenorge.no/en/health-rights-living-abroad/posted-workers-in-the-eu-eea-and-switzerland/`
    - Published: `2026-03-03`
    - Evidence: `You will retain your mandatory membership of the Norwegian National Insurance Scheme if you work for up to two years in another EU/EEA country or Switzerland for your Norwegian employer and are a citizen of Norway, another EU/EEA country or Switzerland. You must attach the following: employment contract; confirmation of the assignment/posting to another EEA country or Switzerland; certificate A1 from the Norwegian Labour and Welfare Administration (NAV).`

18. `NO-FR:healthcare-s1-during-posting:s1_during_posting` → `representative`
    - Same Helsenorge source/date.
    - Evidence: `Before you leave Norway, you must apply to Helfo for certificate S1. This certificate confirms your healthcare rights in the country in which you are going to work. You must attach the following: employment contract; confirmation of the assignment/posting to another EEA country or Switzerland; certificate A1 from the Norwegian Labour and Welfare Administration (NAV). Helfo’s processing time for applications for certificate S1 is normally up to 4 weeks.`

19. `NO-FR:registration-french-social-security-number:french_social_security_number` → `representative`
    - Source: `https://entreprendre.service-public.gouv.fr/vosdroits/F23107`
    - Source version: `Entreprendre Service-Public, « Procédure et formalités d'embauche d'un salarié du secteur privé » — Vérifié le 01 juin 2026, retrieved 2026-08-19`
    - Published: `2026-06-01`
    - Corrected fact text: `Before a private-sector employee starts work in France, the employer must submit the déclaration préalable à l'embauche (DPAE) to Urssaf or MSA. The DPAE handles the employee's registration with the primary health-insurance fund or agricultural fund, and includes the employee's social-security number if they are already registered. It must be transmitted before the employee starts work or the trial period begins, no earlier than eight days before the hiring date.`
    - Evidence: `La DPAE permet à l'employeur d'accomplir les déclarations et demandes suivantes : Immatriculation du salarié à la caisse primaire d'assurance maladie ou de la MSA pour les salariés agricoles. La déclaration doit être transmise à l’organisme de sécurité sociale compétente avant la prise de fonction ou le début de la période d’essai, au plus tôt dans les 8 jours précédant la date de l’embauche.`

20. `NO-FR:tax-prelevement-a-la-source:prelevement_a_la_source` → `representative`
    - Source: `https://www.service-public.gouv.fr/particuliers/vosdroits/F34009?lang=en`
    - Published: `2026-01-01`
    - Evidence: `If you are employee or pensioner, the tax is collected by your employer or pension fund. The tax is deducted directly from your income by the collector according to a levy rate calculated by the tax authorities. If you have not yet filed a tax return, the administration cannot calculate a personalized rate. In this case, it applies you a default rate. The rate is applied on the basis of annual scale. It ranges from 0% to 43%.`

21. `NO-FR:tax-french-residence-criteria:french_residence_criteria` → `representative`
    - Source: `https://www.impots.gouv.fr/resident-de-france`
    - Published: `2026-01-27`
    - Evidence: `Vous disposez de votre domicile fiscal en France si un des critères suivants est rempli : Vous y avez votre foyer ou, à défaut de foyer, le lieu de votre séjour principal; Vous y exercez une activité professionnelle salariée ou non, à moins que cette activité y soit exercée à titre accessoire; Vous y avez le centre de vos intérêts économiques.`

22. `NO-FR:tax-worldwide-income-taxation:worldwide_income_taxation` → `representative`
    - Same impots.gouv.fr source/date.
    - Evidence: `Si vous êtes résident fiscal de France, vous êtes alors imposable sur vos revenus de sources française et étrangère, sous réserve des conventions internationales.`

### Exact preparation-item classifications

These four entities remain `status='pending'`. Set `entity_type='preparation_item'` and clear `authority`, `official_source_url`, `source_version`, `source_published_date`, and `last_verified_date` to null. Do not promote their facts.

- `GB-NO:registration-bankid-electronic-id-friction`
- `GB-NO:healthcare-interim-private-health-cover-gap`
- `ES-IE:housing-payslip-catch22`
- `NO-FR:housing-dossier-and-guarantor`

### Official-source trust-root decision

Retain these reviewed entries unchanged in `tools/corridor-facts/official-sources.ts`:

- `gov.uk` — UK government and HMRC, jurisdiction `GB`
- `legislation.gov.uk` — The National Archives / UK statute book, jurisdiction `GB`
- `rtb.ie` — Residential Tenancies Board statutory regulator, jurisdiction `IE`

The host allowlist is not blanket page approval. Every promoted fact still needs its own current page date and evidence quote.

### Dependencies that must resolve after promotion

- ES-IE: `pps_number` → `revenue_myaccount` → `paye_system`, `emergency_tax`
- ES-IE: `prsi_once_employed` → `combining_contributions`
- ES-IE: `tax_residence` → `split_year_treatment`
- NO-FR: `reg_883_via_eea` → `a1_posting` → `a1_issued_by_nav` → `s1_during_posting`
- NO-FR: `french_social_security_number` → `prelevement_a_la_source`
- NO-FR: `french_residence_criteria` → `worldwide_income_taxation`
- FR-NO: `deposit_cap_6_months` → `lease_terms`

No dependency may be removed merely to make the gate pass.

### Metrics and acceptance criteria

The implementation is complete only when all of these are demonstrated in generated reports:

1. Source-control completeness
   - One canonical Markdown review is present.
   - One strict machine-readable manifest contains exactly 22 fact promotions, 22 matching entity promotions, and 4 preparation classifications.
   - The runner and tests are committed; no required value exists only in live DB, chat, or Downloads.

2. Live data invariants
   - Promoted pack facts: exactly 22 = 5 active + 17 representative.
   - Pending pack facts: exactly 100, by corridor 26/27/23/24 as listed above.
   - Promoted facts missing `evidence_quote`: 0.
   - Promoted facts/entities missing `source_url`/`official_source_url`, `source_published_date`, or `last_verified_date`: 0.
   - Promoted source dates before `2025-08-19` or after `2026-08-19`: 0.
   - Preparation classifications: exactly the four listed; all remain pending and have null entity provenance.
   - Unexpected changed keys: 0.
   - Second apply planned changes: 0.
   - `curated-import.enabled` after completion: false.

3. Gate verdicts
   - Run from `tools/corridor-facts` with the explicit reproducible date:

```bash
npx tsx cli.ts gate --corridor GB-NO --run-date 2026-08-19 --report ../../data/corridor-facts/gate-gb-no-2026-08-19-promotion.json
npx tsx cli.ts gate --corridor FR-NO --run-date 2026-08-19 --report ../../data/corridor-facts/gate-fr-no-2026-08-19-promotion.json
npx tsx cli.ts gate --corridor ES-IE --run-date 2026-08-19 --report ../../data/corridor-facts/gate-es-ie-2026-08-19-promotion.json
npx tsx cli.ts gate --corridor NO-FR --run-date 2026-08-19 --report ../../data/corridor-facts/gate-no-fr-2026-08-19-promotion.json
```

   - Target: all four reports say `PASS` for checks (a) official source, (b) freshness, (c) schema completeness, and (d) internal consistency.
   - Do not massage data or tests to force PASS. If a report fails, preserve the report, identify whether the failure predates this manifest or was introduced by it, and fix only evidence-backed content. Never invent dates or remove dependencies.

4. Guidance and rendering evals
   - Run `lint-guidance --corridor` for each touched corridor and save reports. A warning is not a gate verdict, but newly customer-visible bookkeeping language is a release defect that must be resolved.
   - Verify `lib/dataSheetBuilder.ts` renders the 22 promoted rows according to status policy and still excludes all 100 pending facts.
   - Verify the four pending preparation items do not appear as authority-published process steps.
   - Verify existing pre-promotion active/representative facts still render and were not overwritten.

### Test and eval plan

Add or extend deterministic tests covering:

- Manifest schema rejects duplicate fact/entity keys, unknown keys, unsupported status, missing evidence quote, missing date, stale/future date, mismatched entity status, and promotions outside the 22-key allowlist.
- Dependency closure rejects a manifest that promotes a dependent while leaving its prerequisite staged.
- Dry-run emits the exact expected 22 fact + 22 entity + 4 classification plan against a pre-promotion fixture.
- Idempotency emits zero changes against a post-promotion fixture.
- Preparation-item patches clear entity provenance and never promote facts.
- Apply error reporting identifies partially completed keys and still executes hook-disable cleanup.
- Gate fixtures cover each of the four corridors with the promotion delta and assert no new failure in checks (a)–(d).
- Guidance lint evaluates every newly visible `guidance` value.

Run the existing corridor test suite plus the new tests. Record exact commands, exit codes, and report paths in the review Markdown. Do not claim a test passed without command output.

### Final deliverables

- Source-controlled review Markdown and this context/runbook.
- Machine-readable promotion manifest.
- Idempotent dry-run/apply/report tooling and tests.
- Four dated gate JSON reports and four guidance-lint reports.
- Updated README workflow and counts.
- A concise final summary containing:
  - files changed,
  - live counts before/after,
  - exact test/gate/lint commands and verdicts,
  - confirmation that `curated-import` is disabled,
  - any remaining staged-source debt or counsel-attestation work.

Commit the repository changes with a clear message and push the feature branch according to repository conventions. Do not publish the app or mark any corridor sellable.

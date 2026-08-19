# Corridor source re-verification — 2026-08-15

What was actually opened, what each official page publishes about its own
revision, and what that means for the 4-check pre-verification gate
(`tools/corridor-facts/gate.ts`) on FR-NO, NO-FR and ES-IE.

Every date below was read off the page on 2026-08-15. Nothing here is inferred,
carried over from a sibling page, or produced by a model. Where a page publishes
no revision date at all, that is recorded as a finding rather than filled in.

## Result

| Corridor | Verdict before | Verdict after | Where it stands |
|---|---|---|---|
| ES-IE | FAIL (b: 6, c: 1) | **PASS** | 6 steps + 20 requirement facts, all re-sourced to pages revised within 12 months. |
| FR-NO | FAIL (a: 5, c: 32) | **PASS** (2026-08-16 passes — see addenda) | 29 process steps + 12 preparation items + 17 requirement facts; expansion rows re-provenanced. |
| NO-FR | FAIL (a: 9, c: 63) | **PASS** (2026-08-16 pass — see addendum) | 21 steps + 18 requirement facts; authored `no-fr.json`, dead fiches replaced, BankID step reclassified. |

Reproduce with `cd tools/corridor-facts && npx tsx cli.ts gate --corridor <X> --run-date 2026-08-15`
(FR-NO / NO-FR passed with `--run-date 2026-08-16`; reports in `gate-fr-no-2026-08-16.json` and
`gate-no-fr-2026-08-16.json`).

## The structural problem check (b) creates

Check (b) requires every `source_published_date` to be no more than 12 months
old (cutoff 2025-08-15 for a run today). A corridor can therefore only pass if
the page it cites has been *republished* within the last year — not merely if the
rule it states is still correct.

That interacts badly with a second fact: **several of the authorities these
corridors depend on publish no revision date at all.** Checked today, in page
HTML, JSON-LD, meta tags and HTTP headers:

| Host | Publishes a revision date? | Evidence |
|---|---|---|
| `citizensinformation.ie` | yes | visible `Page edited: <date>` |
| `gov.ie` | yes | visible `Published on:` / `Last updated on:` |
| `irishimmigration.ie` | yes | JSON-LD `dateModified` + `article:modified_time` |
| `lovdata.no` | yes | document header field `Sist endret` giving the amending instrument's identifier and date |
| `brreg.no` | yes | JSON-LD `dateModified` |
| `info.altinn.no` | yes | visible `Last updated dd.mm.yyyy` |
| `service-public.gouv.fr` | yes | visible `Vérifié le <date>` |
| `cleiss.fr` | HTTP header only | `Last-Modified` (static files) |
| `udi.no` | **no** | no date in body, meta, JSON-LD or headers; sitemap `lastmod` is stale (skilled-workers page 2017-07-03) |
| `skatteetaten.no` | **no** | no date anywhere; `Last-Modified` header is request time |
| `politiet.no` | **no** | no date anywhere |
| `enterprise.gov.ie` | **no** | no date anywhere; sitemap `lastmod` for the permit pages is 2015 |
| `legifrance.gouv.fr` | not checkable from CI | returns HTTP 403 to the build agent |
| `nav.no` | not checkable from CI | TLS handshake fails from the build agent; the page renders without a visible date |

This is why the pre-existing ES-IE rows carried `2026-05-13` and `2026-03-01`
against `enterprise.gov.ie` pages: those pages publish no date, so those values
could not have been read from them. They were replaced with dates read from
Citizens Information, which restates the same DETE rules and does print an
edition date.

## ES-IE — what was done

Authored file: `data/corridor-facts/es-ie.json`. Gate report:
`data/corridor-facts/gate-es-ie-2026-08-15.json`.

Sources used, with the revision each page prints:

| Source | Revision published | Covers |
|---|---|---|
| Citizens Information, *Types of employment permits* | 2026-03-02 | permit required at all |
| Citizens Information, *Critical Skills Employment Permit* | 2026-04-02 | CSEP eligibility, thresholds, 2-year offer, who applies, fee |
| Citizens Information, *General Employment Permit* | 2026-03-02 | GEP route, thresholds, LMNT, 50:50 rule |
| Citizens Information, *Visa requirements for entering Ireland* | 2026-06-17 | visa-required nationality, C vs D visa |
| Citizens Information, *Registration of non-EEA nationals* | 2026-07-15 | 90-day registration, landing stamp, €300 fee |
| gov.ie, *Get a PPS Number* | 2026-01-30 | PPS purpose and evidence requirements |
| ISD, *Required documents* | 2026-07-17 | first-registration documents, appointment only after arrival |
| ISD, *Giving your details on AVATS* | 2025-10-14 | AVATS, Long Stay (D), permit reference required on the visa form |

Re-verification changed content, which is the point of doing it:

- **GEP threshold.** The stored row said `EUR 36,605 … EUR 34,009 for an Irish
  graduate … EUR 32,691 (minimum EUR 16.12/hour) for SOC 6145 roles`. The page
  says EUR 36,605, with EUR 32,691 for four named occupations (meat processing
  operative, horticultural operative, healthcare assistant, home carer). There is
  no EUR 34,009 band and no hourly figure on it.
- **Labour Market Needs Test exemption.** The stored row said the test is not
  required for roles paying over EUR 68,911. The page says EUR 64,000.
- **PPS number.** The stored row said the Irish-address requirement means the
  number "generally cannot be obtained until the employee has arrived". Both
  gov.ie and Citizens Information state the online service is available to
  customers resident abroad, so that claim was dropped.
- **D-visa mechanics.** The ISD long-stay employment visa page
  (`…/applying-for-a-long-stay-employment-visa/employment-visa/`) was last
  modified **2024-09-23** — outside the window. Its "apply up to 3 months before
  travel / documents within 30 days / apply from your home country or country of
  legal residence" detail is therefore **not** carried in the authored set. The
  visa facts are stated from the AVATS page (2025-10-14) instead. If that detail
  is wanted back, ISD has to republish it or a lawyer has to attest it.

The 20 pre-existing orphaned rows were **adopted, not duplicated**:
`tools/corridor-facts/rekey-legacy-rows.mjs` re-keyed each one from its old key
(e.g. `IE:IE-employment_visa:d_visa_timing`) onto the authored key
(`ES-IE:entry-visa:d_visa_timing`), after which the loader patched the remaining
columns. ES-IE now holds exactly 20 requirement-fact rows and 6 step rows, with
no orphans and no duplicates.

## FR-NO and NO-FR — what is still needed

Both corridors fail today on (a) and (c), and both would *acquire* new (b)
failures the moment honest dates are filled in, because their current rows have
no `source_published_date` at all and check (b) silently skips a null date.

### The unlock: lovdata prints a versioned, dated `Sist endret`

This was the decisive finding for the Norwegian side. A lovdata document header
carries a `Sist endret` field naming the last amending instrument, whose
identifier embeds its date. Read today:

| Instrument | `Sist endret` | Date | Within window? |
|---|---|---|---|
| Utlendingsloven (LOV-2008-05-15-35) | LOV-2026-06-19-50 | 2026-06-19 | yes |
| Utlendingsforskriften (FOR-2009-10-15-1286) | FOR-2026-06-19-1132 | 2026-06-19 | yes |
| Arbeidsmiljøloven (LOV-2005-06-17-62) | LOV-2026-06-19-33 | 2026-06-19 | yes |
| Skattebetalingsloven (LOV-2005-06-17-67) | LOV-2026-06-19-45 | 2026-06-19 | yes |
| Skattebetalingsforskriften (FOR-2007-12-21-1766) | FOR-2026-06-26-1385 | 2026-06-26 | yes |
| Folketrygdloven (LOV-1997-02-28-19) | LOV-2026-06-19-45 | 2026-06-19 | yes |
| Folkeregisterforskriften (FOR-2017-07-14-1201) | FOR-2025-12-17-2639 | 2025-12-17 | yes |
| Hvitvaskingsloven (LOV-2018-06-01-23) | LOV-2026-02-06-2 | 2026-02-06 | yes |
| Folkeregisterloven (LOV-2016-12-09-88) | LOV-2025-04-25-12 | 2025-04-25 | **no** |
| A-opplysningsloven (LOV-2012-06-22-43) | LOV-2025-04-25-12 | 2025-04-25 | **no** |

So `source_version` can be the amending instrument's identifier and
`source_published_date` its date — exactly the "revision identifier printed on
the page" that `apps/case-command/corridor-step-provenance.ts` asks for. Section
titles confirmed present in the consolidated texts: utlendingsloven § 55 (*Krav om
oppholdstillatelse for å kunne ta arbeid og opphold*), § 117 (*Registreringsbevis
for utlendinger med oppholdsrett*), § 108 (*Straff*); skattebetalingsloven § 5-5
(*Forskuddstrekkets størrelse*); arbeidsmiljøloven § 14-5 / § 14-6 (written
contract and its minimum content); folketrygdloven § 1-3 (*Forholdet til
EØS-avtalens hoveddel*); folkeregisterforskriften §§ 2-2-2 to 2-2-6 (d-nummer).

Two further Norwegian sources that do carry fresh dates:
`info.altinn.no` *A-melding – reporting salary and employees* (Last updated
2026-03-18: monthly filing, deadline the 5th of the following month, enforcement
fine, organisation number, automatic Aa-register employer registration), and
`brreg.no` (JSON-LD `dateModified` 2026-05-26 / 2026-08-01).

### Dead URLs found in the stored NO-FR rows

- `https://www.service-public.gouv.fr/particuliers/vosdroits/F1611` → 404
- `https://www.service-public.gouv.fr/particuliers/vosdroits/F22105` → 404

These are cited by `NO-FR-french-bank-account-droit-au-compte` and
`NO-FR-eea-national-no-residence-permit`. They pass check (a) (the host is
official) but the pages no longer exist, so the requirement text behind them is
unverified. French fiches that *do* resolve with a fresh `Vérifié le`:
F14807 (justificatif de domicile, 2026-05-19) and F492 (2025-11-19). F12859
(PUMa) is 2024-04-02 — outside the window.

### The 14 legacy step rows still fail (a) and (c)

`FR-NO` has 5 and `NO-FR` 9 step rows in `requirement_entities`, all seeded by
`apps/case-command/datasheet-seed.ts` with a bare domain in
`official_source_url` (`skatteetaten.no`, `nav.no · helfo.no`) and no provenance
columns. They **cannot** be adopted by the loader the way the fact rows were:
their `entity_id` has no corridor prefix, and ~124 Data Sheet field rows join to
them, so re-keying them would break the Personal Relocation Data Sheet. They must
be fixed in place through `apps/case-command/corridor-step-provenance.ts`, whose
`STEP_SOURCE_PROVENANCE` table is still empty. Two of them additionally cite a
host the registry does not list (`bankid.no`) or two sources in one field
(`nav.no · helfo.no`, `service-public.gouv.fr/… · douane.gouv.fr`), which is a
content decision, not a URL fix.

### Order of work for the next pass

1. Author `data/corridor-facts/fr-no.json` against the lovdata / altinn / brreg
   sources in the table above; the 17 stored FR-NO facts already carry correct
   `employee_profile`, `responsible_party` and `lead_time_days` to carry over.
2. Decide the NO-FR French-side sources: resolve the two dead service-public
   fiches, and settle whether `cleiss.fr` (2024-09-09) and EUR-Lex consolidated
   883/2004 and 987/2009 can carry facts at all under a 12-month window, or
   whether those requirements must be restated from a fresher French page.
3. Fill `STEP_SOURCE_PROVENANCE` for the 14 legacy step rows and apply the same
   values to the stored rows.
4. Re-key and import each corridor exactly as ES-IE was, then gate.

### One question for the gate's owner

If a rule is stable and its authority simply has not republished the page, an
honest `source_published_date` is older than 12 months and check (b) fails
forever. Either the corridor cites a secondary official restatement that *is*
republished often (what ES-IE now does via Citizens Information), or check (b)
needs a documented way to record "re-read on <date>, unchanged since <older
date>" — `last_verified_date` already carries the first half of that. Worth
settling before FR-NO and NO-FR are authored, because it changes which sources
they should cite.

**Decision taken on the 2026-08-16 pass:** check (b) stays exactly as it is.
No gate change; both corridors instead cite official texts that ARE republished
within the window — lovdata consolidated statutes/regulations (`Sist endret`
identifier + date), service-public fiches (`Vérifié le`), info.altinn.no and
brreg.no (`Last updated`), Your Europe (`Last checked`), and the BOFiP
convention list (dated `BOI-ANNX` identifier). `last_verified_date` keeps its
existing meaning (the day a human re-opened the page). Weakening check (b) is a
trust decision that belongs to the gate's owner, not to a backfill pass; if a
future corridor genuinely cannot be restated from a republished official page,
reopen this question then.

## Addendum 2026-08-16 — FR-NO and NO-FR now PASS

Executed exactly as the "Order of work" above prescribed. Every date below was
re-read off the page on 2026-08-16.

- **`data/corridor-facts/fr-no.json`** (11 steps, 17 facts). All Norwegian-law
  facts cite lovdata consolidated texts (utlendingsloven LOV-2026-06-19-50,
  utlendingsforskriften FOR-2026-06-25-1375, arbeidsmiljøloven LOV-2026-06-19-33,
  skattebetalingsloven LOV-2026-06-19-45, folketrygdloven LOV-2026-06-23-65,
  folkeregisterforskriften FOR-2025-12-17-2639, hvitvaskingsloven
  LOV-2026-02-06-2), plus info.altinn.no (18.03.2026) and brreg.no (23.03.2026).
  Content corrections: the NOK 409,972 family-income figure is restated as the
  3.2 G rule utlendingsforskriften § 10-8 actually prints; the folkeregister
  deadline is corrected to "three months and eight days after arrival, in
  person" per § 6-5-4 (the stored "8 weeks after the 6-month mark" appears on no
  official page); undated UDI processing-time estimates dropped.
- **`data/corridor-facts/no-fr.json`** (13 steps, 18 facts). Dead/stale French
  sources replaced: F1611 (404) → F2417 droit au compte (Vérifié 28/10/2025);
  F22105 (404) → F2651 séjour d'un Européen (01/04/2026); F12859 PUMa
  (02/04/2024, stale) → F34308 (13/05/2026). The stored impots.gouv.fr
  'questions' URLs are ALSO dead (404) and impots.gouv.fr prints no revision
  date, so the tax facts cite F34009 (15/04/2026, which also prints the
  domicile-fiscal criteria and the foreign-income acompte rule) and F369
  (05/06/2026). **cleiss.fr and EUR-Lex decision:** neither can carry facts —
  cleiss.fr is Last-Modified 2024-09-09 and the latest EUR-Lex consolidations of
  883/2004 / 987/2009 are years old. Instead the coordination facts cite
  folketrygdloven § 1-3 a (lovdata, in window), which gives both regulations
  force of statute law in Norway, and the A1/posting mechanics cite Your Europe
  (12/07/2026). The France–Norway treaty facts cite the BOFiP convention list
  BOI-ANNX-000306-20260429 (29/04/2026), which prints the Norway row; the
  substantive doctrine page (BOI-INT-CVB-NOR-20120912) is stale, so both treaty
  facts carry `professional_review_required`.
- **The 14 legacy step rows.** `STEP_SOURCE_PROVENANCE` in
  `apps/case-command/corridor-step-provenance.ts` now holds verified entries for
  5 FR-NO + 8 NO-FR steps, and the same values were applied to the stored
  `requirement_entities` rows in place (entity_ids unchanged — the ~124 Data
  Sheet field rows that join on them are untouched). Source decisions:
  `nofr-bankid-preservation` was reclassified `entity_type = 'preparation_item'`
  (bankid.no is a private operator and no authority publishes the step — the
  same class the FR-NO expansion gave 'BankID setup'), and the two dual-source
  fields were resolved to one page each ('nav.no · helfo.no' → folketrygdloven
  § 2-14 on lovdata; 'service-public… · douane.gouv.fr' → fiche F492).
- **Adoption.** `rekey-legacy-rows.mjs` was extended deterministically: a row is
  "already owned" only when its fact_uid is exactly an authored key (the old
  corridor-prefix test wrongly matched the NO-FR legacy uids), and the fact_key
  match falls back to lower-casing and stripping a '<corridor>-' prefix. FR-NO
  re-keyed 17/17 and NO-FR 18/18, with zero unmatched leftovers; both imports
  are idempotent on re-run, and ES-IE still gates PASS.

**Resolved in the expansion addendum below:** the 14 FR-NO expansion subjects
are now reviewed; 13 gate-bearing rows have dated provenance and the private-
school admissions window is a `preparation_item`.

## Addendum 2026-08-16 — FR-NO expansion provenance restored

The 25 expansion rows were already live when this pass began, so the risk was
active rather than pending. All 14 cited subjects were opened again. Thirteen
remain authority-published `process_step` rows and now carry the exact page URL,
printed revision identifier/date and `last_verified_date = 2026-08-16` in
`STEP_SOURCE_PROVENANCE` and in live `requirement_entities`. The school row was
reclassified after source review (details below). No host was added to
`official-sources.ts`.

| Expansion step(s) | Official page used | Printed revision |
|---|---|---|
| UDI skilled-worker permit; regulated-profession recognition check | Utlendingsforskriften § 6-1 | `Sist endret` FOR-2026-06-19-1132 / FOR-2026-06-25-1375; dated 2026-06-25 |
| Employer offer/letter | Utlendingsloven § 23 | `Sist endret` LOV-2026-06-19-50; dated 2026-06-19 |
| Dependant registration planning; police-registration confirmation | Utlendingsloven § 117 | `Sist endret` LOV-2026-06-19-50; dated 2026-06-19 |
| Household goods (flyttegods) | Merverdiavgiftsforskriften § 7-3-2 | `Sist endret` FOR-2026-06-26-1398; dated 2026-06-26 |
| Pet travel from France | Your Europe, *EU rules on travelling with pets and other animals* | `Last checked: 23/04/2026` |
| Used vehicle import/registration | Engangsavgiftsforskriften § 1-4 | `Sist endret` FOR-2026-01-13-29; dated 2026-01-13 |
| Brønnøysund employer/NUF check | brreg.no, *Norwegian-registered foreign business (NUF)* | `Last updated: 23 March 2026` |
| A-melding setup | info.altinn.no, *A-melding – reporting salary and employees* | `Last updated 18.03.2026` |
| RF-1198/RF-1199 assignment reporting | Skatteforvaltningsforskriften § 7-6-6 | `Sist endret` FOR-2026-07-02-1489; dated 2026-07-02 |
| Foreign-worker PAYE election | Skatteloven chapter 20 | `Sist endret` LOV-2026-06-23-66; dated 2026-06-23 |
| GP service / fastlege management | Helsenorge, *Om Helsenorge* | `Sist oppdatert 27. februar 2026` |

### The four host decisions

- **`nokut.no`: not added.** The stored label incorrectly implied NOKUT is the
  universal credential decision-maker. The row is now a regulated-profession
  recognition check, sourced to current utlendingsforskriften § 6-1, which
  expressly requires approval/authorisation where law or regulation imposes a
  qualification requirement. Authority is now the relevant professional
  authority. (The general yrkeskvalifikasjonsloven page prints 2024-06-12,
  outside the gate window.)
- **`lfo.no`: not added.** LFO is a private school, and no public authority
  publishes LFO/NLIS/OIS admissions windows. Those dates vary by school and
  academic year. The row is now `preparation_item`, its bare source and
  provenance are cleared, and its note tells the case owner to verify dates
  directly with each school.
- **`mattilsynet.no`: not added.** The Norwegian pet regulation's printed last
  amendment is 2024-08-28, outside the window. Your Europe was last checked
  2026-04-23 and directly prints the France-to-Norway dog/cat/ferret rules,
  including the 24–120 hour Echinococcus treatment window for dogs.
- **`vegvesen.no`: not added.** Engangsavgiftsforskriften § 1-4 was revised
  2026-01-13 and states that a used imported vehicle needs Statens vegvesen
  individual approval before one-off tax is calculated, and payment before
  registration.

### Content corrections made during re-verification

The undated UDI `8–16 weeks` estimate and the unsourced `25%` PAYE rate were not
carried forward. The dependant note no longer claims every family member
automatically needs a D-number. The flyttegods note now follows § 7-3-2's actual
conditions and exclusions. The pet and vehicle notes now state only the rules
printed by their replacement official pages. The dedicated Helsenorge GP-change
page prints 2025-08-12 — four days older than this run's cutoff — so that date
was recorded as a finding, not reused; the cited Helsenorge overview is dated
2026-02-27 and identifies GP management as a Helsenorge service.

Live post-backfill verification found **29 process steps**, all with absolute
allowlisted official URLs and complete in-window provenance; **12 preparation
items**; **17 sourced requirement facts**; and **134 Data Sheet field rows**.
The refreshed `gate-fr-no-2026-08-16.json` records PASS with 46 rows checked for
(a), (b) and (c), and 17 facts checked for (d). The `curated-import` write hook
was disabled again immediately after the in-place patch.

## Addendum 2026-08-16 — Otto batch `FR-NO-immig-2026-08-16.jsonl` superseded, not imported

`audos-workspace-776786/data/FR-NO-immig-2026-08-16.jsonl` (11 flat concepts,
keyed `fr-no:<slug>`, no `step_id`) was reconciled against the authored
`data/corridor-facts/fr-no.json` on 2026-08-16 and judged **superseded**. It was
NOT imported; deletion has been requested (confirmation-gated, pending the
founder). Every batch concept restates an obligation the authored set already
carries:

| Batch key | Authored `fact_key` | Match |
|---|---|---|
| `fr-no:eea_not_eu` | `eea_not_eu_status` | lexical |
| `fr-no:right_to_work` | `right_to_work_verification` | lexical |
| `fr-no:employment_contract` | `signed_employment_contract` | lexical |
| `fr-no:d_number` | `d_number_application` | lexical |
| `fr-no:skattekort` | `skattekort` | lexical |
| `fr-no:eea_police_registration` | `eea_police_registration` | lexical |
| `fr-no:bank_account` | `norwegian_bank_account` | lexical |
| `fr-no:national_registry` | `folkeregister_residence` | read side by side |
| `fr-no:social_security_a1` | `eea_social_security_coordination` | read side by side |
| `fr-no:residence_permit_non_eea` | `skilled_worker_permit` (+ `permit_window_warning`) | read side by side |
| `fr-no:employer_brreg` | `brreg_registration` | read side by side |

Why nothing was folded in (each candidate detail was checked):

- **SUA Oslo 4–6-week appointment wait; bank onboarding 2–4 weeks.** Operational
  wait times published on no dated official page (udi.no, skatteetaten.no and
  politiet.no publish no revision date — see the host table above), so neither
  can carry `source_version` / `source_published_date` and both would fail
  checks (b)/(c). The authored `eea_police_registration` and
  `norwegian_bank_account` facts already say to book/start early, without the
  unverifiable figures.
- **Article 16 extension ceiling.** The batch itself marks it
  NEEDS-CONFIRMATION; not importable content. The authored
  `eea_social_security_coordination` fact keeps the whole determination
  consult-professional, which is the correct treatment.
- **Folkeregister "6 months / within 8 days" framing.** This is the exact claim
  the 2026-08-16 authoring pass corrected: folkeregisterforskriften § 6-5-4
  requires reporting in person within **three months and eight days** after
  arrival. Importing the batch row would regress that correction.

Structural reasons an import was wrong regardless of content: the batch rows
lack `source_version` and `source_published_date` (gate checks (b)/(c) would
fail, putting FR-NO back to FAIL from its current PASS), and with no `step_id`
their keys land on two-segment `fact_uid`s (`FR-NO:<slug>`) — a live check on
2026-08-16 found zero two-segment rows, so `--apply` would have added 11 NEW
duplicate rows in a second key namespace rather than updating anything. The
batch's own `depends_on` values (`signed_employment_contract`,
`d_number_application`) are authored `fact_key`s, confirming it was written
against the canonical vocabulary and then flattened. If the file survives the
deletion request it is a research artefact only and must never be fed to
`scripts/import_otto_facts.py --apply` (with or without `--force`).

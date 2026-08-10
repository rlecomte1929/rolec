# France ⇄ Germany — Requirement Verification Report

> **Companion to `ReloPass_FR-NO_Requirements_VERIFICATION.md`, same discipline.** Every item below
> was checked against **official government or EU sources only** (gesetze-im-internet.de,
> BZSt, BMG, service-public.gouv.fr, ameli.fr, European Commission) in **August 2026**. For each:
> a **verdict**, the **exact official quote**, the **source URL**, and what to do before sign-off.
>
> **This does not tick your boxes.** `verification_status='verified'` is *your* judgment. This
> report is the evidence so your fact-by-fact sign-off is a quick confirm, not a research project.
>
> **Prerequisite for AIQ-1770.** The DE/FR data-sheet seeds must transcribe their `note` and
> `portal_url` values from this file, exactly as `20261015000000_seed_frno_data_sheet.sql`
> transcribed them from the FR→NO report. Nothing in a seed may assert a fact that is not below.
>
> **Both corridors are EEA→EEA.** Neither needs a visa, a work permit or a residence title. That
> makes the *administrative* steps the entire product surface — and it is where the two countries
> diverge sharply.

---

## Bottom line

| | FR → DE (destination Germany) | DE → FR (destination France) |
|---|---|---|
| Residence title needed | **No** — §2(4) FreizügG/EU | **No** — service-public.gouv.fr |
| Certificate/document issued | **None** for EU citizens | **None** required (card optional) |
| Arrival registration | **Yes — within 2 weeks**, statutory | **None at all** |
| Tax ID | **Automatic**, by post, no application | via CPAM, employee-initiated |
| The ambush | the 2-week clock gates everything downstream | **9-month** wait for the definitive SS number |

**11 items checked: 8 CONFIRMED, 2 PARTIAL, 1 REFUTED-AS-STATED.**

**The refuted one found a live defect.** Item 3 set out to check whether "obtain your residence
document" is a real DE step. It is not — and while checking, prod turned out to already ship
`RESID-PERMIT-DE`, an ungated template that sends *every* DE-bound employee, EEA free-movement
cases included, to an Ausländerbehörde appointment for a permit the law does not issue them.
That is the single most actionable output of this report; see item 3.

**Two items must NOT be seeded** (items 9 and 10) — one has no fetchable official quote, the
other's headline claim is unverified. They are marked rather than quietly dropped.

**The asymmetry is the headline.** Germany front-loads a hard statutory deadline; France has no
arrival registration whatsoever but carries a long administrative tail. An engine that assumes
"a destination country implies an arrival-registration step" will **invent a step that does not
exist** for France, and **under-weight** the one that does exist for Germany.

---

## Non-obvious items (the demo)

### Item 1 — DE: Anmeldung within two weeks — ✅ CONFIRMED
- **Official quote:** *"Anyone who moves into a residence is required to register with the registration authority within two weeks of moving in."*
- **Source:** https://www.gesetze-im-internet.de/englisch_bmg/englisch_bmg.html (§ 17 BMG, official English translation) · German text: https://www.gesetze-im-internet.de/bmg/__17.html
- **Why this is the whole corridor:** the Anmeldung is not one step among many — it is the **gate**.
  The Steuer-IdNr (item 2) is only triggered by it, and the `Meldebestätigung` is the document the
  bank and the employer ask for. Miss it and the downstream chain does not start.
- **Contrast with Norway, worth stating in the sheet:** Norway's police/EEA registration deadline is
  **three months** (FR→NO item 3). Germany's is **two weeks**. Anyone reasoning by analogy from the
  Norwegian corridor will be six weeks late.
- **Also confirmed:** *"persons who usually live abroad and are not registered in Germany do not have to register if they stay in Germany for less than three months"* — so a genuinely short assignment may be out of scope entirely. Keys off **actual stay length**, not the STA/LTA label (the same nuance as FR→NO item 5).
- **Change:** none. Do **not** state a Land-specific deadline — the two-week rule is federal (BMG); appointment availability is not.

### Item 2 — DE: the Steuer-IdNr is passive, and there is no published lead time — ✅ CONFIRMED (with a real gap)
- **Official quote:** *"Das BZSt teilt Ihnen Ihre IdNr zu, sobald die Meldebehörde dem BZSt die benötigten Daten übermittelt hat."*
- **Second quote (the only official timing statement):** *"Sollte Ihnen trotz Anmeldung bei der Meldebehörde nach drei Monaten keine IdNr mitgeteilt worden sein, können Sie dem BZSt eine Kopie Ihres Ausweisdokumentes und der Meldebestätigung zusenden."*
- **Sources:** https://www.bzst.de/DE/Privatpersonen/SteuerlicheIdentifikationsnummer/FAQ/faq_node.html · https://www.bzst.de/EN/Private_individuals/Tax_identification_number/tax_identification_number_node.html
- Confirmed: **there is nothing to apply for.** The Meldebehörde transmits, BZSt assigns, and — *"the IdNo can only be communicated to you through the mail for data protection reasons"* — it arrives by post at the registered address. So the sheet must say *expect a letter*, not *submit a form*.
- ⚠️ **A "four weeks after registration" figure circulates widely and I could not confirm it on any BZSt page.** The **only** timing BZSt publishes is the **three-month** point at which you may chase it. Do **not** put four weeks in the seed. Mark the lead time **ESTIMATE pending confirmation** and cite the three-month chase threshold as the hard fact.
- **Change:** none to the fact. Drop any four-week claim.

### Item 3 — DE: "obtain your residence document" is WRONG for Germany — ❌ REFUTED AS STATED
- **Official quote:** *"EU citizens shall not require a visa in order to enter the federal territory or a residence title in order to stay in the federal territory."* (§ 2(4) FreizügG/EU)
- **Source:** https://www.gesetze-im-internet.de/englisch_freiz_gg_eu/englisch_freiz_gg_eu.html
- **And there is no ordinary certificate either.** Current § 5 FreizügG/EU issues only: a **residence card for non-EU family members** (*"Dependants entitled to freedom of movement who are not EU citizens shall be issued with a residence card for dependants of EU citizens valid for five years ex officio"*, §5(1)), and a **permanent-residence certificate on application** (*"EU citizens shall be provided with a certificate confirming their right of permanent residence forthwith, upon due application."*, §5(5)).
- **Why this is flagged rather than just noted:** the old **Freizügigkeitsbescheinigung** — the certificate an EU citizen used to collect from the Ausländerbehörde — **no longer exists**. Any DE step, template or roadmap item that tells an EU employee to obtain a residence document or visit the Ausländerbehörde is instructing them to request something the law does not provide. That is precisely the failure class the honesty engine exists to prevent.

#### 🔴 This is not hypothetical — it is already live in prod

Checked against `public.form_templates` on 2026-08-10:

| code | name | trigger conditions | fires for FR→DE? |
|---|---|---|---|
| `RESID-PERMIT-DE` | Residence permit appointment (Auslaenderbehoerde) | `{destination_country: DE}` | **YES — defect** |
| `BLUE-CARD` | EU Blue Card / residence title (Aufenthaltstitel) | `{destination_country: DE, visa_type: skilled_worker}` | no |
| `WORK-VISA-DE` | National visa for employment (D-Visa) | `{destination_country: DE, visa_type: skilled_worker}` | no |
| `ANMELDUNG` | Address registration (Anmeldung beim Buergeramt) | `{destination_country: DE}` | yes — **correct** |

`RESID-PERMIT-DE` carries **no `visa_type` condition**, so it attaches to *every* DE-destination
case on `roadmap.arrival_confirmed` — including an FR→DE free-movement case. Its fields
(`biometric_photo`, `anmeldung_ref`, passport original required) walk an EU employee into an
Ausländerbehörde appointment to collect a permit that, per the quote above, they neither need nor
can be issued. Source: `supabase/migrations/20260610010000_seed_de_form_templates.sql:172-188`.

Note the inversion, because it is counter-intuitive: the two templates that *look* most alarming
(`BLUE-CARD`, `WORK-VISA-DE`) are **safe** precisely because their `visa_type: skilled_worker`
condition can never be satisfied on an EEA→EEA corridor — `trigger_engine._build_context` forces
`eea_registration` there. The **ungated** template is the one that misfires. Adding a condition is
the fix, not removing one.

- **Action:** fix `RESID-PERMIT-DE` before or alongside the DE seed — either gate it on a non-EEA
  `visa_type` or retire it. Filed as a finding, not silently patched here, because it predates this
  work and deserves its own reviewed change. When seeding DE, assert *no residence title and no
  certificate*.

### Item 4 — FR: there is **no** arrival registration in France at all — ✅ CONFIRMED
- **Official quote:** *"Si vous êtes Européen et venez travailler en France, vous pouvez demander un titre de séjour même si ce n'est pas obligatoire."*
- **Source:** https://www.service-public.gouv.fr/particuliers/vosdroits/F16003
- Confirmed: no titre de séjour obligation, and **no mairie/town-hall registration duty** — France has no equivalent of the Anmeldung or of Norway's police registration. A carte de séjour may be **requested** but is optional; permanent residence accrues after 5 years of continuous legal residence and its card is likewise optional.
- **This is the highest content risk in the DE→FR sheet.** The absence of a step is a fact, and it must be *stated* rather than left as a silent gap — otherwise an employee reasonably assumes ReloPass forgot it. Say plainly: *nothing to register on arrival; this is not an omission.*
- **Change:** none. Do not invent a "register with your mairie" step to make the corridor look symmetrical with DE.

### Item 5 — FR: the definitive social security number has a **9-month** stated instruction time — ✅ CONFIRMED
- **Official quotes:** applicants first receive a *"numéro d'identification d'attente (NIA)"*; the *"délai d'instruction est de 9 mois"* for the *"numéro de sécurité sociale définitif"*.
- **Source:** https://www.ameli.fr/assure/droits-demarches/europe-international/protection-sociale-france/ne-etranger-demander-numero-securite-sociale
- **This is the France-side ambush** — the DE→FR analogue of the SUA Oslo wait time in FR→NO. The employee is not blocked from working or from care (the NIA carries interim entitlement), but the **definitive** number can be most of a year away. Setting that expectation up front is the product.
- **Also confirmed — a French-specific document demand that catches people out:** *"Extrait d'acte de naissance avec filiation (avec le nom de vos parents)"*, or a *"Copie intégrale d'acte de naissance"*. A plain birth certificate is **not** enough — it must show parents' names. For an EU national, *"formulaire S1 ou un autre formulaire normalisé en matière de sécurité sociale"* is also listed.
- ⚠️ **Not stated on the page:** whether a sworn translation of a German birth certificate is required. Do **not** assert one either way. Leave it as a determination.
- **Change:** none. Mark the 9 months as the **official stated instruction time**, not an estimate — it is published.

### Item 6 — FR: the DPAE is the **employer's** duty, 8 days before start — ✅ CONFIRMED
- **Official quote:** *"vous effectuez une déclaration préalable à l'embauche (DPAE) auprès de l'Union de recouvrement des cotisations de la sécurité sociale (Urssaf) par Internet, par télécopie ou par courrier, dans les 8 jours qui précèdent la prise de fonction du salarié"*
- **Source:** https://www.ameli.fr/entreprise/vos-salaries/embaucher-salarie/numero-securite-sociale-salarie
- Confirmed two-step shape: **employer** files the DPAE with URSSAF in the 8 days before the start date; the **employee** then approaches the CPAM of their place of residence for the number. There is also a fully digital employer channel: *"L'Assurance Maladie met à disposition des employeurs un service en ligne qui permet d'envoyer les demandes d'immatriculation de salariés étrangers et les pièces justificatives, de façon 100 % dématérialisée."*
- **Seeding consequence:** this field belongs to the **employer**, not the employee. Do not put a DPAE action on the employee's data sheet — surface it as an HR/employer obligation, or the sheet asks the employee to do something they cannot.
- ⚠️ I could not retrieve the URSSAF page itself (connection dropped, then bot protection). The deadline is quoted above from **ameli.fr**, which is official. A second official corroboration from urssaf.fr is still worth having.

### Item 7 — A1 / posting: same rules as FR→NO, same unresolved ceiling — ✅ CONFIRMED (PARTIAL on one figure)
- **Official quote (EU Commission):** *"Workers must be insured in their home country for at least three months before being posted abroad. After 24 months of posting, there must be a break of at least two months before another posting."*
- **Source:** https://employment-social-affairs.ec.europa.eu/node/76_en · A1 / applicable-legislation framing: https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html
- Confirmed: the **24-month** standard posting limit under Art. 12 of Reg. 883/2004 applies to the FR⇄DE corridor exactly as it does to FR→NO — both are inside the EU coordination regime, so there is no corridor-specific variation to discover.
- **Carry over the FR→NO distinction verbatim:** the A1 applies only to a **genuine posting** (the home employer sends you and you keep working for them). Someone **hired locally** in the destination country is **not** posted and joins the destination scheme.
- ⚠️ **Keep the FR→NO restraint:** an **Article 16 exception agreement** can extend beyond 24 months, but **do not quote a ceiling.** The commonly cited ~5 years is not corridor-confirmed for FR⇄DE any more than it was for FR→NO. Confirm with URSSAF/CLEISS (FR side) or DVKA (DE side) before any figure reaches a customer.
- **Also unverified:** I could not fetch the Art. 12(1)/16(1) text from EUR-Lex directly (blank response on two URL forms). The 24-month figure above is from the Commission's own page, not from my reading of the Regulation. Good enough to state; not good enough to paraphrase the Article's conditions.

---

## Baseline items

### Item 8 — DE: health insurance is compulsory — ✅ CONFIRMED
- **Official quotes:** *"All citizens who reside in Germany are required to take out health insurance."* and *"In addition, SHI members must be insured in the social long-term care insurance."*
- **Source:** https://www.bundesgesundheitsministerium.de/en/themen/krankenversicherung/online-ratgeber-krankenversicherung/krankenversicherung/statutory-health-insurance-shi
- ⚠️ **The page does not state the income threshold** (`Jahresarbeitsentgeltgrenze`) above which an employee may opt out of SHI into private cover. Do **not** put a figure in the seed. Treat statutory-vs-private choice as a **determination** (`consult_professional`), which is also the honest answer — it interacts with the A1 position in item 7.

### Item 9 — DE: employer registers the employee for social security — ⚠️ PARTIAL
- Confirmed in substance: where the job is subject to German social security, the employer registers the employee with the statutory providers (health, pension, unemployment, long-term care, accident).
- ⚠️ **Sourcing limit, stated honestly:** `make-it-in-germany.com` — the official portal that carries this most clearly — is behind bot protection and returned a security-check page on every attempt, as did the BMI English pages (HTTP 400). I have **not** obtained a verbatim quote from a fetchable official source. **Do not seed this as a cited fact.** Either mark it a determination or leave it out until quoted.

### Item 10 — DE: ELStAM / wage-tax deduction needs the IdNr — ⚠️ PARTIAL, one claim explicitly NOT verified
- Confirmed: *"Der Leistungsempfänger bzw. Beitragszahler bzw. Kontoinhaber hat den zur Datenübermittlung verpflichteten Stellen auf Aufforderung seine IdNr mitzuteilen"* — the individual must supply the IdNr on request.
- **Source:** https://www.bzst.de/DE/Privatpersonen/SteuerlicheIdentifikationsnummer/FAQ/faq_Arbeitgeber_Arbeitnehmer.html
- ❌ **NOT verified:** the widely repeated claim that failing to supply the IdNr causes taxation under **Steuerklasse VI** (the highest withholding class). The BZSt employer FAQ does not say this. This is the DE analogue of Norway's 50% withholding rule (FR→NO item 1) and would be excellent sheet content — **but it must be sourced to the Finanzamt/BMF before it is asserted.** Do not seed it.
- **Action:** either find the official statement or omit. An unsourced withholding-penalty claim is exactly the kind of confident-and-wrong content that damages trust.

### Item 11 — Both: no work permit, no labour-market test — ✅ CONFIRMED (by construction)
- Follows directly from item 3 (§2(4) FreizügG/EU covers workers) and item 4. Both directions are intra-EU free movement; there is no permit to obtain and no employer sponsorship step.
- **Change:** none. But note this is *derived*, not separately quoted — same status as FR→NO items 8–9.

---

## Do this before ticking (summary)

1. **Item 2:** remove any "four weeks" IdNr lead time. Cite the **three-month chase threshold**; mark the lead time **ESTIMATE pending confirmation**.
2. **Item 3:** audit existing DE steps/templates for a residence-document or Ausländerbehörde instruction. There is no such document for EU citizens — treat a hit as a defect.
3. **Item 4:** state the *absence* of French arrival registration explicitly in the sheet, so it does not read as an omission.
4. **Item 5:** seed the **9 months** as an official published figure. Leave the birth-certificate **translation** question as a determination.
5. **Item 6:** put the DPAE on the **employer**, not the employee. Seek a urssaf.fr corroboration.
6. **Item 7:** carry over the 24-month limit and the posted-vs-locally-hired split. **Quote no Article 16 ceiling.**
7. **Items 9 and 10:** do **not** seed. One has no fetchable official quote; the other's headline claim (Steuerklasse VI) is unverified.
8. **Item 8:** no `Jahresarbeitsentgeltgrenze` figure. Statutory-vs-private is a determination.

---

## Accuracy caveats (honest limits of this check)

- All quotes were fetched **August 2026** from official government or EU sources. Government pages
  change — re-check before a customer's first real move on this corridor, per the event-gated
  re-fetch rule already applied to FR→NO.
- **Three official sources were not machine-readable and are genuine gaps, not oversights:**
  `make-it-in-germany.com` and `bzst.de` EN sub-pages sit behind Radware bot protection; the BMI
  English pages returned HTTP 400; EUR-Lex returned an empty body for Reg. 883/2004 on two URL
  forms. Every fact affected is marked PARTIAL or NOT verified above rather than quietly asserted.
- The German facts rest on **statutory text** (BMG § 17, FreizügG/EU §§ 2 and 5 in the official
  English translations) which is the strongest available basis — stronger than the portal prose
  the FR→NO report had to rely on in places.
- **No item was verified in the customer's own language pair end-to-end.** As with FR→NO's A1 path,
  no single official page states "German national moving to France" or vice versa; the corridor is
  assembled from mutually consistent single-country sources.
- This report verifies **facts, not engine logic**. Which items apply to a given case — the
  under/over-three-months split in item 1, posted vs locally hired in item 7 — is a separate
  correctness question.
- Nothing here is `verification_status='verified'`. The DE/FR seeds must ship
  **`representative`**, and only your fact-by-fact sign-off changes that.

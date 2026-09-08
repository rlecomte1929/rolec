# France → Norway — Corridor Requirement Set (DRAFT for sign-off)

> **Purpose:** the authoritative content to load into `requirement_items` for the France→Norway (EEA) corridor, so Case Command / the public endpoint surfaces the *non-obvious* items — not just passport + employment letter.
>
> **Status:** core facts verified against official Norwegian sources (Skatteetaten, UDI, politiet) in July 2026 — see Sources. **Romain is still the final quality bar:** confirm fact-by-fact, then flip `verification_status` from `representative` → `verified`. Do not ship as gospel until you've signed off.
>
> **Scope note (important):** the engine is *destination-only*. This set assumes an **EEA-national employee moving from France** (a French citizen). Norway is **EEA but not EU**, so free movement applies (start work immediately, no work permit) — but the registrations below are mandatory and deadline-bound. A **third-country national** moving from France would need a residence/work permit instead; that's a different requirement set and the engine can't express it yet.

---

## Sign-off protocol (this is the human accuracy gate)

Each item below has a **`SIGNED OFF`** checkbox. Tick it (`[ ]` → `[x]`) **only after** you've verified that item against its linked source. Claude Code sets `verification_status='verified'` **only** on items whose box is ticked; unticked items load as `representative`. Never auto-verify. This is your judgment, not a value copied from this file.

- Tick to sign off: change `- [ ] **SIGNED OFF**` to `- [x] **SIGNED OFF**`.
- Leave unticked anything you haven't personally confirmed.

---

## Schema additions needed first

Your `requirement_items` table has no way to drive the "flag the non-obvious ones" demo. Add two fields:

- **`non_obvious`** (boolean) — is this something a non-expert wouldn't know to look for? This is what the face flags.
- **`timing`** (text) — when it must happen (e.g. "before first salary", "within 3 months of arrival"). Drives the "week-seven ambush in week-one" value.

Also: populate **`citations_json`** with the official source URLs below, and set **`verification_status = 'verified'`** per item once you sign off (all Norway rows are currently `representative` = unverified placeholder).

---

## The signature NON-OBVIOUS items (the demo — currently missing or vague)

**1. Tax deduction card (skattekort) — before the first payroll**
- Pillar: `TAX` (or SOCIAL_SECURITY) · Severity: **BLOCKER** · Applies: all (anyone earning salary) · **non_obvious: true** · **timing: before first salary payment**
- *Description:* Your employer must retrieve your electronic tax deduction card (skattekort) from Skatteetaten **before your first salary**. If it isn't on file, the employer is legally required to withhold **50% of your salary** automatically until it is. This is the classic week-seven shock — pay lands halved.
- Status in DB: **MISSING.** Add.
- Source: skatteetaten.no (tax deduction card)
- [ ] **SIGNED OFF** (Romain) — verified against source

**2. D-number (temporary identity number) — for stays under 6 months**
- Pillar: `IDENTITY` · Severity: **BLOCKER** · Applies: STA / any stay < 6 months · **non_obvious: true** · **timing: on arrival — via in-person tax-office appointment; issued together with the tax card**
- *Description:* Anyone in Norway under 6 months gets a **D-number**, not a national ID. For an EEA worker it's issued by Skatteetaten when you apply for the tax card, and requires an **in-person appointment to verify identity**. Without it you can't be paid correctly, open a bank account, or function administratively.
- Status in DB: **MISSING as a distinct item** (the folkeregister row is adjacent but not this). Add.
- Source: UDI (D-number) / Skatteetaten
- [ ] **SIGNED OFF** (Romain) — verified against source

**3. Police registration for EU/EEA nationals (registration certificate)**
- Pillar: `RESIDENCE` / IMMIGRATION · Severity: **WARN→BLOCKER** · Applies: LTA / PERMANENT (any stay > 3 months) · **non_obvious: true** · **timing: no later than 3 months after arrival**
- *Description:* EEA nationals may start work immediately, but if staying **more than 3 months** they must **register with the police** within 3 months of arrival and receive a registration certificate. Registration is free but requires the **employment contract/certificate** as proof. Easily missed because you can legally work before doing it.
- Status in DB: **MISSING.** Add.
- Source: UDI (EU/EEA registration certificate) / politiet.no
- [ ] **SIGNED OFF** (Romain) — verified against source

**4. Social-security coordination — A1 certificate vs. folketrygden membership**
- Pillar: `SOCIAL_SECURITY` · Severity: **WARN** · Applies: STA / posted workers primarily · **non_obvious: true** · **timing: before or at start of assignment**
- *Description:* Working in Norway normally makes you a member of Norwegian National Insurance (**folketrygden**). But a **posted** French employee can often remain in the French social-security system by obtaining an **A1 certificate** from France — avoiding double contributions. Which applies depends on the posting structure. *(Verify the specific A1 conditions for your case types before shipping.)*
- Status in DB: partially — "National Insurance (folketrygden)" exists, but the A1 nuance is missing. Refine + add A1.
- Source: **needs verification** — EU/EEA social-security coordination (A1); confirm current conditions before sign-off
- [ ] **SIGNED OFF** (Romain) — verified against source

---

## Baseline items (mostly present — keep / refine)

**5. National identity number — report a move (folkeregister), for stays ≥ 6 months**
- Pillar: `RESIDENCE` · Severity: WARN · Applies: LTA / PERMANENT · non_obvious: false · timing: after arrival, in person at one of the designated tax offices
- *Description:* Staying **6 months or more** means you must **report a move** to the Tax Administration and are assigned a **national identity number** (fødselsnummer), which then replaces any D-number. Present in DB as "Residence registration (folkeregister)" — keep, refine wording to the 6-month rule + national ID number.
- Source: Skatteetaten (national identity numbers) / UDI
- [ ] **SIGNED OFF** (Romain) — verified against source

**6. Valid travel document — passport or EEA national ID card**
- Pillar: `IDENTITY` · Severity: BLOCKER · Applies: all · non_obvious: false
- *Refine:* DB says "Valid passport (6+ months)". As an **EEA national**, a valid **national identity card** is also acceptable for entry — soften from passport-only.
- Source: UDI (EU/EEA entry) — confirm
- [ ] **SIGNED OFF** (Romain) — verified against source

**7. Employment contract / certificate**
- Pillar: `EMPLOYMENT` · Severity: WARN · Applies: all · non_obvious: false
- *Description:* Needed both as the basis of the move **and** as the document you must present to the police for EEA registration (item 3). Present in DB — keep; add the cross-link note.
- Source: UDI (employer / EU-EEA employee)
- [ ] **SIGNED OFF** (Romain) — verified against source

**8. Long-term housing contract**
- Pillar: HOUSING · Severity: WARN · Applies: LTA/PERMANENT · non_obvious: false
- Present in DB — keep. Source: internal / confirm
- [ ] **SIGNED OFF** (Romain) — verified against source

**9. Minimum lead time**
- Pillar: TIMELINE · Severity: WARN · Applies: all · non_obvious: false
- *Description:* Consider deriving it from the deadlines above (skattekort before payroll; police within 3 months). Present in DB — keep.
- Source: derived from items 1 & 3
- [ ] **SIGNED OFF** (Romain) — verified against source

---

## Gap summary (what to change in `requirement_items`)

- **ADD:** skattekort-before-payroll (1), D-number (2), police/EEA registration (3), A1 social-security coordination (4).
- **REFINE:** folkeregister → 6-month national-ID framing (5); passport → allow EEA ID card (6); folketrygden → link to A1 (4).
- **KEEP:** employment contract (7), housing (8), lead time (9), passport as baseline.
- **SCHEMA:** add `non_obvious` + `timing`; backfill `citations_json`; set `verification_status = 'verified'` **only on ticked items**.
- **ACCURACY NUANCE:** the D-number vs national-ID split is driven by **actual stay length (≶6 months)**, not the STA/LTA label. Ideally the engine keys off duration; using assignment type is a proxy that can misfire (a 5-month LTA, an 8-month STA).

---

## Sources (verify against these before ticking sign-off)

- Skatteetaten — Tax deduction card / order: https://www.skatteetaten.no/en/person/taxes/tax-deduction-card-and-advance-tax/order-a-tax-deduction-card/
- Skatteetaten — Tax deduction cards for foreign employees: https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/
- UDI — D number: https://www.udi.no/en/word-definitions/d-number/
- UDI — National identity number: https://www.udi.no/en/word-definitions/national-identity-number/
- UDI — Registration certificate for EU/EEA nationals: https://www.udi.no/en/word-definitions/registration-certificate-for-eueea-nationals/
- UDI — Employee who is an EU/EEA national: https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/
- Skatteetaten — National identity numbers / reporting a move: https://www.skatteetaten.no/en/person/national-registry/identitetsnummer-og-elektronisk-id/fodselsnummer/
- Nordic co-operation — Norwegian identification numbers: https://www.norden.org/en/info-norden/norwegian-identification-numbers

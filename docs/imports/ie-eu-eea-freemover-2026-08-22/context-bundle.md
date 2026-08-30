# Context Bundle — Ireland EU/EEA free-mover requirements

**Run:** AIQ-1994 (research) → AIQ-2028 (load) · Bridge run #1
**Loop role:** this is the **read-only context bundle** (loop step 1). Otto relays it to Cursor; Cursor returns title/reconciliation **decisions**; Cowork verifies them vs prod; Claude Code (wired applier) derives SQL, dry-runs, and promotes to **pending**; Cowork verifies the result.
**Prod snapshot:** ReloPass `nsvefcvpvwwwhuqyuqmp` (eu-west-1), read 2026-08-22.
**Target:** `public.requirement_items`, destination **IRELAND**, nationality **EU/EEA free-mover**.

---

## 0. What Cursor is being asked to decide

Produce the **generic EU/EEA free-mover requirement set for Ireland** — the practical "what an EU national actually does on arrival in Dublin" list — as keyed NDJSON facts, **deduplicated against what Ireland already has**, mirroring the shape France already models. For each proposed requirement, decide a **title** that does *not* collide with a live row, and label it **net-new / duplicate / update**.

**Cursor decides titles and reconciliation. It does not emit SQL.** The wired applier owns SQL, id derivation, dry-run and promote.

---

## 1. ⚠️ Corrected premise — this is a reconciliation, not a greenfield load

The AIQ-2028 card says *"Ireland genuinely has zero EU/EEA free-mover rows today — all 14 IE requirement_items are THIRD_COUNTRY."* **That is stale.** As of 2026-08-22 prod holds:

- **65** live `requirement_items` for `country_code = 'IRELAND'`.
- **6** already scoped `["OWN_NATIONAL","EU_EEA"]` (see §4) — all `purpose=employment`, all promoted from the ES→IE batch (topic keys `*_eea`), so worded Spain-side.
- **6** more with `applies_to_nationality_classes_json = NULL` (= applies to everyone, free movers included).
- ~53 `THIRD_COUNTRY`.

So the free-mover set is **partially built** (tax / PPSN / PRSI / USC / health / A1-posted-worker). The job is to add the **residence-right, entry, identity and registration** facts that are still missing, without overwriting the 12 rows that already serve a free mover. This dedupe-against-a-live-corpus reconciliation is exactly what the bridge is for.

---

## 2. Target schema + the hard rules

**Table:** `public.requirement_items`. **Natural upsert key:** `(country_code, purpose, title)` — `crud.create_requirement_item` upserts on this and **rewrites description/severity/owner/citations on collision.** Never emit a row whose key matches a live row (§4) unless the intent is deliberately to update it.

Columns the promote path writes: `id, country_code, purpose, pillar, title, description, severity, owner, required_fields_json, citations_json, applies_to_nationality_classes_json, verification_status, review_status, non_obvious, timing, last_verified_at`.

**Two hazards, both load-breaking:**

1. **`review_status` DEFAULTS to `'approved'`.** A row inserted without it is served to real users immediately. The load **must** set `review_status = 'pending'` explicitly. Only `approved` is served (`requirements_builder` returns approved only); the flip is the human lawyer gate at `/admin/countries`.
2. **`country_code` is the catalog NAME `IRELAND`, not the ISO code `IE`.** Staging (`otto_staging`) keys on `IE`; `requirement_items` keys on `IRELAND` (`iso_to_catalog_name('IE') → 'IRELAND'`). The deterministic id is:

   ```
   id = uuid5( a1c9e349-0000-4000-8000-000000000001 , "IRELAND|<purpose>|<title>" )
   ```
   (`_SEED_NS` in `backend/scripts/seed_requirements.py`, reused by the Otto executor.) The applier derives this — Cursor does not.

---

## 3. Mapping rules (`backend/imports/otto/mappings.py :: resolve()`)

Every target column is derived from a **bounded** field; an unrecognised value is a **refusal** (`Unmapped`), never a default. For this batch:

| Target | Derived from | This batch |
|---|---|---|
| `applies_to_nationality_classes_json` | `applies_to.nationality` | **`"EU"` or `"EEA"` → `["OWN_NATIONAL","EU_EEA"]`**. Never `"any"` — `"any"` is refused (it would serve a visa track to free movers). |
| `purpose` | `applies_to.status` | **`"professional"` → `employment`**. (`student→study`, `family→family`, `any→other`.) |
| `pillar` | `domain_area='immigration'` → `RESIDENCE` | ⚠️ see note below. |
| `severity` | not derivable | default `WARN`; `BLOCKER` only where a human sets it (France sets it on passport). |
| `owner` | — | default `EMPLOYEE`. |
| `verification_status` | evidence | `corpus_grounded` only if **every** fact is official-sourced **and** carries an `evidence_quote`; otherwise `representative`. Expect `representative`. |
| `non_obvious` | any fact's `applies_to.non_obvious` | set `true` where the official page and lived reality diverge — it drives the client badge. |
| `citations_json` | `source_url` per fact | **object form** `{"url":…, "topic_key":…, "name":…, "needs_lawyer_review":…}` — never bare URL strings (a bare URL matches nothing in `source_records` and serves an empty citation). |

**⚠️ Pillar caveat (AIQ-2036).** `resolve()` currently hardcodes `pillar=RESIDENCE` for every immigration row, but the live IE/FR free-mover rows use richer pillars — **`RESIDENCE, HEALTHCARE, HOUSING, IDENTITY, EMPLOYMENT, SOCIAL_SECURITY`**. Those were set by hand-authored seeds or a manual re-pillar after promote. So: have Cursor **carry `applies_to.pillar` on each fact** (mirroring the FR analogue in §5), and the applier either lands AIQ-2036 first (make `resolve()` read `applies_to.pillar`) or does the one manual re-pillar pass after promote. Do **not** let everything collapse to `RESIDENCE`.

---

## 4. Live tripwire rows — DO NOT collide (append-only)

These already serve an Irish free mover. A new fact that duplicates one of these topics is a **duplicate** (drop it), not a new requirement. The md5 fingerprint over these rows must be unchanged after apply.

**Already `["OWN_NATIONAL","EU_EEA"]` (promoted, `purpose=employment`):**

| Existing title | staging topic_key |
|---|---|
| A1 Certificate — Posted Workers from Spain (EU/EEA nationals) | `a1_posted_worker_eea` |
| Public Health Entitlement — Ordinary Residence (EU/EEA nationals) | `health_entitlements_eea` |
| Irish Income Tax — Rates and Bands (EU/EEA nationals) | `income_tax_basics_eea` |
| PPS Number — Application and Uses (EU/EEA nationals) | `ppsn_application_eea` |
| PRSI — Compulsory Social Insurance (EU/EEA nationals) | `prsi_social_insurance_eea` |
| Universal Social Charge — Threshold (EU/EEA nationals) | `usc_universal_social_charge_eea` |

**Already `NULL` nationality (applies to everyone, incl. free movers):**
Contributions paid abroad can be combined with Irish contributions · Irish tax residence turns on 183 days in a year, or 280 across two · PRSI is compulsory for most employees between 16 and pensionable age · Register the job with Revenue through myAccount to avoid emergency tax · Split-year treatment can be requested for the year of arrival · The employer's RPN drives Income Tax, USC and PRSI deductions.

> Note for Romain: the 6 EU/EEA rows are worded Spain-side ("Posted Workers **from Spain**"). A generic EU mover to Dublin from anywhere sees odd copy. Re-wording them to corridor-neutral titles is a **separate** change (it alters the upsert key) — flagged, not in scope here.

---

## 5. The France EU/EEA template — the shape to mirror

France already models the free-mover set (15 live `["OWN_NATIONAL","EU_EEA"]` rows). Mirror its **topic coverage, pillar assignment, title style, severity and `non_obvious` calls** for Ireland:

| FR title | pillar | purpose | severity | non_obvious |
|---|---|---|---|---|
| Entry to France — No Visa for EEA Nationals | RESIDENCE | employment | WARN | false |
| EU/EEA/Swiss citizen – worker right of residence (optional carte de séjour) | RESIDENCE | employment | WARN | false |
| Carte de séjour UE/EEE — Optional Residence Card for EEA Workers | RESIDENCE | employment | WARN | true |
| EEA Residence Right if Involuntarily Unemployed | RESIDENCE | employment | WARN | true |
| Valid passport or national identity card | IDENTITY | employment | **BLOCKER** | false |
| French health cover (CPAM affiliation) | HEALTHCARE | employment | WARN | false |
| French Social Security Number (NIR) — Assignment | RESIDENCE | employment | WARN | true |
| French Tax Domicile — CGI Article 4B | RESIDENCE | employment | WARN | true |
| Justificatif de domicile (proof of French address) | HOUSING | employment | WARN | false |
| Signed French employment contract | EMPLOYMENT | employment | WARN | false |
| Single-State Social Security Principle (Reg. 883/2004) | RESIDENCE | employment | WARN | true |
| A1 Certificate — Workers Posted from Norway | RESIDENCE | employment | WARN | true |
| EU/EEA/Swiss citizen – permanent residence card (after 5 continuous years) | RESIDENCE | **other** | WARN | false |
| EU/EEA/Swiss citizen – student right of residence | RESIDENCE | study | WARN | false |

---

## 6. The gap — candidate net-new requirements for Ireland

Cross-referencing the France template (§5) against what Ireland already has (§4), the genuinely-missing free-mover requirements are the **residence-right / entry / identity / registration** ones. Suggested set (Cursor decides the final list + exact titles + sourcing):

1. **Entry & residence without a visa or permit** — an EU/EEA/Swiss national enters and works in Ireland with no visa, no employment permit, no IRP registration. *(This is the card's headline — the "one notice and nothing else" gap.)*
2. **No residents' registration in Ireland** — unlike Spain's *padrón*, Ireland has no municipal registration; address is proven ad hoc (utility bill / tenancy) for PPSN etc. `non_obvious=true`.
3. **Valid passport or national identity card** — IDENTITY pillar; mirror FR (note: Ireland is outside Schengen and the CTA nuance for Irish/UK).
4. **Right of residence retained if involuntarily unemployed** — register with the relevant office, mirror FR.
5. **Single-State Social Security (Reg. 883/2004)** — the *general* single-state rule for an ordinary EU hire in Ireland (distinct from the existing Spain **posted-worker A1** row).
6. **Proof of address for administrative steps** — HOUSING; the Irish analogue of *justificatif de domicile*.
7. *(optional, lower value)* Permanent residence / long residence after 5 years; "signed Irish employment contract as the unlock."

Exclude anything already covered in §4 (PPSN, PRSI, USC, income tax, health entitlement, A1 posted worker, tax residence, RPN, emergency-tax registration).

---

## 7. Fact NDJSON contract (`otto_staging.immigration_fact_candidates`)

**One JSON object per line (JSONL).** Grain: **one entity (topic) = one requirement**; multiple facts per topic compose one description. `dedupe_key = "IE|<entity_topic_key>|<fact_key>"` is UNIQUE.

Required fields per line: `destination_country` (`"IE"`), `entity_topic_key`, `fact_key`, `fact_text`, `source_url`.
Optional/understood: `entity_title`, `fact_type` ∈ `{eligibility, step, document, deadline, fee, where_to_apply, other}`, `evidence_quote` (verbatim), `confidence` ∈ `{high, medium, low}`, and `applies_to` (jsonb) carrying:

```json
"applies_to": {
  "nationality": "EEA",              // → ["OWN_NATIONAL","EU_EEA"]; never "any"
  "status": "professional",          // → purpose=employment
  "pillar": "RESIDENCE",             // one of RESIDENCE/HEALTHCARE/HOUSING/IDENTITY/EMPLOYMENT/SOCIAL_SECURITY
  "non_obvious": true,               // where official vs reality diverge
  "needs_lawyer_review": false,      // rides into the citation
  "source_name": "Citizens Information",
  "corridor": "any_eu_to_ie",
  "quote_verbatim_confirmed": true   // false = captured but not re-checked → downgraded
}
```

Every topic must carry a single, consistent `nationality` and `status` across its facts (a topic whose facts disagree is refused as "not one requirement").

---

## 8. Sourcing gate (`classify_source`) — cite the statutory publisher

A fact's **publisher domain** decides how far it is trusted. UNOFFICIAL (blogs, law firms, relocation vendors) is **rejected outright** — no exceptions. Every fact needs a verbatim `evidence_quote`, or it is downgraded to `needs_review`.

- **OFFICIAL (auto-acceptable) for Ireland:** `*.gov.ie`, `irishimmigration.ie`, `hse.ie`, `rtb.ie`, `ndls.ie`, `rsa.ie`, `welfare.ie`, `mywelfare.ie`. **EU:** `europa.eu` (incl. `eur-lex`, `ec.europa.eu`).
- **SEMI_OFFICIAL (kept, but forced to `needs_review`):** `citizensinformation.ie`, `revenue.ie`, `youreurope.europa.eu`.
- Anything else → **rejected**. (This allowlist has been too narrow before — every `.ie` statutory body that isn't `gov.ie` had to be named explicitly. If a fact's natural source isn't listed here, flag it rather than downgrading silently.)

For the free-mover set: right-of-residence and entry facts → `citizensinformation.ie` / `europa.eu`; PPSN → `mywelfare.ie` / `welfare.ie`; health → `hse.ie`; tenancy/address → `rtb.ie`; licence → `ndls.ie` / `rsa.ie`.

---

## 9. What Cursor returns (the DECISIONS artifact)

Reviewable **markdown** (not SQL, not pasted into chat — delivered as a **file**), one block per proposed requirement:

- **Chosen title** + explicit collision check against §4 (exact + fuzzy) → verdict `net-new` / `duplicate-of:<title>` / `update:<title>`.
- `entity_topic_key`, `purpose`, `pillar`, `nationality`.
- The facts (each: `fact_key`, `fact_type`, `fact_text`, `source_url`, `evidence_quote`, `non_obvious`, `source_class`).
- A one-line rationale (what it adds that §4 doesn't already have).

Plus the **NDJSON** file (§7) + a **manifest** (schema, record count, full GCS URL) for the applier.

---

## 10. Governance + verification recipe

**Promote-to-PENDING only.** Rows land `review_status='pending'` → not served. The flip to served is the human lawyer gate at `/admin/countries`. Append-only; never overwrite a §4 row. After the applier's dry-run (`BEGIN … ROLLBACK`, before/after count, pre-image fingerprint) and apply, **Cowork verifies vs prod:**

- `count(*)` for IRELAND EU/EEA = old + N.
- md5 fingerprint over the untouched rows (`string_agg(id||title||description||verification_status||review_status ORDER BY id)`) **unchanged**.
- `verified`/`expert_verified` counts **unchanged** (nothing over-claimed).
- the N new rows present, all `review_status='pending'`, correct pillar/purpose, `applies_to_nationality_classes_json=["OWN_NATIONAL","EU_EEA"]`.
- mark the promoted staged facts `status: new → promoted`.

---

## 11. The four rules + roles (do not skip)

1. **Cursor decides, doesn't SQL** — judgment is its strength.
2. **The wired applier owns SQL + dry-run + apply** — it knows the id/mapping derivation.
3. **Cowork verifies independently** via direct prod read — never the executor.
4. **Relay artifacts as files, not pasted text** — paste corrupts; files arrive intact.

Otto = research + relay · Cursor = reconciliation + titles (no prod/repo) · Claude Code = wired applier (repo + prod + gh) · Cowork = independent verifier + this bundle · Human = the lawyer gate.

---

## 12. Open items for Romain

- **Stale card premise** — AIQ-2028 says "zero EU/EEA rows / 14 items"; prod has 65 rows and 12 that already serve free movers. Worth updating the card, and re-checking its "re-measure the France baseline" acceptance test against the real numbers (FR EU/EEA is now 15 rows, not 7).
- **AIQ-2036 (pillar)** should ideally land before this promote so pillars aren't hand-set afterwards — see §3.
- **Spain-worded EU/EEA rows** (§4) may deserve corridor-neutral re-titling later (separate change; alters the upsert key).

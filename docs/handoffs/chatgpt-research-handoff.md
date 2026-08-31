# ReloPass — ChatGPT research handoff (corridor / cities / services)

**Purpose.** Offload the *research* half of the corridor-knowledge pipeline to ChatGPT (which
needs no repo or database access), and keep Claude Code / the operator for the in-repo
*verify → stage → promote* half. This conserves the Claude and GitHub quota while producing
artifacts that drop straight into the existing importers with **no rework**.

**Golden rule.** ChatGPT produces **candidates only, in an exact format, with a real cited
source and a verbatim quote for every fact.** It never invents a source, number, phone, or
confidence. Anything it cannot verify is **omitted and noted**, never guessed. This is the whole
value — the pipeline's entire point is auditability.

---

## 1. What ReloPass is, and the moat

ReloPass turns a cross-border corporate relocation into a guided, compliant journey (personas:
Employee, HR, Admin). Its durable moat is a proprietary **corridor knowledge graph** —
*country-pair × employee-type × current requirements* — continuously verified and kept current.

The valuable part is **not** the requirement list a government website already gives. It is the
**divergence between what official guidance says and what actually happens** on the ground — the
thing an HR generalist cannot get from a gov page and the thing a relocating employee is
blindsided by. Prefer facts that capture that divergence, deadlines, chicken-and-egg traps, and
"non-obvious" gotchas.

---

## 2. Pick something NEW (don't redo covered work)

Three research products are wanted. Pick a target that is **not already covered**:

**A. A corridor** = an origin→destination country pair for a persona (e.g. `FR→DE` for a
non-EEA professional). Corridor *pairs* worked end-to-end already: **ES→IE, NO→FR, FR→SG,
US→EC**. Destination-level candidate facts already exist for ~37 countries (NO, DE, FR, IE, US,
CH, SG, NL, AT, NZ, DK, AU, CA, PT, SE, BE, ES, GB, AE, JP, …). **High-value NEW corridors to
pick from** (named as parked hubs, thin or missing on the *origin/pair* side):
`FR→DE`, `ES→DE`, `IE→DE` (Germany hub); `NO→NL`, `FR→NL` (Netherlands hub, 30% ruling);
`SE→NO`, `DK→NO`, `FI→SE` (Nordic); `GB→NO`, `NO→GB` (post-Brexit).

**B. A list of cities** = destination-city enrichment (neighborhoods, transport, schools,
banking, healthcare, practicalities, cost of living). Done so far: Stavanger, Copenhagen, Oslo
(+ provider cities Dublin, Madrid, Paris). **NEW city picks:** Berlin, Munich, Frankfurt,
Amsterdam, Rotterdam, Singapore, Zurich, Lisbon — ideally the main arrival city of a corridor
above.

**C. A list of services (suppliers)** = vetted providers per service category for a corridor's
destination city, harvested from an **official registry** (movers, legal/immigration, banking,
housing/relocation, tax). Provider batches exist for Dublin, Madrid→Dublin, Paris, FR→SG, US→EC.
**NEW picks:** providers for any city in a NEW corridor above (e.g. Berlin movers/legal/banking).

> You do **not** need to guarantee novelty perfectly — the in-repo importers dedupe on the
> natural key and the reviewer confirms. But state which corridor/city/category you chose and
> why you believe it is new.

---

## 3. The three output contracts — EXACT format

Deliver a folder named for the batch (see §5). Counts in the manifest must reconcile **exactly**
against the files.

### 3A. Corridor requirement facts — NDJSON + manifest + captured sources

One JSON object per line in `<batch>.ndjson`. **Every field below is required unless marked
optional.** This is the real shipped schema:

```json
{
  "target_table": "requirement_facts",
  "destination_country": "DE",
  "corridor": "FR-DE",
  "topic_key": "FR-DE:eea:residence_registration",
  "domain_area": "registration",
  "entity": {
    "destination_country": "DE",
    "topic_key": "FR-DE:eea:residence_registration",
    "domain_area": "registration",
    "title": "Germany — residence registration (Anmeldung) for an EU professional"
  },
  "fact_key": "anmeldung_deadline_14_days",
  "fact_type": "deadline",
  "name_en": "Anmeldung must be done within 14 days of moving in",
  "fact_text": "An EU national moving to Germany must register their address (Anmeldung) at the local Bürgeramt within 14 days of moving into accommodation. The Anmeldebestätigung it produces is a prerequisite for a bank account, a tax ID, and a phone contract — the classic chicken-and-egg.",
  "source_url": "https://service.berlin.de/dienstleistung/120686/",
  "source_name": "Service Berlin — Anmeldung einer Wohnung",
  "evidence_quote": "You must register within 14 days of moving into your apartment.",
  "confidence_score": 0.9,
  "confidence": "high",
  "required_fields": [],
  "last_verified_date": "2026-09-01",
  "applies_to": {
    "corridor": "FR->DE",
    "nationality": "EEA",
    "status": "professional",
    "persona": "EU professional relocating Paris->Berlin",
    "fact_uid": "FR_DE:EEA:anmeldung_deadline_14_days",
    "pillar": "REGISTRATION",
    "topic": "residence_registration",
    "non_obvious": true,
    "needs_lawyer_review": false,
    "review_status": "pending",
    "verification_status": "representative",
    "quote_verbatim_confirmed": true,
    "source_name": "Service Berlin — Anmeldung einer Wohnung",
    "batch_id": "fr-de-eea-requirements-2026-09-01",
    "nationality_scope_basis": "audience_scope"
  }
}
```

Field notes:
- `domain_area` ∈ `immigration | registration | tax | social_security | healthcare | housing | other`.
- `fact_type` is a short controlled value: `eligibility | deadline | document | fee | account | where_to_apply | other`.
- `evidence_quote` **must be a verbatim substring of the cited page's text** (see §4). This is
  re-checked by the importer against the captured source; a paraphrase fails.
- `applies_to.nationality`: `EEA` / `non-EEA` — or **omit** it entirely if the rule binds
  everyone (NULL nationality = "applies to all"; never write `"any"`).
- `applies_to.nationality_scope_basis`: `nationality_determined` (the obligation exists *because*
  of nationality) or `audience_scope` (nationality-neutral rule; you're just noting the batch's
  audience — do NOT let a serving layer infer an exemption).
- `non_obvious: true` for the divergence/gotcha facts — these are the moat.
- `review_status` / `verification_status` stay `pending` / `representative`. **Never** `approved`,
  `verified`, `lawyer_verified`, or `live`.
- `fact_uid` / `topic_key` are your idempotency keys — stable, unique, derived from the natural
  key. Re-running must not create duplicates.

**Captured sources are mandatory.** For every distinct `source_url`, also deliver:
`sources/<hash>.txt` = the plain extracted text of that page, and `sources/index.json` mapping
each URL → `{file, sha256_of_text, text_chars, is_pdf}`. The importer **refuses to promote** a
fact whose quote is not found in the captured text, so a batch without real captured text cannot
be verified. (If a page is JS-rendered and yields no static text, omit those facts and say so in
the honesty notes — do not fake the capture.)

### 3B. City / destination enrichment — NDJSON (8 keys)

One JSON object per line, exactly these keys:

```json
{"city":"Berlin","country":"DE","topic":"banking","title":"Opening a bank account before Anmeldung","body":"Traditional German banks require an Anmeldebestätigung to open an account, but N26/Vivid (fintechs) open on passport alone and give you an IBAN in a day — the standard bridge while you wait for registration.","source_url":"https://n26.com/en-de/bank-account","source_name":"N26 — Open a bank account","retrieved_at":"2026-09-01"}
```

`topic` ∈ neighborhoods, transport, schools, banking, healthcare, practicalities, cost_of_living.
Leave anything you don't have as **absent** — do not invent coordinates, price ranges, districts,
or "family friendly" flags (the importer keeps them NULL; filling them is fabrication).

### 3C. Services / suppliers — CSV + manifest + rejects

`providers.csv` with **exactly this header (9 columns, in this order):**

```
corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry
```

- `service_category` ∈ `movers | legal_admin | banking | housing | tax | insurance` (use the
  closest existing one).
- Every company must come from an **official registry / accreditation body** (FIDI FAIM, IAM,
  EuRA for movers; the national bar / law society for legal; the national financial regulator for
  banking; etc.) — `source_url` points at the registry page that proves membership, and
  `accreditation_*` records the membership id + expiry. A provider you cannot tie to a registry
  page goes in `rejects.csv` with the reason, **not** in `providers.csv`.
- `rejects.csv` = same shape + a `reject_reason` column. The reject list is the re-sourcing
  worklist, not noise — keep it.
- Manifest lists per category: `{service_category, register, denominator, accepted, rejected,
  confidence, notes}` (denominator = how many candidates you evaluated).

---

## 4. Provenance & the hard rules (non-negotiable)

1. **Real source per fact.** Every fact/record carries a `source_url` + `source_name` +
   `retrieved_at`/`last_verified_date` you actually fetched. No invented sources, numbers, phones.
2. **Verbatim evidence.** `evidence_quote` is copied from the page, not reconstructed from memory.
   If normalization (whitespace) was needed, keep it minimal and flag it.
3. **Official / statutory sources only** for requirements: government bodies, statutory agencies,
   official portals (e.g. `service-public.fr`, `service.berlin.de`, `bzst.de`, `skat.dk`,
   `nyidanmark.dk`, `mom.gov.sg`, `ind.nl`, `belastingdienst.nl`). Blogs, law-firm marketing, and
   relocation-vendor pages are **not** acceptable sources for a requirement (they may be a *lead*
   to find the official page).
4. **Omit, don't guess.** An unverifiable item is dropped and listed in the honesty notes. A field
   with no source data stays absent/NULL. A record you're unsure applies stays out.
5. **Candidate only.** Nothing is `approved` / `verified` / `lawyer_verified` / `live`. The
   pipeline is: *LLM generates candidates → real user + regulated lawyer verify → deterministic
   engine serves.* Generation and serving never touch; your output ends at "candidate, reviewable".
6. **Honesty notes.** End every batch with a short list of *what you deliberately did not include
   and why* (JS-rendered page, 403, source conflict, ambiguous applicability). This is the part
   that decays fastest into false certainty if lost — it is required, not optional.
7. **Counts reconcile.** The manifest's declared counts must equal the file line counts exactly.

---

## 5. Packaging & naming

Deliver one folder / zip named `<slug>-<date>`, e.g. `fr-de-eea-requirements-2026-09-01` or
`berlin-city-enrichment-2026-09-01` or `fr-de-berlin-providers-2026-09-01`, containing:

- **Corridor:** `<batch>.ndjson`, `manifest.json`, `sources/index.json`, `sources/*.txt`.
- **City:** `<batch>.ndjson`, `manifest.json` (+ `sources/` if you captured pages).
- **Services:** `providers.csv`, `rejects.csv`, `manifest.json`.

`manifest.json` (common shape): `batch_id`, `generated`, `corridor`/`city`, `target_table`,
`counts` (records total + per-topic/category), `sources[]` (url, source_name, records_citing),
and a `policy`/`honesty_notes` block. Use the same `batch_id` everywhere — it is the join key
across ChatGPT, the repo, Notion, and Otto (see §6).

---

## 6. Splitting the work + keeping BOTH systems in sync (don't lose status)

**The split.**
- **ChatGPT (research lane):** picks a target (§2), produces the candidate artifacts (§3) with
  captured sources, and emits a **status block** (below). Needs no repo/DB access.
- **Claude Code / operator (import lane):** drops the artifacts into `docs/imports/<batch_id>/`,
  runs the importer **dry-run first** (`scripts/import_otto_facts.py <batch_id>` for corridor
  facts; `scripts/import_resources.py --bundle …` for cities; `scripts/import_supplier_candidates.py
  <csv>` for providers), verifies quotes + counts + source tiers, then stages as candidates. A
  human/lawyer reviews before anything promotes. **Never `--promote` / `--apply` without the gate.**

**The single source of truth for status = the Notion AI Work Queue** (board "AI Work Queue").
One card per batch, keyed by `batch_id`. Lifecycle:
`Otto ready` (research not started) → `AI in Progress` (ChatGPT researching) → `Human Review`
(artifacts delivered, awaiting Claude Code ingest) → `Done` (staged + reviewer signed).

**So status is never lost, ChatGPT must end EVERY batch with this block** (paste it into the
batch's Notion card, and into the repo batch doc):

```
=== RELOPASS BATCH STATUS ===
batch_id:        fr-de-eea-requirements-2026-09-01
type:            corridor | city | services
target:          FR->DE  (EU professional, Paris->Berlin)
status:          DELIVERED (candidates only — NOT imported, NOT served)
counts:          22 facts / 9 sources   (manifest reconciles: yes)
non_obvious:     14 of 22
omitted/why:     3 (2 JS-rendered A1 pages; 1 source 403) — listed in honesty_notes
blocking:        none  |  <what a human/Claude must decide>
next owner:      Claude Code (ingest via scripts/import_otto_facts.py, dry-run first)
=============================
```

**Loop, per batch:**
1. Romain (or Claude) creates the Notion card in `Otto ready` with the `batch_id` and the target.
2. ChatGPT researches → delivers the folder + the status block. Romain flips the card to
   `Human Review` and drops the folder into the repo (`docs/imports/<batch_id>/`).
3. Claude Code / an egress session ingests (dry-run → stage), writes the durable batch doc under
   `docs/imports/<batch_id>/README.md` with a gate script, updates the card, and lists any
   rejects (the re-sourcing worklist) back for ChatGPT.
4. Card → `Done` only when rows are staged as candidates **and** a reviewer has signed. A staged
   draft is not "Done"; a doc-only note is not "Done".

Because every artifact, the repo folder, the Notion card, and Otto's task all carry the same
`batch_id`, either side can reconstruct status at any point from that key alone.

---

## 7. Ready-to-paste ChatGPT prompt

Copy the block below into ChatGPT, fill the two brackets, and attach/keep this document for the
schemas. (A concrete, copy-ready version is also in the chat reply that produced this file.)

> You are a compliance-research assistant for ReloPass. Produce a **candidate** research batch
> for **[CHOOSE ONE: corridor FR→DE for an EU professional / city enrichment for Berlin /
> Berlin providers for movers+legal+banking]**, following the ReloPass research handoff exactly.
> Output the required files (§3) with a manifest whose counts reconcile, and for every requirement
> fact include a **verbatim** `evidence_quote` copied from an **official/statutory** source you
> actually read, plus the captured source text. **Omit** anything you cannot verify and list it in
> honesty notes. Mark everything **candidate / pending** — never approved or verified. Do not
> invent sources, numbers, or fields. End with the RELOPASS BATCH STATUS block.

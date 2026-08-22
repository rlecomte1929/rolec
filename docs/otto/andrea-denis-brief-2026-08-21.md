# Otto collaboration brief — Andrea (ES→IE) & Denis (NO→FR)

**Authored by Claude Code, 2026-08-21.** For Otto to execute and for Claude Code to ingest
without a second conversation. Every §4 work package maps to an **AI Work Queue** row (§7).

---

## 0. How we work together (the contract)

**Otto** researches in the Audos workspace: free compute, cannot read this repo, produces
**files** (NDJSON + manifest) committed to branch `fix/td-qa-services-batch-0719` under
`audos-workspace-776786/data/` and `docs/imports/<batch-id>/`. **Claude Code** owns every line of
code, every migration, every DB write, and every review/approval. Otto never touches code, the
database, or a review status.

The hand-off is a **file contract**, not chat. A batch Claude Code can act on is: a scoped NDJSON
+ a `manifest.json` + a one-page batch doc, all conforming to §3. Anything missing a §3 field is
refused by the loader before it reaches a human — by design.

## 1. The two movers

| | **Andrea** | **Denis** |
|---|---|---|
| Corridor | ES → IE (Madrid → Dublin) | NO → FR (Norway → Paris) |
| Nationality | **Venezuelan** — third-country | **French** — EEA / own-national into France |
| `applies_to.nationality` | **`non-EEA`** | **`EEA`** |
| Pathway | `CSEP_2026` (Critical Skills permit) | `RETURNING_EEA_CITIZEN_2026` |
| Destination catalog | `IRELAND` (29 approved rows) | `FRANCE` (16 approved rows) |
| Origin-side today | `corridors/ES_IE/facts.yaml` `origin_facts: []` — **nothing** | `corridors/NO_FR/facts.yaml` `origin_facts: 4` — **partial** |

They are the paired demo: Andrea proves the **third-country permit** path, Denis the **EEA
free-mover** path. Getting the nationality scoping right on both is the whole point.

## 2. What Otto already delivered — and the exact reason none of it can load yet

On the branch: `es-ie-general-2026-08-21.jsonl` (33 facts) and `no-fr-general-2026-08-21.jsonl`
(20 facts). The vocabulary is **correct** (`destination_country`, `entity_topic_key`,
`fact_key`, `fact_text`, `source_url`, `fact_type`, `evidence_quote`, `confidence`, `applies_to`),
so **no converter is needed**. But:

1. **All 53 records have `applies_to.nationality = null`.** After the 2026-08-21 loader hardening
   (`backend/imports/otto/mappings.py`, PR #1954), a fact with no nationality is **refused
   loudly** (`Unmapped`), and a null would otherwise mean "applies to everyone" — serving a
   third-country visa requirement to a Spanish free mover. **Every one of the 53 would be
   rejected at promote time.**
2. **No `applies_to.status`** → also refused (promotes as `purpose='other'`, which no reader can
   return; PR #1954).
3. No `manifest.json` (no counts, no sha256, no scope), no `non_obvious` flags, no
   `needs_lawyer_review`, and `fact_type:"step"` records mixed into the fact stream (steps are the
   roadmap graph, not requirement facts — see §3.4).

**The single most important change: every fact must be nationality-scoped and status-scoped,
correctly, to the audience the obligation governs.** The rest of this brief is the standard that
fixes all of the above.

## 3. The delivery contract (read once; every §4 task depends on it)

### 3.1 The fact record (one JSON object per NDJSON line)

```jsonc
{
  "destination_country": "IE",              // REQUIRED. ISO-2 of the destination.
  "entity_topic_key": "registration",       // REQUIRED. Stable snake_case topic; groups facts into one requirement.
  "fact_key": "es_ie_irp_register_90_days",  // REQUIRED. Globally unique; prefix with corridor. Keep STABLE across re-deliveries (idempotent).
  "fact_text": "…",                          // REQUIRED. The claim, in the mover's terms. Must be supported by evidence_quote.
  "source_url": "https://www.irishimmigration.ie/…",  // REQUIRED. The exact page that states the claim. OFFICIAL publisher (§3.6).
  "evidence_quote": "…verbatim sentence(s) from the page…",  // REQUIRED IN PRACTICE — no quote ⇒ graded needs_review, cannot be trusted.
  "fact_type": "eligibility|document|deadline|fee|where_to_apply|other",  // NOT "step" — see §3.4. Unknown ⇒ normalised to 'other'.
  "confidence": "high|medium|low",           // maps to 0.9 / 0.6 / 0.3
  "applies_to": {
    "nationality": "non-EEA",                // ⛔ MAKE-OR-BREAK, REQUIRED. One of: EEA | EU | non-EEA | non-EU. NEVER null. See §3.4.
    "status": "professional",                // ⛔ REQUIRED. One of: professional | student | family | any. See §3.5.
    "pillar": "RESIDENCE|EMPLOYMENT|HEALTHCARE|HOUSING|SOCIAL_SECURITY|IDENTITY",  // the loader now reads this (AIQ-2036).
    "non_obvious": true,                      // true when a non-expert would not know to look for this — the moat.
    "non_obvious_note": "Commonly believed … Actually … Action required …",  // the plain-language trap, when non_obvious.
    "needs_lawyer_review": false,             // true for any legal/tax DETERMINATION rather than a published procedural rule.
    "quote_verbatim_confirmed": false,        // Otto sets false; a human confirms the quote before approval.
    "corridor": "ES->IE"
  }
}
```

### 3.2 The `manifest.json` (one per batch — this is what makes a batch auditable)

Exact keys (the VE→IE batch `docs/imports/ve-ie-entry-family-2026-08-20/manifest.json` is the
reference):

```jsonc
{
  "batch_id": "es-ie-thirdcountry-requirements-2026-08-22",
  "generated_at": "2026-08-22", "generated_by": "otto (Audos)",
  "corridor": "ES-IE", "origin_country_code": "ES", "destination_country_code": "IE",
  "nationality_class": "THIRD_COUNTRY",       // requirement_items vocabulary: THIRD_COUNTRY | EU_EEA | OWN_NATIONAL
  "target_table": "public.requirement_items", "target_country_code": "IRELAND",
  "record_count": 24, "non_obvious_count": 9, "needs_lawyer_review_count": 3,
  "artifact": "es-ie-thirdcountry-requirements-2026-08-22.ndjson",
  "sha256": "<sha256 of the ndjson bytes>",   // Claude Code re-hashes and reconciles; a mismatch fails the gate.
  "review_status_all": "pending", "verification_status_all": "representative",
  "scope": "One paragraph: what this batch covers, what it deliberately excludes, and against what it reconciles.",
  "load_task": "AIQ-nnnn"
}
```

Manifest counts must reconcile **exactly** against the NDJSON. A discrepancy is the batch's
problem to explain, never Claude Code's to reconcile away.

### 3.3 Batch folder layout & naming

```
docs/imports/<batch-id>/
  ├── <batch-id>.ndjson        ← the facts (source of truth; never retyped)
  ├── manifest.json            ← §3.2
  └── README.md                ← ≤1 page: facts as a table (topic → what it establishes), source list, load contract, the §S1 scoping-audit column
```
`batch-id` = `<corridor>-<theme>-<YYYY-MM-DD>`, e.g. `no-fr-norway-departure-2026-08-22`.

### 3.4 Nationality scoping — the make-or-break rule

The rule that broke the empadronamiento rows (PR #1956) and rejects all 53 delivered facts today.

1. **Every fact carries `applies_to.nationality`, always** — `EEA`/`EU` (free movers) or
   `non-EEA`/`non-EU` (third country). **Never null.** Null is refused by the loader.
2. **Scope to the audience the obligation actually governs — read it from the fact, never infer it
   from the corridor.** An Irish IRP fact and a Spanish TIE fact are `non-EEA`; an EU-registration
   fact is `EEA`. Andrea's batch is overwhelmingly `non-EEA`; Denis's overwhelmingly `EEA`.
3. **A truly universal obligation** (e.g. municipal address registration, which every resident does
   regardless of passport) is delivered as **two records**, one `EEA` and one `non-EEA`, each with
   its own `fact_key`. There is no "applies to all" value, and a null is refused.
4. **`fact_type:"step"` is not a requirement fact.** Sequenced actions (apply for the permit, then
   the visa, then register) are the *roadmap step graph*, authored in
   `corridors/<id>/pathways/*.yaml` by Claude Code. Do not put them in the fact stream. A genuinely
   new step goes in the batch README under "step candidates" and Claude Code places it.

### 3.5 Status (purpose) scoping

`applies_to.status` is required, one of `professional` (→ `employment`), `student`, `family`,
`any` (→ `other`). Both movers are employment relocations, so **`professional`** unless a specific
fact is genuinely family-scoped (a dependant-visa fact → `family`). Absent/unrecognised ⇒ refused.

### 3.6 Honesty rules (mirror the platform's own guardrails)

- **Official publishers only.** The publisher's DOMAIN decides trust; `source_name` gets no vote.
  OFFICIAL (a government/statutory body) may auto-accept; SEMI_OFFICIAL (public agency without a
  gov TLD, or a portal restating rules) is forced to review; UNOFFICIAL (blog, law firm, vendor) is
  REJECTED and the fact is lost. Known-good hosts:
  - **Ireland**: `irishimmigration.ie`, `gov.ie` (official); `citizensinformation.ie`, `revenue.ie`
    (semi-official → review).
  - **Spain**: `gob.es` suffix, plus `boe.es`, `seg-social.es`, `agenciatributaria.es`,
    `policia.es`, `sepe.es`, `madrid.es`, `barcelona.cat` (allowlisted 2026-08-20, PR #1912).
  - **Norway**: `udi.no`, `skatteetaten.no`, `politiet.no`, `nav.no`, `altinn.no`, `lovdata.no`,
    `helsenorge.no`, `folkeregisteret.no`.
  - **France**: `service-public.fr`, `legifrance.gouv.fr`, `urssaf.fr`, `ameli.fr`,
    `impots.gouv.fr`, `france-visas.gouv.fr`, `ofii.fr`.
- **No fabrication.** A field the research does not support stays absent. Never invent a number, fee,
  deadline, or citation. A believed-but-unpublished claim ("market practice") says so in `fact_text`
  and sets `needs_lawyer_review` — do not attach a source that does not state it.
- **Evidence quote is the proof.** `evidence_quote` is a verbatim sentence from `source_url` that
  supports `fact_text`. Set `quote_verbatim_confirmed: false`; a human confirms.
- **`needs_lawyer_review: true`** for any legal/tax *determination* (treaty tie-breakers,
  residence-status conclusions), not a published procedural rule.
- **Candidate-only.** `review_status_all: "pending"`, `verification_status_all: "representative"`.
  Never `approved`/`verified`/`lawyer_verified`/`live`.

## 4. The work packages — each is one Otto deliverable and one Notion task

Format: **Goal / Spec / Deliverable / Acceptance / Reuse (how Claude Code consumes it)**.

### ANDREA — ES → IE (third-country / `non-EEA`)

**A1 · Redo the ES→IE destination requirement facts, correctly scoped.** *(→ AIQ-1833, ES-IE half)*
- *Goal:* replace the unusable `es-ie-general` drop with a loadable batch.
- *Spec:* every fact `applies_to.nationality:"non-EEA"`, `status:"professional"`; drop the 9
  `fact_type:"step"` records (the CSEP step graph is already authored); flag non-obvious traps.
  Topics: immigration_work_authorization, ISD/IRP registration, PPSN, Revenue/RPN + the
  40%-week-5 emergency-tax rule, health entitlements, taxation.
- *Deliverable:* `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/`.
- *Acceptance:* `check_otto_batches` passes; **100 % of records promote** (0 `Unmapped`); reconciles.
- *Reuse:* raises IRELAND non-obvious recall for the `ES_IE:non_eu_passport_holder` eval slice.

**A2 · Spain-departure obligations (Andrea's origin side — modelled nowhere today).** *(NEW)*
- *Goal:* the exit side of her move.
- *Spec:* baja del padrón (municipal de-registration), Seguridad Social baja / posted-worker A1 if
  she stays on an ES contract, AEAT tax-exit / non-resident transition. Sourced to AEAT /
  Seg-Social / the ayuntamiento; `nationality:"non-EEA"`, `status:"professional"`.
- *Deliverable:* `docs/imports/es-departure-2026-08-22/`. *Acceptance:* gate passes; ≥6 official-sourced facts.
- *Reuse:* closes the `origin_facts: []` gap; feeds the origin-side serving work (Claude Code).

**A3 · ISD visa-required reference list (reference data, not requirement facts).** *(NEW)*
- *Goal:* let the platform **assert** "you are a visa-required national" instead of hedging.
- *Spec:* a JSON map `{ iso2 → visa_required: bool }` for Ireland's visa-required list, sourced to
  irishimmigration.ie, with `retrieved_at`. Venezuela = true.
- *Deliverable:* `docs/imports/ie-isd-visa-required-2026-08-22/isd_visa_required.json` + manifest + source.
- *Acceptance:* every entry cites the ISD page; VE present and true.
- *Reuse:* Claude Code wires it as the `isd_visa_required.{iso}` lookup the CSEP pathway references,
  flipping Andrea's D-visa advisory from conditional to **asserted**.

**A4 · Dublin vendor directory.** *(→ AIQ-1871)*
- *Spec:* 4–6 each of movers serving Dublin, letting/relocation agencies, a CSEP immigration
  solicitor, an Irish bank onboarding new arrivals. Fields: name, official URL, service area,
  categories, contact. Provenance: the provider's own site.
- *Deliverable:* `docs/imports/dublin-vendors-2026-08-22/vendors.ndjson` + manifest.
- *Reuse:* Claude Code loads into the supplier registry + adds `ES-IE` to `KNOWN_CORRIDORS`.

**A5 · ES→IE RAG corpus (Tier-1 source documents).** *(→ extends AIQ-1852)*
- *Spec:* clean full text of the 8–12 Tier-1 pages the requirement facts cite, one doc per source,
  with url + retrieved_at + publisher.
- *Deliverable:* `docs/imports/es-ie-corpus-2026-08-22/*.txt` + manifest.
- *Reuse:* Claude Code indexes into `immigration_corpus_chunks` for `ES_IE`.

**A6 · Document-extraction reference (Andrea's papers).** *(NEW)*
- *Spec:* the layout/field patterns of (a) an Irish/English employment contract and (b) a Spanish
  TIE card — labelled sample structure, field names, where each datum sits. **No real PII.**
- *Deliverable:* `docs/imports/es-ie-doc-reference-2026-08-22/` (structured notes).
- *Reuse:* Claude Code adds an IE/EN locale to `employment_contract.py` and routes the TIE.

### DENIS — NO → FR (EEA free mover / `EEA`)

**D1 · Redo the NO→FR (France) destination requirement facts, correctly scoped.** *(→ AIQ-1833, NO-FR half; AIQ-2017)*
- *Spec:* every fact `applies_to.nationality:"EEA"`, `status:"professional"`; drop `step` records;
  flag non-obvious. Topics: France residence registration (an EU national needs *none* — that fact
  itself matters), numéro fiscal / tax registration, CPAM / carte vitale, social-security single-state rule.
- *Deliverable:* `docs/imports/no-fr-eea-requirements-2026-08-22/`. *Acceptance:* gate passes; 100 % promote.
- *Reuse:* FRANCE non-obvious recall for the `NO_FR` eval slice.

**D2 · Norway-departure obligations (complete the partial set).** *(NEW; references AIQ-1899)*
- *Spec:* extend the 4 existing `NO_FR` origin facts — folkeregister move-abroad notification, exit
  from folketrygden, skattekort/exit-tax, the A1 issued by URSSAF (France) not Norway, and the
  "preserve BankID before de-registration disables it" trap. Sourced to skatteetaten.no / nav.no /
  urssaf.fr; `nationality:"EEA"`, `status:"professional"`. Claude Code will supply the 4 existing
  `fact_key`s so there is no duplication.
- *Deliverable:* `docs/imports/no-departure-2026-08-22/`. *Acceptance:* gate passes; no dup of the 4.

**D3 · Paris/France vendor directory.** *(NEW)*
- *Spec:* movers into Paris, letting agencies, a French bank onboarding new residents, CPAM help.
  Same fields as A4. *Deliverable:* `docs/imports/paris-vendors-2026-08-22/`.
- *Reuse:* supplier registry + `NO-FR` in `KNOWN_CORRIDORS`.

**D4 · NO→FR RAG corpus.** *(NEW)* As A5, for the FR-side sources. *Deliverable:*
`docs/imports/no-fr-corpus-2026-08-22/`. *Reuse:* index into `immigration_corpus_chunks` for `NO_FR`.

### SHARED

**S1 · Nationality-scoping self-audit (do this on A1 and D1 before delivering).** *(→ AIQ-2044)*
- *Spec:* for every fact, state in the batch README a one-line justification of its
  `applies_to.nationality` against the fact's own text ("IRP applies to non-EEA only → non-EEA").
- *Acceptance:* the README audit column is complete; the gate's `_unscoped_topics` check is empty.

## 5. Metrics & evals — the return on the work

Per batch (in the README, re-checked by Claude Code):

| Metric | Target | How measured |
|---|---|---|
| Promote rate | **100 %** | `import_otto_facts.py` dry-run: 0 `Unmapped` |
| Correctly nationality-scoped | **100 %** | §S1 audit + the `overserved_requirements` eval (PR #1955) stays 0 for the slice |
| Manifest reconciliation | exact | sha256 + counts match |
| Citation-resolves rate | ≥ 95 % | `curl` every `source_url`; a dead link fails |
| Zero fabrication | 100 % | every `fact_text` has a supporting `evidence_quote` |
| Non-obvious recall | ≥ prior | the `nonobvious_recall` eval (PR #1950) for the corridor×employee-type slice |

Programme-level (the demo is "done" when):
- **corridors-serving-nothing = 0** for IRELAND (Andrea) and FRANCE (Denis), with the *right*
  nationality audiences served;
- both personas' journeys complete end-to-end (roadmap traps, asserted advisories, origin +
  destination, vendors, audit trail);
- `nonobvious_recall` **and** `overserved_requirements` are green for both slices — the precision
  axis proves Denis (EEA) is never shown Andrea's (third-country) permit content and vice-versa.

## 6. Validation pipeline — what happens after Otto delivers (Claude Code's side)

1. **Gate** — `scripts/check_otto_batches.py` (the generic gate): sha256, count reconciliation,
   real `parsers.read_jsonl` with zero rejections, `_unscoped_topics` empty (nationality + status
   present), no served status, candidate-only. **A batch that fails the gate is not loaded** — it
   returns to Otto with the failure.
2. **Load as candidates** — `import_otto_facts.py <batch> --apply` → `otto_staging`, `status='new'`.
3. **Promote to `pending`** — into `requirement_items`, never past `pending`.
4. **Review & approve** — through the review discipline; counsel-flagged rows wait for the assurance model.
5. **Implement the reuse** — corpus indexing, vendor registry, extractor locales, the ISD lookup —
   the code half, Claude Code's.

## 7. Notion mapping (AI Work Queue)

Existing tasks to reference/enrich, and the genuinely-new ones to create. Every task:
`Assigned = Claude Cowork` (Otto) · `Task Type = Research` · `Autonomy Tier = 🔴 Red — full human
gate` (research feeding served content is never auto-approved) · `Test Command =
./.venv311/bin/python scripts/check_otto_batches.py <batch-id>`.

| Package | AI Work Queue | Action |
|---|---|---|
| A1 / D1 | **AIQ-1833** "Otto re-deliver ES-IE + NO-FR in JSONL schema" | **ENRICH** — add the mandatory `applies_to.nationality` + `status` contract (§3.4/3.5) it predates |
| A4 | **AIQ-1871** "ES_IE marketplace is empty" | reference |
| A5 | **AIQ-1852** "ES_IE corpus: real lead times, re-index" | reference / extend |
| D1 | **AIQ-2017** "NO→FR Corridor Authoring" | reference |
| A1/A2 posted-worker | **AIQ-1899** "EU posted-worker Compliance Pack" | reference |
| Andrea family/entry | **AIQ-1993** (VE→IE entry/family) | reference (VE→IE loaded as AIQ-2027) |
| S1 scoping | **AIQ-2044** "settle-in resources can't vary by nationality" | reference |
| ingest pillar | **AIQ-2036** "mappings ignores applies_to.pillar" | reference (Claude Code) |
| A2 | Spain-departure obligations | **CREATE** |
| A3 | ISD visa-required list | **CREATE** |
| A6 | ES→IE document-extraction reference | **CREATE** |
| D2 | Norway-departure completion | **CREATE** |
| D3 | Paris/France vendors | **CREATE** |
| D4 | NO→FR RAG corpus | **CREATE** |

## 8. Guardrails — what Otto must never do

- Never write code, a migration, or the database. Deliver files.
- Never null or guess `applies_to.nationality` — it decides who sees a visa requirement. Read it
  from the fact.
- Never emit `fact_type:"step"` into the fact stream — steps are the roadmap graph Claude Code owns.
- Never invent a source, number, fee, deadline, or confidence. Absent stays absent.
- Never set a served status. Everything is `pending` / `representative`.
- Never merge to `main` or promote past candidate.

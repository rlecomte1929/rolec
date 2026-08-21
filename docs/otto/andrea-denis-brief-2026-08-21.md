# OTTO COLLABORATION BRIEF — Andrea (ES→IE) & Denis (NO→FR)

> **This is the deliverable the user asked for.** On approval it becomes a committed repo MD
> (`docs/otto/andrea-denis-brief-2026-08-21.md`), and each §4 work package becomes an
> **AI Work Queue** row (Status = *Otto ready*, Assigned = *Claude Cowork*). It is written for
> Otto to execute and for me (Claude Code) to ingest without a second conversation.

## 0. How we work together (the contract)

**Otto** researches in the Audos workspace: free compute, cannot read this repo, produces
**files** (NDJSON + manifest) and commits them to branch `fix/td-qa-services-batch-0719` under
`audos-workspace-776786/data/` and `docs/imports/<batch-id>/`. **I (Claude Code)** own every
line of code, every migration, every DB write, and every review/approval. Otto never touches
code, the database, or a review status.

The hand-off is a **file contract**, not chat. A batch I can act on is: a scoped NDJSON + a
`manifest.json` + a one-page batch doc, all conforming to §3. Anything missing a field in §3 is
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
| They are the paired demo: Andrea proves the **third-country permit** path, Denis the **EEA free-mover** path. Getting the nationality scoping right on both is the whole point. | | |

## 2. What Otto already delivered — and the exact reason none of it can load yet

On the branch: `es-ie-general-2026-08-21.jsonl` (33 facts) and `no-fr-general-2026-08-21.jsonl`
(20 facts). The vocabulary is **correct** (`destination_country`, `entity_topic_key`,
`fact_key`, `fact_text`, `source_url`, `fact_type`, `evidence_quote`, `confidence`, `applies_to`)
— so no converter is needed. But **all 53 records have `applies_to.nationality = null`**, and
after this session's hardening the loader (`backend/imports/otto/mappings.py`) **refuses loudly**
on:

- **absent nationality** → `Unmapped` ("the audience is unscoped, and NULL here would serve a
  visa track to free movers"), and
- **absent status** → `Unmapped` ("promotes as `purpose='other'`, which no reader can return").

So **every one of the 53 facts would be rejected at promote time.** They also carry no
`manifest.json` (no counts, no sha256, no scope), no `non_obvious` flags, no
`needs_lawyer_review`, and mix `fact_type: "step"` records (which are roadmap steps, not
requirement facts) into the fact stream. The rest of this brief is the standard that fixes all
of that. **The single most important change: every fact must be nationality-scoped and
status-scoped, correctly, to the audience the obligation governs.**

## 3. The delivery contract (read once; every §4 task depends on it)

### 3.1 The fact record (one JSON object per NDJSON line)

```jsonc
{
  "destination_country": "IE",              // REQUIRED. ISO-2 of the destination.
  "entity_topic_key": "registration",       // REQUIRED. Stable snake_case topic; groups facts into one requirement.
  "fact_key": "es_ie_irp_register_90_days",  // REQUIRED. Globally unique; prefix with corridor to avoid collisions.
  "fact_text": "…",                          // REQUIRED. The claim, in the mover's terms. Must be supported by evidence_quote.
  "source_url": "https://www.irishimmigration.ie/…",  // REQUIRED. The exact page that states the claim. Must be an OFFICIAL publisher (see 3.6).
  "evidence_quote": "…verbatim sentence(s) from the page…",  // REQUIRED IN PRACTICE — a fact with no quote is graded needs_review and cannot be trusted.
  "fact_type": "eligibility|document|deadline|fee|step|other",  // 'step' facts do NOT belong here — see 3.4.
  "confidence": "high|medium|low",
  "applies_to": {
    "nationality": "non-EEA",                // ⛔ MAKE-OR-BREAK, REQUIRED. One of: EEA | EU | non-EEA | non-EU. NEVER null. See 3.4.
    "status": "professional",                // ⛔ REQUIRED. One of: professional | student | family | any. See 3.5.
    "non_obvious": true,                      // true when a non-expert would not know to look for this — the moat.
    "non_obvious_note": "Commonly believed … Actually … Action required …",  // the plain-language trap, when non_obvious.
    "needs_lawyer_review": false,             // true for any claim that is a legal/tax determination rather than a published rule.
    "quote_verbatim_confirmed": false,        // Otto sets false; a human confirms the quote before approval.
    "corridor": "ES->IE",
    "pillar": "RESIDENCE|EMPLOYMENT|HEALTHCARE|HOUSING|SOCIAL_SECURITY|IDENTITY"
  }
}
```

### 3.2 The `manifest.json` (one per batch — this is what makes a batch auditable)

Exact keys (the VE→IE worked example is the reference):

```jsonc
{
  "batch_id": "es-ie-thirdcountry-requirements-2026-08-22",
  "generated_at": "2026-08-22", "generated_by": "otto (Audos)",
  "corridor": "ES-IE", "origin_country_code": "ES", "destination_country_code": "IE",
  "nationality_class": "THIRD_COUNTRY",       // the requirement_items vocabulary: THIRD_COUNTRY | EU_EEA | OWN_NATIONAL
  "target_table": "public.requirement_items", "target_country_code": "IRELAND",
  "record_count": 24, "non_obvious_count": 9, "needs_lawyer_review_count": 3,
  "artifact": "es-ie-thirdcountry-requirements-2026-08-22.ndjson",
  "sha256": "<sha256 of the ndjson bytes>",   // I re-hash and reconcile; a mismatch fails the gate.
  "review_status_all": "pending", "verification_status_all": "representative",
  "scope": "One paragraph: what this batch covers, what it deliberately excludes, and against what it must reconcile.",
  "load_task": "AIQ-nnnn"
}
```

Counts in the manifest must reconcile **exactly** against the NDJSON. A discrepancy is the
batch's problem to explain, never mine to reconcile away.

### 3.3 Batch folder layout & naming

```
docs/imports/<batch-id>/
  ├── <batch-id>.ndjson        ← the facts (source of truth; never retyped)
  ├── manifest.json            ← 3.2
  └── README.md                ← ≤1 page: the facts as a table (topic → what it establishes), the source list, the load contract
```
`batch-id` = `<corridor>-<theme>-<YYYY-MM-DD>`, e.g. `no-fr-norway-departure-2026-08-22`.

### 3.4 Nationality scoping — the make-or-break rule

This is the rule that broke the empadronamiento rows last week and would reject all 53 delivered
facts today. Three parts:

1. **Every fact carries `applies_to.nationality`, always, one of `EEA` / `EU` (free movers) or
   `non-EEA` / `non-EU` (third country).** Never null. Null is refused by the loader.
2. **Scope to the audience the obligation actually governs — read it from the fact, never infer
   it from the corridor.** A Spanish TIE fact and an Irish IRP fact are `non-EEA`; an EU-registration
   fact is `EEA`. Andrea's batch is overwhelmingly `non-EEA`; Denis's is overwhelmingly `EEA`.
3. **A truly universal obligation** (e.g. municipal address registration, which every resident
   does regardless of passport) is delivered as **two records**, one `EEA` and one `non-EEA`, each
   with its own `fact_key`. Do not emit a single "applies to all" record — there is no such value,
   and a null is refused.
4. **`fact_type: "step"` is not a requirement fact.** Sequenced actions (apply for the permit,
   then the visa, then register) are the *roadmap step graph*, which I author in
   `corridors/<id>/pathways/*.yaml`. Do not put them in the fact stream. If Otto surfaces a
   genuinely new step, list it in the batch README under "step candidates" and I will place it.

### 3.5 Status (purpose) scoping

`applies_to.status` is required and must be one of `professional` (→ `employment`), `student`,
`family`, `any` (→ `other`). Both Andrea and Denis are employment relocations, so **`professional`**
unless a specific fact is genuinely family-scoped (e.g. a dependant-visa fact → `family`). Absent
or unrecognised → refused.

### 3.6 Honesty rules (non-negotiable — they mirror the platform's own guardrails)

- **Official publishers only.** Source each fact to the government/statutory body that publishes
  it (irishimmigration.ie, revenue.ie, DGT, AEAT, URSSAF, service-public.fr, skatteetaten.no, …).
  A non-official host is rejected by the sourcing gate.
- **No fabrication.** A field the research does not support stays absent. Never invent a number,
  a fee, a deadline, or a citation. If a claim is believed but unpublished ("market practice"),
  say so in `fact_text` and set `needs_lawyer_review` — do **not** attach a source that does not
  state it.
- **Evidence quote is the proof.** `evidence_quote` must be a verbatim sentence from
  `source_url` that supports `fact_text`. Set `quote_verbatim_confirmed: false`; a human confirms.
- **`needs_lawyer_review: true`** for any legal/tax *determination* (treaty tie-breakers,
  residence-status conclusions) rather than a published procedural rule.
- **Candidate-only.** `review_status_all: "pending"`, `verification_status_all: "representative"`.
  Never `approved`, `verified`, `lawyer_verified`, or `live`. I load as candidates; a human approves.

## 4. The work packages — each is one Otto deliverable and one Notion task

Format per task: **Goal / Spec / Deliverable / Acceptance / Validates**. Effort is Otto's
research effort. "Reuse" = how I consume it directly.

### ANDREA — ES → IE (third-country / `non-EEA`)

**A1 · Redo the ES→IE destination requirement facts, correctly scoped.**
*Goal:* replace the unusable `es-ie-general` drop with a loadable batch. *Spec:* every fact
`applies_to.nationality: "non-EEA"`, `status: "professional"`; drop the 9 `fact_type:"step"`
records (they are the CSEP step graph I already own); flag the non-obvious traps
(`non_obvious:true` + note). Topics: immigration_work_authorization, ISD/IRP registration,
PPSN, Revenue/RPN + the 40%-week-5 emergency-tax rule, health entitlements, taxation.
*Deliverable:* `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/` (ndjson + manifest +
README). *Acceptance:* `check_otto_batches` gate passes; **100 % of records promote** (0
`Unmapped`); reconciles to manifest. *Validates:* raises IRELAND non-obvious recall for the
`ES_IE:non_eu_passport_holder` eval slice.

**A2 · Spain-departure obligations (Andrea's origin side — currently modelled nowhere).**
*Goal:* the exit side of her move. *Spec:* baja del padrón (municipal de-registration), Seguridad
Social baja / posted-worker A1 if she stays on an ES contract, AEAT tax-exit / non-resident
transition; each sourced to AEAT / Seg-Social / the ayuntamiento; `nationality: "non-EEA"`,
`status: "professional"`. *Deliverable:* `docs/imports/es-departure-2026-08-22/`. *Acceptance:*
gate passes; ≥ 6 facts, each official-sourced. *Validates:* closes the `origin_facts: []` gap;
feeds the origin-side serving work on my side.

**A3 · ISD visa-required reference list (reference data, not requirement facts).**
*Goal:* let the platform *assert* "you are a visa-required national" instead of hedging. *Spec:*
a JSON map `{ iso2 → visa_required: bool }` for Ireland's short/long-stay visa-required list,
sourced to irishimmigration.ie, with `retrieved_at`. Venezuela = true. *Deliverable:*
`docs/imports/ie-isd-visa-required-2026-08-22/isd_visa_required.json` + manifest + source.
*Acceptance:* every entry cites the ISD page; VE present and true. *Reuse:* I wire it as the
`isd_visa_required.{iso}` lookup the CSEP pathway already references, flipping Andrea's D-visa
advisory from conditional to **asserted**.

**A4 · Dublin vendor directory.** *Goal:* make her RFQ show real providers. *Spec:* 4–6 each of:
international movers serving Dublin, letting/relocation agencies, an immigration solicitor who
does CSEP, an Irish bank that onboards new arrivals. Fields: name, official URL, service area,
categories, contact. Provenance: the provider's own site. *Deliverable:*
`docs/imports/dublin-vendors-2026-08-22/vendors.ndjson` + manifest. *Acceptance:* every row has a
resolving URL and a Dublin/IE service area. *Reuse:* I load into the supplier registry + add
`ES-IE` to `KNOWN_CORRIDORS`.

**A5 · ES→IE RAG corpus (Tier-1 source documents).** *Goal:* ground the Policy Assistant so a
Dublin question isn't refused for lack of context. *Spec:* the full text (or clean extract) of
the 8–12 Tier-1 pages the requirement facts cite, one document per source, with url + retrieved_at
+ publisher. *Deliverable:* `docs/imports/es-ie-corpus-2026-08-22/*.txt` + manifest.
*Reuse:* I index them into `immigration_corpus_chunks` for `ES_IE`.

**A6 · Document-extraction reference (Andrea's papers).** *Goal:* make her Google contract and
Spanish TIE actually extract. *Spec:* the layout/field patterns of (a) an Irish/English employment
contract and (b) a Spanish TIE card — labelled sample structure, field names, where each datum
sits — enough for me to add an IE/EN locale to `employment_contract.py` and route the TIE.
*Deliverable:* `docs/imports/es-ie-doc-reference-2026-08-22/` (structured notes, no real PII).
*Reuse:* I code the extractor locales.

### DENIS — NO → FR (EEA free mover / `EEA`)

**D1 · Redo the NO→FR (France) destination requirement facts, correctly scoped.** *Goal:* replace
the unusable `no-fr-general` drop. *Spec:* every fact `applies_to.nationality: "EEA"`,
`status: "professional"`; drop `step` records; flag non-obvious. Topics: France residence
registration (an EU national needs *none* — that fact itself matters), numéro fiscal / tax
registration, CPAM / carte vitale health, social-security single-state rule. *Deliverable:*
`docs/imports/no-fr-eea-requirements-2026-08-22/`. *Acceptance:* gate passes; 100 % promote;
reconciles. *Validates:* FRANCE non-obvious recall for the `NO_FR` eval slice.

**D2 · Norway-departure obligations (complete the partial set).** *Goal:* Denis's exit side. *Spec:*
extend the 4 existing `NO_FR` origin facts — folkeregister move-abroad notification, exit from
folketrygden, skattekort/exit-tax, the A1 issued by URSSAF (France) not Norway, and the
"preserve BankID before de-registration disables it" trap. Sourced to skatteetaten.no / NAV /
URSSAF; `nationality: "EEA"`, `status: "professional"`. *Deliverable:*
`docs/imports/no-departure-2026-08-22/`. *Acceptance:* gate passes; no duplication of the 4
existing facts (I'll give Otto the existing `fact_key`s). *Validates:* completes Denis's
origin side.

**D3 · Paris/France vendor directory.** *Goal:* Denis's RFQ shows providers. *Spec:* movers into
Paris, letting agencies, a French bank onboarding new residents, CPAM registration help. Same
fields as A4. *Deliverable:* `docs/imports/paris-vendors-2026-08-22/`. *Reuse:* supplier registry
+ `NO-FR` in `KNOWN_CORRIDORS`.

**D4 · NO→FR RAG corpus.** As A5, for the FR-side sources. *Deliverable:*
`docs/imports/no-fr-corpus-2026-08-22/`. *Reuse:* index into `immigration_corpus_chunks` for `NO_FR`.

### SHARED

**S1 · Nationality-scoping self-audit (do this on A1 and D1 before delivering).** *Goal:* never
ship a null or mis-scoped nationality again. *Spec:* for every fact, Otto states in the README a
one-line justification of its `applies_to.nationality` against the fact's own text ("IRP applies
to non-EEA only → non-EEA"). *Acceptance:* the README audit column is complete; the gate's
`_unscoped_topics` check is empty.

## 5. Metrics & evals — the return on the work

Per batch (in the batch README, and re-checked by me):

| Metric | Target | How measured |
|---|---|---|
| Promote rate | **100 %** | `import_otto_facts.py` dry-run: 0 `Unmapped` |
| Correctly nationality-scoped | **100 %** | S1 audit + the `overserved_requirements` eval (this session's precision axis) stays 0 for the slice |
| Manifest reconciliation | exact | sha256 + counts match |
| Citation-resolves rate | ≥ 95 % | I `curl` every `source_url`; a dead link fails |
| Zero fabrication | 100 % | every `fact_text` has a supporting `evidence_quote` |
| Non-obvious recall | ≥ prior | the `nonobvious_recall` eval for the corridor×employee-type slice |

Programme-level (the demo is "done" when):
- **corridors-serving-nothing = 0** for IRELAND (Andrea) and FRANCE (Denis) with the *right*
  nationality audiences served;
- both personas' journeys complete end-to-end (roadmap traps, asserted advisories, origin +
  destination, vendors, audit trail);
- the `nonobvious_recall` **and** `overserved_requirements` evals are green for both slices — the
  precision axis is what proves Denis (EEA) is never shown Andrea's (third-country) permit content
  and vice-versa.

## 6. Validation pipeline — what happens after Otto delivers (my side)

1. **Gate** — `scripts/check_otto_batches.py` (the generic gate from the pipeline plan below):
   sha256, count reconciliation, real `parsers.read_jsonl` with zero rejections, `_unscoped_topics`
   empty (nationality + status present), no served status, candidate-only. **A batch that fails
   the gate does not get loaded** — it goes back to Otto with the failure.
2. **Load as candidates** — `import_otto_facts.py <batch> --apply` → `otto_staging`, `status='new'`.
3. **Promote to `pending`** — into `requirement_items`, never past `pending`.
4. **Review & approve** — through the review discipline; the counsel-flagged rows wait for the
   assurance model.
5. **Implement the reuse** — corpus indexing, vendor registry, extractor locales, the ISD lookup
   wiring — the code half, which is mine.

## 7. Notion staging — the row per §4 task

Each work package → one **AI Work Queue** row:
`Status = "Otto ready"` · `Assigned AI Agent = "Claude Cowork"` · `Task Type = "Research"` ·
`Product Area = "Corridor Knowledge"` (A2/D2/A3 = "Data Quality"; A4/D3 = "Integrations") ·
`Strategic Objective` = the *Goal* line · `Expected Output` = the *Deliverable* path + format ·
`Validation Criteria` = the *Acceptance* line · `Test Command` = `./.venv311/bin/python
scripts/check_otto_batches.py <batch-id>` · `Technical Constraints` = §3 contract ·
`Autonomy Tier = "🔴 Red — full human gate"` (research feeding served content is never auto-approved).
`Dependencies`: A3 blocks the asserted-visa advisory; D2 must reference the 4 existing NO_FR facts.

## 8. Guardrails — what Otto must never do

- Never write code, a migration, or the database. Deliver files.
- Never null or guess `applies_to.nationality` — it is the field that decides who sees a visa
  requirement. Read it from the fact.
- Never emit `fact_type:"step"` into the fact stream — steps are the roadmap graph I own.
- Never invent a source, number, fee, deadline, or confidence. Absent stays absent.
- Never set a served status. Everything is `pending` / `representative`.
- Never merge to `main` or promote past candidate.

---
---

# Andrea's relocation case — completing the end-to-end journey (demo-first)

> **Execution log (this pass):**
> - **Workstream 1 (Stage 2) — DONE.** [#1958](https://github.com/rlecomte1929/rolec/pull/1958)
>   MERGED (backend: 7 CSEP step traps carried through the overlay to both roadmap surfaces),
>   [#1959](https://github.com/rlecomte1929/rolec/pull/1959) in CI (frontend: amber "Easy to
>   miss" callout on the task list). Corrected mid-flight from "content tweak" to a vertical
>   slice — the honest home was step annotations, not `requirement_items` rows.
> - Next: workstream 3 (intake `holds_eu_ltr_in_spain` → asserted advisories), then the
>   `rce.*` audit trail (workstream 2/5, better as a create-hook than a one-off prod write).


> This plan sits above the "Otto → Served" pipeline plan below it, which is the shipped work
> from this session (7 merged PRs). That work made Andrea's **immigration roadmap** correct and
> visible. This plan captures everything *else* her case touches — intake, documents, services,
> vendors, HR oversight, audit trail, and the Spain-departure side — so the whole journey holds
> together as something you can show.

## Context

Andrea is a Venezuelan national, legally resident in Spain, relocating **Madrid → Dublin** for
Google with a spouse and two children — corridor `ES_IE`, pathway `CSEP_2026`, nationality class
`THIRD_COUNTRY`. She is a named, first-class fixture in the code (`nationality_class.py:120`:
*"Andrea, the first real ES→IE case, is Venezuelan"*).

This session fixed her immigration roadmap: the CSEP journey now reaches her live task list, the
non-obvious advisories render with the honest asserted/conditional distinction, and free-mover
mis-serving is gone. But a relocation case is far more than the visa track, and two Explore
passes plus direct DB/engine reads found the rest of her journey is uneven — some parts polished,
several empty or hedged.

**Goal (chosen): a flawless end-to-end demo.** Order by what a viewer sees, front to back, and
fix whatever breaks, reads as hedged, or returns empty on Andrea's path. **Spain-departure is in
scope** — her real move has an exit side, and today it is modelled nowhere.

**What already works for her** (don't touch): intake captures VE/ES→IE/employment/family/date and
the name→class resolution is correct; the immigration roadmap and advisories; HR feasibility (the
104-day runway renders); passport and diploma extraction; Dublin neighbourhoods and schools have
real recommendation data; the RFQ plumbing itself.

---

## The gaps, as a viewer meets them

### Stage 1 — Intake: the roadmap is correct but hedged, because the wizard doesn't ask enough

The CSEP pathway declares inputs the wizard never collects (`roadmap_corridor_overlay.py` docstring
says so outright), so advisories that *should* be definite for Andrea stay conditional:

- **`holds_eu_ltr_in_spain`** (`CSEP_2026/v1.yaml:131-133`, `USER_INPUT`) — for Andrea this is
  **true**, and it is exactly what makes "your Spanish long-term residence does not transfer to
  Ireland" a *statement about her* rather than a generic "if you hold…". Unasked, so the advisory
  renders conditional.
- **`visa_required_nationality`** (`v1.yaml:105-107`, `EXTERNAL_LOOKUP`) — the ISD visa list does
  not exist in the repo, so the D-visa advisory stays conditional even though for VE it is
  knowably true.
- `has_relevant_degree`, `gross_salary_annual` (only a coarse band is collected), full
  `intended_stay_months` — CSEP eligibility inputs the wizard skips.

**Fix:** add the CSEP-relevant intake questions (`intakeSteps.ts`, `EmployeeIntakePage.tsx`,
`intakeToCaseDraft.ts`), and seed a minimal ISD visa-required lookup (a static table with VE=true
is enough) so the two load-bearing advisories resolve to **asserted** on her case. Wire the
answers through `wizard_draft_mapper.py` → the overlay's `asserted` logic. **Effort: M.**

### Stage 2 — Roadmap content: two of her sharpest "easy to miss" traps don't surface

- **The emergency-tax 40% number never reaches the UI.** The fact exists and is correctly flagged
  (`seeds/facts/IE.yaml:121-150`, "rising to 40% from week five", `non_obvious: true`) but is in
  the `HOLD` set in `seed_corridor_facts.py:96-98` because it collides with the approved PPSN row —
  so the served row is the bland PPSN one and the number is lost (`docs/corridors/DATA-PATHS.md`).
- **The Dublin rental payslip catch-22 carries no badge.** `payslip_catch22`
  (`seeds/facts/IE.yaml:303-317`) is `non_obvious: true` but `kind: preparation_item, status:
  staged`, which `seed_corridor_facts.py:200-202` skips entirely — so no requirement row, no
  badge. The served "Dublin rental market" row is `non_obvious=false`.

**Fix — CORRECTED after execution.** The original "enrich a requirement row" plan collides with
the honesty model this session hardened: each fact carries exactly one citation (so the 40% number
can't be appended to the badged Revenue row, whose source page doesn't state it), and the payslip
catch-22 deliberately carries **no source** ("market practice, not a published rule"), so it can't
become a cited served row. Also, the 40% number *already reaches the UI* on the PPSN row — that row
is just `non_obvious=false`.

The honest home for both traps is the **corridor step graph**, which already marks 7 CSEP steps
`non_obvious: true` with the explanations in YAML comments (the 40% rate on `REVENUE_REGISTRATION`,
the proof-of-address catch-22 on `BANK_ACCOUNT`). The `CorridorStep` dataclass parses `non_obvious`
(loader.py:134,637) but the overlay **drops it** — the exact analogue of the advisories bug #1953
fixed, one layer down. So: add a `non_obvious_note` field, lift the comment text into it on the
CSEP steps, carry `non_obvious` + note through the overlay to the roadmap step, and render the badge
+ note. Two PRs (backend then frontend), mirroring #1952/#1953. **Effort: M, not S** — a vertical
slice, not a content tweak. This surfaces both traps on Andrea's actual steps, honestly.

### Stage 3 — Documents: Andrea uploads her Google contract and nothing extracts

Passport (4× VE, via MRZ) and diploma extraction work. The rest of her CSEP `required_documents`
don't:

- **Irish employment contract → emits nothing.** `employment_contract.py` detects only FR/DE/NO
  locales; an English/Irish contract yields `jurisdiction is None` → zero fields
  (`employment_contract.py:443-454`). This is the sharpest demo break — her Google contract is the
  centrepiece document.
- **Spanish TIE** — no dedicated extractor; only reachable via the generic `VISA_PERMIT` agent if
  classified `RESIDENCE_PERMIT_EU`.
- **Marriage cert, birth certs** — agents exist and work, but the classifier can't route them
  (Cohort-1 gap, `document_type_vocabulary.py:87-88`), so her family docs classify as UNKNOWN.
- No extractor at all for employment permit, D-visa, private medical insurance, proof-of-address.

**Fix (demo-scoped):** add an IE/EN locale to `employment_contract.py`; route the Spanish TIE and
the marriage/birth certs through the classifier so her family's real documents extract. The
permit/visa/insurance/address extractors are lower priority (she may not upload them in a demo).
**Effort: M.**

### Stage 4 — Services & vendors: the Dublin marketplace is mostly empty

Neighbourhoods and schools return real Dublin data. Movers, banks and housing agencies fall back
to Singapore/Munich/Oslo datasets, and there are **no Dublin/ES-IE supplier rows at all** — so an
RFQ for a Dublin mover or a CSEP immigration solicitor has no recipients. ES-IE isn't in
`hr_vendors.py` `KNOWN_CORRIDORS`.

**Fix (demo-scoped):** seed a handful of real Dublin providers (a mover, a housing agency, a CSEP
immigration solicitor, an Irish bank) into the supplier registry; add `ES-IE` to `KNOWN_CORRIDORS`;
add Dublin rows to the movers/banks/housing-agency datasets. Enough that the RFQ flow shows real
recipients. **Effort: M (mostly content/seed).**

### Stage 5 — HR view: feasibility works, the timeline is unconfirmed

HR sees Andrea's 104-day runway verdict (`feasibility_for_case` → `hr_case_detail.py`). But the HR
timeline/roadmap-review reads the **persisted** `case_milestones` table, not the live corridor
overlay — so whether HR sees her 13 CSEP steps depends on those milestones being persisted, which
no seed confirms. **Verify first**, then wire if it's a gap (shares machinery with Stage 6).
**Effort: S to verify, M if a fix is needed.**

### Stage 6 — Audit trail: "prove compliance to your manager" returns empty

`rce.steps` / `rce.cases` hold **0** rows for ES_IE (confirmed live). `hr_case_detail.py:587` and
the audit-export endpoint select from `rce.*` and silently degrade to `[]`. `persist_corridor_case`
(`corridor_persistence.py:204`) can materialise ES_IE — the loader supports it — but it is
**operator-only**, wired to no request path; its own docstring calls the per-case create-hook "a
future" that doesn't exist.

**Fix:** run `populate_rce_from_cases.py` for Andrea's case (operator, immediate demo unblock),
and wire a create-hook so any new ES_IE case gets its audit trail (the durable fix). **Effort: S
operator + M for the hook.**

### Stage 7 — Spain departure: modelled nowhere (in scope)

`corridors/ES_IE/facts.yaml` has `origin_facts: []`; the comment says the Spain-side obligations
"were among the 100 facts left staged." Nothing models baja del padrón, social-security
detachment, or tax exit for an outbound-from-Spain case, and `seed_corridor_facts.py` writes a
requirement row **only** for `destination_facts` — origin facts get a source record and no served
row. `requirement_items` has no origin column, which is the deeper "content is origin-specific,
serving is not" limitation.

**Fix (two parts):** (a) a **research batch** (the Otto → GCS → candidate path in the plan below)
for the Spain-departure obligations — baja padrón, Seguridad Social baja / A1-equivalent, AEAT
exit; (b) the **code** to serve origin-side rows: extend `seed_corridor_facts.py` past
`destination_facts`, and decide how origin obligations attach to a case that is keyed on
destination. **Effort: L (research + modelling).** This is the one workstream that is not a quick
fix; sequence it in parallel and land it last.

### Stage 8 — Assurance on the 4 counsel-flagged rows

The four VE→IE family/entry rows (`spanish_residence_does_not_grant_irish_entry`,
`csep_immediate_family_reunification`, `spouse_stamp_1g_right_to_work`,
`dependant_join_family_d_visa_required`) are approved and serving with `needs_lawyer_review` still
in their citations. Accurate, so low risk for a demo — but they should carry the honest
"not legally reviewed" assurance badge (the model already exists from this session), and the SME
practice-scope rail (Phase 6 of the pipeline plan below) is the durable home for clearing them.
**Effort: S for the badge; the rail is already planned below.**

---

## Recommended sequence (demo-first)

Ordered by visibility-per-effort. The first sprint is all S/M and makes the *visible* journey
correct end to end; the L workstream (Spain departure) runs alongside and lands last.

| # | Workstream | Stage | Effort | Why this slot |
|---|---|---|---|---|
| 1 | Surface the emergency-tax number + badge the rental catch-22 | 2 | S | Her two sharpest traps; pure content; instant demo payoff |
| 2 | Populate `rce.*` for her case (operator) | 6 | S | Turns the empty audit-export into a real one, today |
| 3 | Intake asks `holds_eu_ltr_in_spain` + ISD lookup seed | 1 | M | Flips the two load-bearing advisories from hedged to asserted |
| 4 | Irish employment-contract extractor (+ TIE, marriage/birth routing) | 3 | M | Her Google contract must extract; family docs must classify |
| 5 | Verify + wire HR timeline parity; create-hook for `rce.*` | 5,6 | M | HR sees the same 13 steps; audit trail becomes automatic |
| 6 | Seed Dublin vendors + `ES-IE` corridor; marketplace datasets | 4 | M | RFQ shows real recipients instead of empty |
| 7 | Assurance badge on the 4 flagged rows | 8 | S | Honesty, cheap, reuses this session's model |
| 8 | **Spain-departure research batch + origin-side serving** | 7 | L | Parallel track; the only non-quick piece; lands last |

**First sprint = 1, 2, 3.** They're the highest-visibility, lowest-effort, and they make the
core demo path (roadmap traps → asserted advisories → real audit trail) correct without touching
schema.

## Verification

- **Stages 1-2 (roadmap correctness):** drive `derive_roadmap` for Andrea's draft (VE, ES→IE,
  family) offline — no DB, no keys, as done throughout this session. Assert the emergency-tax
  consequence text and a badged rental row appear, and that with `holds_eu_ltr_in_spain=true` the
  LTR + visa advisories come back `asserted: true`, not conditional.
- **Stage 3 (documents):** run the Irish contract through `employment_contract.py` and assert
  non-empty fields with `jurisdiction='IE'`; classify a Spanish TIE and a marriage cert and assert
  they route to a real agent, not UNKNOWN.
- **Stage 6 (audit trail):** after `populate_rce_from_cases.py`, re-query `rce.steps`/`rce.cases`
  for ES_IE (expect 13 steps + the case) and confirm `GET /api/hr/cases/{id}/steps` returns them.
- **Stage 4 (vendors):** create an RFQ for a Dublin mover and assert the recipient pool is
  non-empty.
- **Stage 7 (Spain departure):** follow the research-batch gate discipline in the pipeline plan
  below — commit artifacts + a gate script, load as candidates (`pending`), never auto-approve.
- **Every stage:** the full backend suite stays at the 23 pre-existing origin/main failures, none
  new — the bar held for all 7 PRs this session.

---
---

# Otto → Served: an engineered plan for the requirement-fact pipeline

*(The shipped work from this session — 7 merged PRs. Retained below as the record of what made
Andrea's immigration roadmap correct, and as the home of the research-batch discipline and the
SME/assurance rail that Stages 7-8 above reuse.)*

---

## Execution log

| PR | What | State |
|---|---|---|
| [#1950](https://github.com/rlecomte1929/rolec/pull/1950) | Phase 0 — eval framework cherry-pick | **MERGED** |
| [#1951](https://github.com/rlecomte1929/rolec/pull/1951) | Phase 1.1/1.2 — nationality gating, dropped steps, duration | **MERGED** |
| [#1952](https://github.com/rlecomte1929/rolec/pull/1952) | Corridor journey on the live employee surface | **MERGED** |
| [#1953](https://github.com/rlecomte1929/rolec/pull/1953) | Advisory rendering, with the `asserted` honesty rule | **MERGED** |
| [#1954](https://github.com/rlecomte1929/rolec/pull/1954) | Phase 3.1 — `applies_to.status` refusal + B3 = `professional` | **MERGED** |
| [#1955](https://github.com/rlecomte1929/rolec/pull/1955) | Precision axis (`must_not_serve`) + real-engine harness | In CI |

**Production data repair (approved 2026-08-21):** 13 orphaned `purpose='other'` rows from the
B3 promotion flipped to `employment`. Pinned by id, dry-run in a rolled-back transaction
first; approved count unchanged at 101, total unchanged at 156, zero natural-key duplicates.
`id` deliberately left as the stale `uuid5(country|other|title)` — `create_requirement_item`
matches on the natural key and never touches `id`, so a re-promote updates rather than
duplicates, and rewriting the PK would have risked the `corridor_attestation_items` FK.

### What execution changed about the plan

**The roadmap has three representations, not one.** Traced before building, and it
invalidated plan item 1.3's "purely frontend" assumption:

| surface | source | corridor content? |
|---|---|---|
| Employee roadmap page | `/api/assignments/{id}/timeline` → `compute_default_milestones` | ✅ already |
| HR case timeline | same | ✅ already |
| Plan email | `derive_roadmap` directly | ✅ already |
| `/employee/tasks` | `/roadmap/tracks` (form-projected) | ❌ → **fixed in #1952** |
| `GET /roadmap` (v1, carries `advisories`) | `derive_roadmap` | **zero frontend callers** |

So "advisories aren't rendered" understated it: the v1 endpoint that carries them is
called by nothing. #1952 puts corridor steps and advisories on `/roadmap/tracks`, which
`EmployeeTaskPage` genuinely renders. **Advisory *rendering* is still open** — the payload
now arrives, no component reads it.

### Defects found during execution that the audit missed

1. **`totals.time` = `"1 days"` on FR→NO** (255 production cases), emailed to families
   under a bare "Overview:". Fixed in #1951.
2. **`pre_arrival_days` was a sum, not a path** — NO_FR reported 349 pre-arrival days
   against a 79-day journey. `feasibility.required_lead_time_days` already did it right;
   the duplicate is deleted.
3. **Root cause of the silent drop**: `JOB_OFFER_CONTRACT` and `TRAVEL_TO_IE` were filed in
   the `visa` lane. `timeline_service._CORRIDOR_STEP_PHASE` already classified them
   `pre_departure` and `logistics`. Re-homed; the visa lane is now exactly the
   immigration-gated set, pinned by a test.
4. **`STAMP4_ELIGIBILITY` would have become a permanent employee task** — it is
   `outcome_type: nothing_to_do`. Now `owner="informational"`: on the roadmap, not in the
   task list.

### Confirmed by execution

- The eval framework **scores 1.0 on every slice against the real engine** — exactly as
  predicted. It is landed as infrastructure, wired into **no CI gate**. The precision axis
  (`must_not_serve`) is what makes it able to fail, and the gate should be switched on only
  when both halves exist.
- Every fix was **written test-first and proven red against `origin/main`**.
- Full suite after each change: the 23 pre-existing failures on main are unchanged, **none
  introduced**.

---

## Context

Otto researches cross-border relocation requirements in the Audos workspace and delivers
NDJSON + manifest batches. Research is **free and continuous**. Yet almost none of it reaches
a user, and the small amount that did got there by a bulk rubber-stamp that published four
claims its own batch contract said must not ship.

Measured in production, 2026-08-21:

| Fact | Number |
|---|---|
| Rows stuck in `otto_staging` at `status='ready'`, never promoted | **109** (14 countries, oldest 10 days) |
| Rows in `requirement_items` at `review_status='pending'`, withheld from every reader | **55** of 156 (35%) |
| Committed corridors that serve **nothing** (`_not_covered`) | **3 of 11** — IE_ES, FR_ES, FR_CH |
| Approved rows served with **no citation at all** | **17** (US 8, SG 5, DE 4, NO 1) |
| Rows with `attestation_status` set | **0** — the SME rail is built and unused |
| Rows that are `expert_verified` | **0** — and no counsel exists to create one |

**No code path anywhere flips `new` → `ready`.** Only four sites write
`immigration_fact_candidates`, and the `otto_writer` role has no `UPDATE` grant
(`20260811222105_otto_writer_role.sql:29-30`). Every promotion so far was hand-run SQL.

### The diagnosis

The bottleneck is not research, and not a missing gate. **Review is expensive and blind.**
The reviewer's entire surface is one Publish/Withhold pair
(`frontend/src/components/admin/CountryDetail.tsx`), and it renders neither `nonObvious`,
`timing`, `lastVerifiedAt`, the evidence quote, the non-obvious divergence pair, nor the
`needs_lawyer_review` flag — which has no column and hides inside the citation object
(`backend/imports/otto/mappings.py:165-166`). `AdminRequirementReviewDTO` is strictly poorer
than the employee-facing `RequirementItemDTO`: **the person deciding whether to publish sees
less than the person reading the result.**

Given that surface, only two behaviours are available: **don't review** (109 + 55 rows) or
**approve everything** (the 9-row bulk approve at 12:02:59 UTC, which published all four
counsel-flagged rows). Both failure modes are present at once — the signature of a missing
system, not a careless operator.

**Thesis: make review cheap, informed and safe, and Otto's output converts to served value on
its own.** Everything below serves that sentence.

### Decisions taken (product owner)

1. **There is no counsel.** Reviewers are the founder plus reachable relocation agents/SMEs,
   who confirm *practice*, not *law*. A gate that blocks on counsel is a permanent blocker and
   therefore the wrong design. `expert_verified` stays honestly empty.
2. The four counsel-flagged Irish rows **stay live, visibly badged as not legally reviewed.**
3. The 17 uncited approved rows **stay live, visibly badged as carrying no source**, then get
   backfilled by Otto.
4. **Pipeline first** — build intake + review machinery, then drain through it.
5. **ES_IE is the proving ground**, despite being only 18 of ~1,800 cases: it is the one
   corridor validatable against a real named person. Note it is already 29/29 approved, so
   there is nothing there to *drain* — what it needs is correctness and evidence. SPAIN is the
   first real drain.

Decisions 2 and 3 are one decision: **serve it, but say what you don't know.** That is a
single assurance model, not two special cases.

### Repo rules that bind

New `public` tables need RLS + policy + `REVOKE ALL FROM anon`; a migration and code reading
its new column **cannot ship in the same PR** (`scripts/check_column_read_before_apply.py`,
unconditional at ci.yml:847); routers register in *both* `backend/main.py` and
`backend/app/main.py`; prod migrations are applied out-of-band, never by CI; **never
batch-merge two migration PRs** — GitHub does not re-run a PR when its base moves.

### Deliberately out of scope

**1,004 of ~1,800 `relocation_cases` have NULL origin/destination** — larger than every real
corridor combined. They resolve to no corridor, so no overlay, no requirements, no
feasibility. That is a case-intake defect; folding it in would double this programme. Flagged
so it is not mistaken for something this plan fixes.

---

## Phase 0 — Land what already exists ⚠️ *(highest ROI; one serious hazard)*

A complete sliced-eval framework and a human-only verification guard **are already written**
and worth nothing unmerged. They exist only on `claude/relopass-esie-audit-99259d`, absent
from `origin/main` by content (`git cherry`).

| commit | gives us |
|---|---|
| `79aaee1e` | `verification_guard.py` — `expert_verified` unforgeable by automation (actor deny-list; `mark_expert_verified()` the single write path; "reject, don't downgrade"). +333 lines of tests. |
| `3c8b7909` | `nonobvious_recall.py`, `hlp_nonobvious_baseline.json` (6 slices, **2 ES_IE**), runner, dashboard + UI wiring. **No mean anywhere — the headline is `worst_recall`.** |
| `54e903b1` | Corridor imports idempotent — a duplicate import inserts zero rows. |

`e3a428ee`, `f9a3edd8`, `8396789f` are already on main by content. Skip them.

> ### ⚠️ Do not merge this branch — cherry-pick
> The branch is **68 commits behind** main and 59 ahead (~50 of them duplicate `docs(stripe)`
> noise). Critically, `roadmap_corridor_overlay.py` **exists on main and not on the branch** —
> the branch predates AIQ-1867. **A merge resolving `roadmap_builder.py` toward the branch
> reverts the entire corridor overlay**, deleting the feature the eval exists to measure.
> Cherry-pick `3c8b7909` → `79aaee1e` → `54e903b1`, resolving `roadmap_builder.py` **in favour
> of main**.

**Two mechanical hazards, both confirmed.** Migration timestamps must be restamped:
`20261108000000` is already taken on main. Prod ledger max `20261114000000`, repo max
`20261115000000` → **stamp above `20261115000000`**. And both commits bundle a migration with
the code reading its new columns, so each splits into a migration PR (applied out-of-band)
then a read PR. Neither `verified_by`/`verified_at` nor `batch_id` exists in prod today.

---

## The correction that changes the design

The obvious move — reuse the well-built attestation rail to get relocation agents signing off
— **cannot ship as is.** Verified verbatim on `origin/main`:

- `DISCLAIMER_TEXT` (`attestation.py:85-93`) opens *"I confirm that I am a qualified legal
  professional acting in my professional capacity"* and asserts the requirements *"accurately
  reflect the applicable law."*
- `create_attestation` (`:243`) filters `review_status == "approved"` — the rail cannot do
  pre-publication review at all.
- `promote_attestation` writes `attestation_status='attested'` unconditionally.

Sending that to a relocation agent either gets it signed falsely or not signed, and would make
practice confirmation indistinguishable from counsel sign-off in every downstream badge — the
same class of error as the "EU AI Act Ready" badge CLAUDE.md has a hard gate about, and the
`verified` → "Expert-verified" mislabel fixed in #1922.

**Required before any SME is invited:** `scope='practice'` with its own disclaimer ("…direct
professional experience administering this process… a statement of observed practice, not
legal advice…"), its own `disclaimer_version`, `include_pending` to allow pre-publication
review, and a promote branch writing `assurance_status='practice_confirmed'` — **never**
`attestation_status='attested'`. This is the one item I would refuse to ship unmodified.

---

## Phase 1 — Stop shipping wrong answers *(small, no migration, ships first)*

All four items verified live on `origin/main` in this session.

**1.1 Nationality-gate the advisories and the family step.**
`roadmap_corridor_overlay.py:211-226` builds advisories with no `is_third_country` check, and
`FAMILY_REGISTRATION` is in `_FAMILY_GATED` but not `_IMMIGRATION_GATED`. A Spanish free mover
correctly gets 0 immigration steps, yet is still told to obtain a 'D' visa before travel and is
*asserted* (`asserted: true`) to receive a CSEP Stamp 1G spouse permission. The module's own
docstring says it exists to prevent exactly this.

**1.2 The dropped-step / wrong-duration defect — the widest-blast-radius bug found.**
`_TRACK_BY_STEP` puts `JOB_OFFER_CONTRACT` and `TRAVEL_TO_IE` in the `visa` track;
`derive_roadmap` builds no visa track for a free mover, so `_apply_corridor_overlay`'s
`if track is None: continue` drops them — but `corridor_overlay` already counted them into
`pre_arrival_days`, and `time_estimate` overwrites `totals.time`. Measured:

| case | `totals.time` | dropped | longest rendered step |
|---|---|---|---|
| Venezuela ES→IE | ~15 weeks | — | 40d |
| **Spain ES→IE** | **~2 weeks** | `JOB_OFFER_CONTRACT`, `TRAVEL_TO_IE` | 21d |
| **France FR→NO** | **"1 days"** | — | 21d |

**FR→NO has 255 production cases** and tells a French family their relocation takes *one day*.

**1.3 Render the advisories.** `GET /{case_id}/roadmap` has **no `response_model`**, so
`advisories` already reaches the wire — purely frontend. Reuse
`components/antigravity/Alert.tsx` (correct `role`/`aria-live` per variant) and rhyme with the
existing counsel-referral box at `RoadmapScreen.tsx:338-353`. Honour `asserted`.

**1.4 The assurance badge — derivable today, no migration.** All four counsel-flagged rows
still carry `needs_lawyer_review: true` inside `citations_json` (verified), so decisions 2 and
3 both ship now: "Not legally reviewed" from the citation flag, "No source recorded" from an
empty `citations_json`. **Wording is load-bearing** — not "unverified" (implies wrong), not
"pending legal review" (implies a lawyer is coming; none is). Same discipline as the
`verified` → "Reviewed" decision. The column follows in Phase 3 as the durable form.

---

## Phase 2 — Generalized intake

**2.1 `batchspec`** — a converter library with **closed strategy registries**, driven by a
per-batch `docs/imports/<batch_id>/batch.yaml` beside the artifact. New
`backend/imports/otto/batchspec.py` + `scripts/convert_otto_batch.py`, replacing both
per-batch converters. **Not an expression DSL** — that moves bugs from reviewed Python into
unreviewed YAML. An unknown key is a refusal, mirroring `mappings.Unmapped`.

Registries need only what covers both existing batches: composers
(`statement_plus_divergence`, `divergence_only`); nationality (`from_field` — VE→IE, which
must *not* derive from corridor; `from_corridor` — B3); status (`literal`, `from_map`,
`refuse`). *Safety test:* output must be **byte-identical** to each legacy converter's
committed JSONL — a test that exists only until 2.3 deletes them.

**2.2 One CI gate that cannot rot.** `scripts/check_otto_batches.py` replaces
`check_ve_ie_batch.py` + `verify_b3_batch.py` (neither is in CI today). Per batch: sha256 vs
manifest, spec reconcile assertions, real `parsers.read_jsonl` with zero rejections, the
AIQ-2034 unconfirmed-quote check, no served status, and — new — `_unscoped_topics()` must be
**empty** (today it only reports). Anti-decoration, per `check_corridor_facts.py:55-62`:
**exit 2 on zero batches examined**, and **exit 2 if any `docs/imports/<dir>/` holds an ndjson
+ manifest but no `batch.yaml`**. The second clause is what stops it rotting. Always-on job,
no DB secret, so it can be a required check.

**2.3** Delete the four bespoke scripts — **separate PR**, or the equivalence test deletes its
own reference.

---

## Phase 3 — Close the silent holes, then make review cheap

**3.1 `applies_to.status` must refuse loudly** (`mappings.py:218`). An absent or conflicting
status silently yields `purpose='other'`, which the strict-equality reader can never return.
Give it the three-branch refusal `nationality` already has; explicit `"any"` still maps to
`other`. *B3's 14 topics carry no status and will refuse* — **nothing regresses**, because
`resolve()` runs at promote time only and a `purpose='other'` row is *already* unservable.
This converts a silently-dead row into a loud worklist entry. Say that plainly in the PR.

**3.2 `new` → `ready` as an auditable action** — `executor.mark_ready(batch_id, actor,
reason)`, **refusing if the batch's latest `load_log.reconcile_status != 'pass'`**.
Deliberately *not* an HTTP endpoint: a fact-level approve UI over `otto_staging` is the exact
pattern the executor's own docstring calls this codebase's recurring failure.

**3.3 One migration.** `requirement_items` gains `source_batch_id`, `source_topic_key`,
`source_destination_country` (ISO — the catalog name is one-way), `assurance_status`,
`assurance_reason`. **Migration PR alone.** `assurance_status`, not `needs_lawyer_review`:
under decision 1 a column demanding a lawyer is a permanently red state people learn to
ignore. Values `NULL` | `assurance_required` | `practice_confirmed` | `counsel_attested`
(reserved). Keep it separate from `attestation_status` — different writers, different
lifecycles; the console collapses them visually, which is where collapsing belongs.

**3.4 Why traceability blocks the console.** `compose_description` (`mappings.py:115-125`)
joins `fact_text` only — **`evidence_quote` never reaches `requirement_items` at all.**
Showing a reviewer the evidence requires reading back into `otto_staging`, which requires the
join key from 3.3. A hard prerequisite, not a parallel nicety.

**3.5 The review DTO.** Add `nonObvious` and `timing` (the employee DTO already has them),
plus `evidence[]` (quote, source, verbatim-confirmed state), the `divergence` pair as a
struct, `assuranceStatus`, and `wouldChange` (`isFirstForCorridor`, `approvedSiblingCount`) —
the field that makes the queue self-prioritising, because it is the difference between
France's 27th row and un-breaking IE_ES. Render via a new `RequirementReviewCard.tsx`
extracted from `CountryDetail.tsx:102-180`, so the *existing* page gains every signal for
free. A cross-country `GET /api/admin/requirements/review-queue`, paginated from the start.

**3.6 Bulk approve with forced acknowledgement.** `POST /api/admin/requirements/bulk-review`
**422s unless the caller's acknowledgement counts equal the server's own count of exceptional
rows.** Under this rule the 12:02:59 request fails until the operator states "I know 4 of
these are assurance_required". It does not *block* — consistent with decision 1 — it forces a
deliberate act. Audit one row **per requirement** plus a batch row; the incident is legible
today precisely because per-row audit exists.

---

## Phase 4 — Prove on ES_IE, then drain

ES_IE needs correctness and evidence, not draining: Phase 1's fixes, the `rce.*` rows so the
audit trail stops returning `[]` silently (prod `rce.steps` holds 9 corridors; ES_IE is not
one), and the golden fixture below. Validate against Andrea.

**Then drain:** SPAIN's 25 (revives IE_ES + FR_ES) → the 17 uncited rows via Otto backfill →
the 109 staged rows.

**FR_CH is not a review problem.** SWITZERLAND has **0 rows**, not 0 approved. No review fixes
it; it needs research. The queue must render "nothing to review" and "nothing approved" as
distinct states, or a research gap masquerades as a review backlog forever.

---

## Metrics, evals and validation

> ### The finding that reshapes this half
> Driving the **real** engine through all six HLP slices scores **1.0 on every one**. So
> replacing the hand-written fixture with real roadmaps changes the number **by zero**. And
> the reason is structural: **`nonobvious_recall` is pure recall, while every defect found is
> an over-serving defect.** Telling a Spanish free mover to get a 'D' visa costs zero recall.
>
> **Wiring real roadmaps in buys honesty, not signal. The missing half is a precision axis.**
> Shipping it alone would be a green gate that provably cannot fail — the exact decoration
> this programme exists to remove. **M1 and M2 must land in the same PR.**

### Gating CI (network-free, DB-free, inside the existing `backend-tests` job)

| | Metric | Definition | Threshold |
|---|---|---|---|
| **M1** | `nonobvious_recall` | worst slice of `served/total`; served ⟺ match appears in **every** roadmap for the slice. No mean. | 1.0, and `unscored == 0` |
| **M2** | `overserved_requirements` **(new)** | each slice gains `must_not_serve[]`; count matches appearing in any produced roadmap **or advisory**. A sum, not a rate. | **0** |
| **M3** | `roadmap_render_parity` **(new)** | computed corridor steps == rendered corridor steps; and `totals.time` ≥ longest **rendered** step. Pure arithmetic, no legal claim. | 0 dropped |

M2 and M3 **fail against today's main**, unmodified. M1 does not.

*Two traps:* never name a report `nonobvious_recall_*` — `_metric_key_for_filename` matches by
`startswith` and would plot it on the recall chart. And `load_live_reports` hardcodes
`aggregate >= threshold`, so a count-down metric reads backwards; emit `1.0 if violations == 0
else 0.0` and keep the raw count in the payload.

### Report-only, scheduled (extend `compliance-daily.yml`; do not create jobs)

- **M4 `assurance_label_honesty`** — a **count** with a draining baseline, not a share
  ("97% honest" is the frame `nonobvious_recall` was built to refuse). Approved rows that are
  `representative` with empty citations (17 today), or `expert_verified` with NULL
  `verified_by`. **Extend `check_requirement_provenance.py`**, don't write a new script.
- **M5 `corridor_serving_coverage`** — corridors with ≥1 **approved** row for the destination
  (SPAIN's 25 pending serve exactly as much as zero). Today ≈ 8/11.
- **M6 `review_sla_compliance`** — **age, not size**. 109 rows is a number; 109 rows with a
  10-day tail is the problem. Fraction of open items younger than 14 days; payload carries
  `oldest_days`, `p90`, `n_open`.
- **M7 `promotion_throughput_ratio`** — promoted / delivered, trailing 7 days. The one metric
  that measures this programme's thesis.

*Cut:* backlog size as a headline (hid the tail); time-to-served as its own family (derivable
from M6); any cross-slice mean.

### The HLP honesty problem

`hlp.standard = "lawyer_verified"` names an assurance the programme cannot reach, and all six
slices sit at `pending_lawyer_signoff`. Replace the file-level constant with a per-slice
**ladder**: `authored` → `practitioner_confirmed` → `lawyer_verified` (kept precisely so its
emptiness is visible). All six are `authored` today, which means **the baseline and the
roadmap derive from the same corridor YAML — recall 1.0 means the pipeline delivers what the
YAML says, not that the YAML is right.** That sentence goes in the file, the runner's stdout,
and the dashboard footnote.

`AdminRagQualityPage.tsx`'s `SliceBreakdown` already *receives* `hlp_status` and renders it
nowhere — the same defect as the unrendered advisories, one layer up. Add an **Assurance**
column and make the card label data-driven. `practitioner_confirmed` requires a mandatory
`not_opined_on` field, and a test asserting no slice claims that tier with an actor failing
`verification_guard.is_human_actor`.

**An SME tier belongs on `requirement_items.verification_status` too** — without it, every
confirmation the founder can actually obtain is unrecordable: `representative` understates it
and `expert_verified` is (correctly) rejected by the guard. Needs a CHECK migration and its
own write path; **defer to a later phase**, nothing here blocks on it.

### The ES_IE golden fixture

`backend/tests/fixtures/eval/es_ie/es_ie_gold.jsonl`, following the five established
conventions. Four cases: the VE family (passes today); **the ES family — fails today on four
independent counts**; ES solo (isolates nationality from family gating); and
`nationality: ""`, which pins the **fail-open** stance so nobody "fixes" the gate by making
`classify` fail closed and hides the visa from a real visa-required national.

Catching "advisories rendered by nothing" needs a pair, because the backend is already
correct: emit case 1's payload to a committed frontend fixture (CI re-emits and diffs), then
assert in vitest that the advisory text renders. **Fails today — zero frontend consumers.**

Paired poisoned tests use the `test_gold_is_a_real_guard` idiom, but poison the **engine**
(monkeypatch `corridor_overlay → None`) rather than a JSON file — strictly stronger. Known
failures use `xfail(strict=True)` so an unexpected pass is a failure and the file drains
instead of becoming a blindfold.

### Two CI wiring defects to fix first

1. **`backend-tests` is gated on a paths-filter that omits `corridors/**`** — so editing
   `CSEP_2026/v1.yaml` skips the entire eval that measures it. Add `corridors/**` and the
   eval's own fixtures. *A gate whose own config can change while the gate is skipped reports
   green on an unchecked tree.*
2. **`check_requirement_provenance.py` triggers on `changes.migrations`**, but its own
   docstring says rows arrive via operator-run loads, essentially never via a migration. Change
   to `backend || migrations`, add the scheduled run, and add `--require-db` so the scheduled
   run **exits 2** when it cannot connect (it currently `return 0`s).

*Leave `eval-llm-reports.yml` report-only* — every producer ends `|| echo "::warning::"`;
adding a real gate there guarantees the next contributor appends an `||`. Add a header line
saying it carries no quality signal.

---

## Sequencing

| # | Work | Gate to proceed |
|---|---|---|
| 0 | Cherry-pick the 3 commits (resolve `roadmap_builder.py` toward **main**); restamp migrations | `check_serving_llm_isolation` + full pytest green |
| 1 | Phase 1.1–1.4 — the three live wrong-answer defects + assurance badge | Tests written to fail against main first |
| 2 | M1+M2+M3 evals **together**, ES_IE gold fixture, CI wiring fixes | M2/M3 red on main, green after Phase 1 |
| 3 | Phase 2 intake (`batchspec`, one CI gate) | Byte-identical equivalence test |
| 4 | 3.1 status refusal, 3.2 `mark_ready` | Discriminating tests |
| 5 | 3.3 migration PR → operator applies → 3.4/3.5/3.6 readers | Serialise; never batch-merge migration PRs |
| 6 | SME practice scope on the attestation rail | `test_practice_scope_never_writes_attested` |
| 7 | Drain: ES_IE validation → SPAIN 25 → uncited 17 → staged 109 | M5 rises 8/11 → 10/11 |

**If only half the time exists:** keep Phase 1 (wrong answers shipping now), M2+M3 (the only
gates that can currently fail), 3.1, the 3.3 migration started early, and the DTO enrichment
rendered in the **existing** `CountryDetail.tsx`. Cut `batchspec` (keep both converters, ship
only the gate), the standalone review-queue page, and the SME scope *unless an SME is actually
lined up* — in which case it moves to the top, because shipping a legal disclaimer to a
relocation agent is worse than shipping nothing.

## Verification

- **Phase 1:** drive `derive_roadmap` offline for VE/ES/FR/NO — no DB, no API keys (done
  repeatedly in this session). Assert 0 advisories and no Stamp 1G step for an EEA national;
  assert `totals.time` ≥ longest rendered step.
- **Phase 2:** `scripts/check_otto_batches.py` on a planted spec-less batch ⇒ exit 2.
- **Phase 3:** replay the 12:02:59 shape — unacknowledged bulk POST ⇒ 422, **zero** rows
  changed. Validate the migration in a rollback transaction before the out-of-band apply.
- **Phase 7:** re-run the audit queries — pending count, corridors-serving-nothing,
  uncited-approved — and diff against the baseline table at the top of this document.

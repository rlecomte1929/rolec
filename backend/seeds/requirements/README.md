# Requirement seeds — methodic country coverage

How ReloPass populates the immigration **requirement catalog** (`requirement_items`) per country,
methodically and with a learning loop, so STA/LTA/PERMANENT journeys differ correctly.

## The model
- The live requirements engine is `requirements_builder.compute_case_requirements` → `rules_engine.apply_rules`
  → `GET /api/cases/{id}/requirements`.
- A requirement may declare `applies_to_assignment_types_json` (e.g. `["LTA","PERMANENT"]`). `apply_rules`
  drops it for cases of other types; `NULL` ⇒ applies to all. (AIQ-1349.)
- `country_code` is a **FULL UPPERCASE name** (`GERMANY`, `UNITED KINGDOM`). Natural key for upsert:
  `(country_code, purpose, title)`.

## Canonical long-term-only taxonomy
Requirement *types* that apply to LTA/PERMANENT but **not** STA (short stays):
1. **Residence registration** (RESIDENCE) — register address / activate residence permit.
2. **Long-term housing** (HOUSING) — 12-month+ lease / tenancy.
3. **Social-security / tax registration** (SOCIAL_SECURITY) — national insurance / SSN / tax ref.

> School enrolment is intentionally NOT seeded here — it's generated dynamically by `rules_engine`
> (only when school-age children are present) and is already STA-suppressed.

Universal types (apply to all, incl. STA) stay un-tagged: passport validity, employment letter, lead time.

## Process (per country): draft → review → load → verify
1. **Draft** — `python backend/scripts/draft_requirements.py --country <NAME> --purpose <p>`
   grounds an LLM (citation-bound, tool-use) in the immigration RAG corpus and writes a DRAFT YAML
   (`verification_status: draft`, each row citing a corpus chunk + `requires_expert_review`). Never writes prod.
2. **Review** — a human edits the YAML: verify against the official authority, fix wording, set
   `applies_to_assignment_types`, promote `verification_status` → `representative` / `expert_verified`.
   (Optionally route via the review queue — `review_queue_service`, type `drafted_requirement_candidate`.)
3. **Load** — `python backend/scripts/seed_requirements.py --file <yaml>` (idempotent upsert; `--dry-run`
   to preview, `--country` to scope).
4. **Verify** — an LTA case in that country surfaces the long-term requirements; an STA case does not.

## On-demand research lifecycle (the moat — AIQ-1349 P2/P3)
When a corridor is uncovered, customers can request research; it is curated and published under a strict,
human-gated process:
1. **Request** — employee/HR clicks "Request research" on the uncovered-corridor state →
   `POST /api/research-requests` → `research_requests` row (`pending`) + a `research_request` review-queue
   item. `company_id` is resolved server-side (never trusted from the client).
2. **Approve** — admin `PATCH /api/admin/research-requests/{id}` `{status:'approved'}` → `in_progress`
   (a curator owns it; `estimated_cost` recorded).
3. **Curate** — the curator authors `corpus/{from}_{to}_corridor.json` + a requirement YAML
   (citation-bound, tiered official sources, like FR/NL), commits them, and applies via the ops pipeline
   (reindex workflow for the corpus + `seed_requirements.py` for the catalog).
4. **Review (mandatory human gate)** — a human resolves the curation review-queue item
   (`review_queue_service`). Completion is BLOCKED until this is `resolved`.
5. **Complete/publish** — admin `POST /api/admin/research-requests/{id}/complete`
   `{result_summary, actual_cost}` → request `completed`, `actual_cost` recorded (invoice line),
   queue item resolved, and the **requester is notified** (`RESEARCH_COMPLETED`). The corridor is now live.
Nothing goes live without ≥1 citation + the disclaimer + a resolved human review.

## Provenance
Every requirement carries a `verification_status` (column on `requirement_items`, surfaced per-item in
the API + a UI badge): `representative` (curated + cited) → `corpus_grounded` (grounded in the
immigration corpus with citations, e.g. FR/NL) → `expert_verified` (signed off by a licensed
immigration professional). Descriptions end "Indicative — confirm with {authority}" + the global
disclaimer. **Expert sign-off is human-only**: `review_queue_service.create_queue_item_from_requirement_verification(country)`
enqueues a `requirement_expert_verification` task; when a lawyer reviews + resolves it, set the
country's rows to `expert_verified` (e.g. reload the YAML with `verification_status: expert_verified`,
or `UPDATE requirement_items`). FR + NL currently have open expert-verification tasks.

## Recommended tooling
- **Anthropic tool-use (structured output)** for drafting — deterministic JSON schema, citation-bound
  (mirrors `roadmap_generator`).
- **Immigration RAG corpus** (`policy_assistant_chunks`, owner `IMMIGRATION_CORPUS_COMPANY_ID`) as the
  learning substrate — grown by `.github/workflows/immigration-indexer.yml`; the more corridors indexed,
  the better the drafts.
- **Prompt caching** on the corpus/system prompt when drafting many countries (biggest cost lever).
- **YAML in git** as the source of truth (diffable, PR-reviewed) → idempotent loader → prod.

## Coverage matrix
Status per (country × purpose). `LT` = long-term-only types seeded; `U` = universal only; `—` = none.

| Country | employment | other | study | family |
|---|---|---|---|---|
| GERMANY | — | U + LT | — | — |
| NORWAY | U + LT | U + LT | — | — |
| SINGAPORE | U + LT | — | U + LT | — |
| UNITED KINGDOM | U + LT | U + LT | — | — |
| UNITED STATES | U + LT | U + LT | — | U + LT |
| FRANCE | grounded | grounded | — | — |
| NETHERLANDS | grounded | grounded | — | — |
| IRELAND | sourced | sourced | — | — |

**France** is `corpus_grounded` (9 reqs, `US→FR` corpus, VLS-TS / Passeport Talent; only the multi-year
residence-card renewal is long-term-only → LTA 9 / STA 8). **Netherlands** is `corpus_grounded` (8 reqs,
`corpus/us_nl_corridor.json`, Highly Skilled Migrant / EU Blue Card; only permanent residence / extension
is long-term-only → LTA 8 / STA 7), cited to ind.nl / government.nl / belastingdienst.nl. Both scoped to
the non-EEA route (EEA nationals exempt) and pending human `expert_verified` (immigration-lawyer sign-off).

**Ireland** (13 reqs, AIQ-1832) is the first country seeded **`sourced`**: every row was authored FROM a
live official page rather than checked against one — the supporting sentence was located in the fetched
page, quoted verbatim, and the requirement written around it. All 14 underlying claims carry a verbatim
match recorded in `docs/evidence/ireland_requirements_evidence_2026-08-13.json`. Unlike the other
countries it seeds BOTH nationality tracks: `[OWN_NATIONAL, EU_EEA]` gets the affirmative "immigration
requires nothing" answer, `[THIRD_COUNTRY]` gets the Critical Skills permit chain (ES 8 rows / IN 10).
No assignment-type scoping — the STA boundary is not sourced, and the engine's contract prefers
over-showing. Three figures asserted elsewhere in the repo were refuted from source and deliberately
omitted (€60,000 off-list threshold, a 12–16 week decision time, the PDF-only emergency-tax rates); a
test fails if any reappears. Still `representative`, pending immigration-lawyer sign-off.
Both resolve via `requirements_builder._ISO_TO_CATALOG_NAME`.

Extend by drafting → reviewing → loading new countries/purposes; update this table per load.

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

## Provenance
Every seeded requirement is `representative` until expert-verified; descriptions end
"Indicative — confirm with {authority}". This matches the platform's content-honesty model.

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
| FRANCE | U + LT | U + LT | — | — |
| NETHERLANDS | U + LT | U + LT | — | — |

France & Netherlands are loaded as `representative` (FR/NL resolve via
`requirements_builder._ISO_TO_CATALOG_NAME`). Promote to `expert_verified` after legal review —
France is corpus-groundable (`US→FR` chunks); the Netherlands corpus still needs indexing.

Extend by drafting → reviewing → loading new countries/purposes; update this table per load.

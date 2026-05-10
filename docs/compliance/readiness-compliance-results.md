# Readiness & compliance refactor — results

## Root causes

1. **Missing `readiness_templates` on Postgres** — migration `20260321000002_case_readiness_core.sql` (formerly duplicate timestamp `20260321000000`) not applied on some environments; any `SELECT` raised `ProgrammingError` → **500** on readiness summary.
2. **Strict assignment run-compliance** — `400` when employee profile missing, blocking HR from running internal checks during partial intake.
3. **Trust gap** — UI and JSON mixed operational checklist copy with no explicit **legal disclaimer**, no **provenance** for checks, and no **step-by-step** audit narrative for compliance runs.

## Fixes implemented

### Backend

- **`Database._readiness_store_available()`** — probes `readiness_templates`, caches result; `get_readiness_template`, `seed_readiness_templates_if_empty`, and summary path avoid throwing when the relation is missing.
- **`get_hr_readiness_summary`** — returns `reason: readiness_store_unavailable` with `user_message`, `route_references`, versions, disclaimer; merges **provenance block** when resolved.
- **`get_hr_readiness_detail`** — enriches each checklist row via **`provenance_catalog.enrich_checklist_row`** (content tier, reference pointer, human review flag).
- **`provenance_catalog.py`** — central place for reference JSON loading, degraded payloads, SG employment official **pointers** (MOM/ICA URLs in seed data, not UI).
- **`run_compliance`** — allows empty profile; wraps report with **`enrich_assignment_compliance_report`** (categories, primary reference to internal rule pack, `explanation.steps`, disclaimers).
- **Seed data** — `stable_key` on Singapore checklist items; `readiness_checklist_provenance_map.json`; `compliance_reference_sources.json`; `mobility_rules_provenance.json`.

### Frontend

- **`CaseReadinessCore`** — degraded states show **human review**, **official pointer links**, legal disclaimer; resolved state shows collapsible references; checklist rows show reference note + link + badge.
- **`HrCaseSummary`** — compliance section labeled **internal rules**; shows disclaimer, verdict explanation, step-by-step JSON log, enriched blocking rows, actions.

### Database / migrations

- **New:** `20260324120000_compliance_reference_sources.sql` — optional future DB mirror; **v1 canonical data remains JSON in repo**.

## Provenance model (summary)

| Field / concept | Purpose |
|-----------------|--------|
| `content_tier` / `output_category` | `official_source_pointer` vs `internal_operational_*` |
| `reference_strength` | `official` / `internal` / … |
| `human_review_required` | true for immigration decisions and unmapped checklist rows |
| `disclaimer_legal` | “Preliminary screening; not legal determination” |
| `explanation.steps` | Audit trail for compliance run |

## First supported route

- **SG + employment** — template in seed; official pointers for MOM passes hub, EP page, ICA entry; checklist items mapped by `stable_key`.

## Human-review fallback

- Any **missing template**, **missing store**, or **unmapped** checklist item → explicit **Human review** in UI + API flags.
- Assignment compliance **never** claims immigration eligibility; `verdict_explanation` states internal rules only.

## Performance / requests

- Summary remains **one GET**; references are **embedded** in the same payload (no N+1 URL fetches).
- Detail still **one GET** when expanded.

---

## Manual verification checklist

- [ ] Readiness summary returns **200** when `readiness_templates` is missing (degraded JSON, no stack trace).
- [ ] After migration applied, SG employment shows **template** + **references** + disclaimer.
- [ ] `run-compliance` returns **200** with empty profile; report includes `explanation` and `disclaimer_legal`.
- [ ] Each compliance check row includes `output_category` / `primary_reference` / `rationale_legal_safety`.
- [ ] Checklist items with `stable_key` show **pointer** link; without mapping show **Human review** + note.
- [ ] No UI file hardcodes MOM/ICA URLs (only renders API-provided `source_url`).
- [ ] Bump `reference_set_version` in `provenance_catalog.py` when editing `compliance_reference_sources.json`.

---

## First-source policy (immigration)

Order of preference for **stating** something as “verified”:

1. Official government / immigration / embassy primary source (stored record + review metadata).
2. Official e-service or gazetted regulatory publication.
3. Company policy (internal).
4. Vetted expert note (stored, dated).
5. Otherwise: **Unverified** + **human review required**.

The engine **does not** auto-upgrade (3)–(4) to immigration truth.

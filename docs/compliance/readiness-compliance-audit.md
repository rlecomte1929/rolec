# Readiness & compliance execution audit

**Scope:** HR case summary readiness card, assignment `run-compliance`, case-level compliance API, template/reference data, destination/route resolution.

## High-level architecture

| Layer | Responsibility |
|--------|----------------|
| **Case Readiness Core** | Destination/route → `readiness_templates` + per-assignment state (`case_readiness_*`). Operational checklist & milestones. |
| **Assignment compliance engine** (`ComplianceEngine`) | Deterministic checks against `mobility_rules.json` (or defaults): housing cap, lead time, document flags. |
| **Case compliance** (`policy_engine.build_compliance_report`) | Spend / policy / exceptions — separate from readiness templates. |

These systems are **not unified** today; this document traces each path.

---

## Execution flow (diagram)

```
HR opens Case Summary (assignment id = case route param)
    │
    ├─► GET /api/hr/assignments/{id}  → includes complianceReport JSON if present
    │
    ├─► GET /api/hr/assignments/{id}/readiness/summary
    │       └─► db.get_hr_readiness_summary(id)
    │               ├─► resolve_readiness_destination_for_assignment
    │               ├─► _readiness_store_available()  [NEW: probes readiness_templates]
    │               ├─► get_readiness_template(dest, route)
    │               ├─► ensure_case_readiness_binding
    │               └─► aggregate checklist/milestone counts
    │
    ├─► (expand) GET /api/hr/assignments/{id}/readiness/detail
    │       └─► get_hr_readiness_detail → checklist + milestones + provenance enrichment
    │
    └─► POST /api/hr/assignments/{id}/run-compliance
            └─► compliance_engine.run(profile) → save JSON report
                    [NEW: empty profile allowed; report enriched with provenance + explanation]
```

**Case-level compliance (different URL shape):**

```
GET  /api/hr/cases/{case_id}/compliance
POST /api/hr/cases/{case_id}/compliance/run
    └─► policy_engine.build_compliance_report(...)  [not assignment engine]
```

---

## Inputs used

### Readiness summary

| Input | Source |
|--------|--------|
| `assignment_id` | Path param |
| Employee profile JSON | `get_employee_profile` → `movePlan.destination`, `relocationBasics.destCountry` |
| Case `profile_json` / `host_country` | If profile destination missing |
| Route | `resolve_readiness_route_key` → **v1 always `employment`** |
| Template row | `readiness_templates` WHERE `destination_key` + `route_key` |
| Checklist state | `case_readiness_checklist_state` |
| Milestone state | `case_readiness_milestone_state` |

### Assignment run-compliance

| Input | Source |
|--------|--------|
| Profile dict | `get_employee_profile` or **{}** if missing [NEW] |
| Rules | `mobility_rules.json` if present on CWD, else coded defaults |

---

## Outputs returned

### Readiness summary (`resolved: true`)

- Route title, HR/employee summary text, watchouts, checklist counts, next milestone.
- **NEW:** `disclaimer_legal`, `trust_summary`, `route_references[]`, `reference_set_version`, `human_review_required`.

### Readiness summary (`resolved: false`)

- `reason`: `no_destination` | `no_template` | `readiness_store_unavailable`
- **NEW:** `user_message`, `route_references` (when destination known), provenance version fields.

### Assignment compliance report (after enrich)

- `checks[]` with `output_category`, `primary_reference`, `rationale_legal_safety`, `human_review_required`
- `actions[]` as objects with `output_category`
- `explanation.steps[]` step-by-step audit narrative
- `meta`, `disclaimer_legal`, `verdict_explanation`

---

## Failure points (historical → current)

| Failure | Cause | Mitigation (implemented) |
|---------|--------|-------------------------|
| 500 on readiness summary | Postgres missing `readiness_templates` (migration not applied) | `_readiness_store_available()` probe; return `readiness_store_unavailable` without throwing |
| Seed crash on startup | Same missing table | Seed short-circuits if store unavailable |
| 400 on run-compliance | Strict “No employee profile” | Empty profile allowed; engine returns NEEDS_REVIEW-style checks + explanation |

---

## Hidden assumptions (explicit)

1. **Route key** is not read from immigration filings — fixed to `employment` until the product stores permit route.
2. **Readiness checklist text** is **internal operational guidance**, not a legal source, unless a row is **mapped** to an official pointer in `readiness_checklist_provenance_map.json`.
3. **Assignment compliance** is **internal policy / product rules**, never immigration law.
4. **Official URLs** are stored in `compliance_reference_sources.json` and surfaced by API — UI does not hardcode them.

---

## Deterministic vs heuristic

| Component | Nature |
|-----------|--------|
| Readiness template resolution (dest + route → template id) | Deterministic given DB + profile data |
| Checklist counts | Deterministic SQL aggregates |
| ComplianceEngine numeric comparisons (budget, dates) | Deterministic given profile + rules |
| Document booleans unknown | Treated as NEEDS_REVIEW (not guessed) |
| Immigration eligibility | **Not computed** — human review required |

---

## Reference implementation files

- `backend/database.py` — readiness CRUD, `_readiness_store_available`, summary/detail
- `backend/readiness_service.py` — destination normalization, default route
- `backend/provenance_catalog.py` — references, degraded payloads, compliance enrich
- `backend/seed_data/readiness_templates.json`, `compliance_reference_sources.json`, `readiness_checklist_provenance_map.json`
- `supabase/migrations/20260321000000_case_readiness_core.sql` — Postgres DDL
- `supabase/migrations/20260324120000_compliance_reference_sources.sql` — optional DB mirror for references
- `frontend/src/features/readiness/CaseReadinessCore.tsx`
- `frontend/src/pages/HrCaseSummary.tsx`
